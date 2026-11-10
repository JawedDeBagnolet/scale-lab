"""IG Private API client for scraper accounts — uses Scrapigo proxy.

Built on top of IGApiClient but:
- Uses session_data from ScraperAccount (not iPhone extraction)
- Routes all requests through Scrapigo residential proxy
- Tracks bandwidth consumption per account
- Handles session expiry and rate limiting

Usage:
    from app.services.ig_api_scraper import IGScraperClient

    client = await IGScraperClient.from_db(db, platform="ig")
    results = await client.search_users("nike")
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger("ig_api_scraper")

IG_BASE = "https://i.instagram.com"
IG_APP_ID = "124024574287414"


@dataclass
class IGScraperClient:
    """API client for IG private API using scraper account sessions + Scrapigo proxy."""

    authorization: str
    mid: str
    ig_did: str
    ds_user_id: str
    user_agent: str
    www_claim: str = "0"
    extra_headers: dict = field(default_factory=dict)

    # Scraper account tracking
    account_id: UUID | None = None
    proxy_url: str | None = None

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def from_scraper_account(cls, account) -> "IGScraperClient | None":
        """Build client from a ScraperAccount model instance."""
        session = account.session_data
        if not session or not session.get("authorization"):
            return None

        www_claim = "0"
        claims_raw = session.get("logging_claims", "")
        if claims_raw:
            try:
                claims = json.loads(claims_raw) if isinstance(claims_raw, str) else claims_raw
                ds = session.get("ds_user_id", "")
                www_claim = claims.get(ds, "0")
            except (json.JSONDecodeError, AttributeError):
                pass

        return cls(
            authorization=session.get("authorization", ""),
            mid=session.get("mid", ""),
            ig_did=session.get("ig_did", session.get("unique_id", "")),
            ds_user_id=session.get("ds_user_id", ""),
            user_agent=account.user_agent or session.get("user_agent",
                "Instagram 454.1.0.0.21 (iPhone10,6; iOS 16_7_15; fr_FR; fr; scale=3.00; 1125x2436; 588848498)"),
            www_claim=www_claim,
            extra_headers=session.get("request_headers", {}),
            account_id=account.id,
        )

    @classmethod
    async def from_db(
        cls,
        db,
        platform: str = "ig",
        account_id: UUID | None = None,
        exclude_ids: list[UUID] | None = None,
    ) -> "IGScraperClient | None":
        """Pick a scraper account from DB and build a client with Scrapigo proxy.

        If account_id is given, uses that specific account.
        Otherwise, picks the least recently used active account (load balancing).
        """
        from app.services.scraper_accounts import get_account, pick_account

        if account_id:
            account = await get_account(db, account_id)
        else:
            account = await pick_account(db, platform=platform, exclude_ids=exclude_ids)

        if not account:
            logger.warning("ig_scraper: no active scraper account for %s", platform)
            return None

        client = cls.from_scraper_account(account)
        if not client:
            logger.warning("ig_scraper: invalid session for @%s", account.username)
            return None

        # Generate Scrapigo proxy
        from app.services.scrapigo import get_scrapigo_client
        scrapigo = await get_scrapigo_client()
        if scrapigo:
            proxy = await scrapigo.get_proxy_for_account(
                account_id=str(account.id),
                country=account.proxy_country or "FR",
                ttl_minutes=120,
            )
            if proxy:
                client.proxy_url = proxy.url
                logger.info("ig_scraper: @%s → proxy %s:%d (%s)",
                            account.username, proxy.host, proxy.port, account.proxy_country)
        else:
            logger.warning("ig_scraper: Scrapigo non configuré, requêtes sans proxy")

        return client

    # ── HTTP ─────────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        """Build request headers matching a real IG iOS client."""
        h = {
            "User-Agent": self.user_agent,
            "Authorization": self.authorization,
            "X-IG-App-ID": IG_APP_ID,
            "X-IG-Device-ID": self.ig_did,
            "X-MID": self.mid,
            "X-IG-WWW-Claim": self.www_claim,
            "X-IG-Connection-Type": "WiFi",
            "X-IG-App-Locale": "fr_FR",
            "X-IG-Device-Locale": "fr_FR",
            "X-IG-Timezone-Offset": "3600",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }
        for k, v in self.extra_headers.items():
            if k not in h:
                h[k] = v
        return h

    async def _get(self, path: str, params: dict | None = None) -> dict:
        """GET request through Scrapigo proxy."""
        proxy = self.proxy_url
        async with httpx.AsyncClient(
            timeout=20,
            verify=False,
            proxy=proxy,
        ) as client:
            resp = await client.get(
                f"{IG_BASE}{path}",
                headers=self._headers(),
                params=params,
            )
            # Track usage
            await self._track(len(resp.content))
            if resp.status_code == 401:
                await self._mark_expired("session expired (401)")
            elif resp.status_code == 429:
                await self._mark_rate_limited()
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, data: dict | None = None) -> dict:
        """POST request through Scrapigo proxy."""
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        proxy = self.proxy_url
        async with httpx.AsyncClient(
            timeout=20,
            verify=False,
            proxy=proxy,
        ) as client:
            resp = await client.post(
                f"{IG_BASE}{path}",
                headers=headers,
                content="&".join(f"{k}={v}" for k, v in (data or {}).items()),
            )
            await self._track(len(resp.content))
            if resp.status_code == 401:
                await self._mark_expired("session expired (401)")
            elif resp.status_code == 429:
                await self._mark_rate_limited()
            resp.raise_for_status()
            return resp.json()

    # ── Usage tracking ───────────────────────────────────────────────────

    async def _track(self, response_bytes: int = 0):
        """Track bandwidth usage for this scraper account."""
        if not self.account_id:
            return
        try:
            from app.db import AsyncSessionLocal
            from app.services.scraper_accounts import track_usage
            async with AsyncSessionLocal() as db:
                await track_usage(db, self.account_id, bytes_delta=response_bytes)
        except Exception:
            pass  # non-critical

    async def _mark_expired(self, error: str):
        if not self.account_id:
            return
        try:
            from app.db import AsyncSessionLocal
            from app.services.scraper_accounts import mark_error
            async with AsyncSessionLocal() as db:
                await mark_error(db, self.account_id, error, status="expired")
        except Exception:
            pass

    async def _mark_rate_limited(self):
        if not self.account_id:
            return
        try:
            from app.db import AsyncSessionLocal
            from app.services.scraper_accounts import mark_error
            async with AsyncSessionLocal() as db:
                await mark_error(db, self.account_id, "rate limited (429)", status="rate_limited")
        except Exception:
            pass

    # ── API methods (same as IGApiClient) ────────────────────────────────

    async def verify(self) -> dict:
        """Verify session is valid."""
        try:
            data = await self._get(f"/api/v1/users/{self.ds_user_id}/info/")
            user = data.get("user", {})
            return {
                "ok": True,
                "user": {
                    "pk": user.get("pk"),
                    "username": user.get("username"),
                    "full_name": user.get("full_name"),
                },
            }
        except httpx.HTTPStatusError as e:
            return {"ok": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}

    async def search_users(self, query: str, count: int = 10) -> list[dict]:
        """Search IG users (autocomplete)."""
        data = await self._get(
            "/api/v1/users/search/",
            params={"q": query, "count": count},
        )
        users = data.get("users", [])
        return [
            {
                "pk": u.get("pk"),
                "username": u.get("username"),
                "full_name": u.get("full_name", ""),
                "profile_pic_url": u.get("profile_pic_url", ""),
                "is_verified": u.get("is_verified", False),
                "is_private": u.get("is_private", False),
                "follower_count": u.get("follower_count"),
            }
            for u in users
        ]

    async def get_user_info(self, user_pk: str) -> dict | None:
        """Get full user profile info."""
        data = await self._get(f"/api/v1/users/{user_pk}/info/")
        user = data.get("user")
        if not user:
            return None
        return {
            "pk": user.get("pk"),
            "username": user.get("username"),
            "full_name": user.get("full_name", ""),
            "biography": user.get("biography", ""),
            "profile_pic_url": user.get("profile_pic_url", ""),
            "hd_profile_pic_url": (user.get("hd_profile_pic_url_info", {}) or {}).get("url", ""),
            "is_verified": user.get("is_verified", False),
            "is_private": user.get("is_private", False),
            "is_business": user.get("is_business", False),
            "follower_count": user.get("follower_count", 0),
            "following_count": user.get("following_count", 0),
            "media_count": user.get("media_count", 0),
            "external_url": user.get("external_url", ""),
            "category": user.get("category", ""),
        }

    async def get_user_feed(
        self, user_pk: str, count: int = 12, max_id: str | None = None
    ) -> dict:
        """Get user's media feed with pagination."""
        params = {"count": count}
        if max_id:
            params["max_id"] = max_id
        data = await self._get(f"/api/v1/feed/user/{user_pk}/", params=params)
        return {
            "items": data.get("items", []),
            "more_available": data.get("more_available", False),
            "next_max_id": data.get("next_max_id"),
        }
