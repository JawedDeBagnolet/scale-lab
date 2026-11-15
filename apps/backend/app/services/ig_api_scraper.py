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
    def from_compte(cls, compte) -> "IGScraperClient | None":
        """Build client from a Compte model instance (is_scraper=True).

        Reads session_data from the compte — same data ScaleTweak extracts
        after a login on the iPhone.
        """
        session = compte.session_data
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
            user_agent=session.get("user_agent",
                "Instagram 454.1.0.0.21 (iPhone10,6; iOS 16_7_15; fr_FR; fr; scale=3.00; 1125x2436; 588848498)"),
            www_claim=www_claim,
            extra_headers=session.get("request_headers", {}),
            account_id=compte.id,
        )

    # Keep old name as alias for verify endpoint compat
    from_scraper_account = from_compte

    @classmethod
    async def from_db(
        cls,
        db,
        platform: str = "ig",
        account_id: UUID | None = None,
        exclude_ids: list[UUID] | None = None,
    ) -> "IGScraperClient | None":
        """Pick a scraper compte from DB and build a client with Scrapigo proxy.

        If account_id is given, uses that specific compte.
        Otherwise, picks the least recently used active scraper compte (load balancing).
        """
        from sqlalchemy import select
        from app.models.compte import Compte

        if account_id:
            compte = await db.get(Compte, account_id)
        else:
            # Pick least recently used active scraper compte
            stmt = (
                select(Compte)
                .where(
                    Compte.is_scraper.is_(True),
                    Compte.plateforme == platform,
                    Compte.status == "ok",
                    Compte.session_data.isnot(None),
                )
                .order_by(Compte.updated_at.asc().nullsfirst())
                .limit(1)
            )
            if exclude_ids:
                stmt = stmt.where(Compte.id.notin_(exclude_ids))
            result = await db.execute(stmt)
            compte = result.scalar_one_or_none()

        if not compte:
            logger.warning("ig_scraper: no active scraper compte for %s", platform)
            return None

        client = cls.from_compte(compte)
        if not client:
            logger.warning("ig_scraper: invalid session for @%s", compte.handle)
            return None

        # Generate Scrapigo proxy
        from app.services.scrapigo import get_scrapigo_client
        scrapigo = await get_scrapigo_client()
        if scrapigo:
            env = compte.env or {}
            country = env.get("proxy_country", "FR")
            proxy = await scrapigo.get_proxy_for_account(
                account_id=str(compte.id),
                country=country,
                ttl_minutes=120,
            )
            if proxy:
                client.proxy_url = proxy.url
                logger.info("ig_scraper: @%s → proxy %s:%d (%s)",
                            compte.handle, proxy.host, proxy.port, country)
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

    async def get_user_highlights(self, user_pk: str) -> list[dict]:
        """Get user's story highlights (tray)."""
        data = await self._get(
            f"/api/v1/highlights/{user_pk}/highlights_tray/",
        )
        trays = data.get("tray", [])
        return [
            {
                "id": t.get("id"),
                "title": t.get("title", ""),
                "cover_url": (
                    (t.get("cover_media", {}) or {})
                    .get("cropped_image_version", {})
                    .get("url", "")
                ),
                "media_count": t.get("media_count", 0),
            }
            for t in trays
        ]

    async def get_user_profile_full(self, username: str) -> dict | None:
        """Get full profile data: info + highlights. One call for the modal.

        Uses web profile endpoint to resolve username → pk, then fetches
        detailed info and highlights in parallel.
        """
        import asyncio

        # Resolve username to pk via search
        data = await self._get(
            "/api/v1/users/web_profile_info/",
            params={"username": username},
        )
        user = (data.get("data", {}) or {}).get("user") or data.get("user")
        if not user:
            return None

        pk = str(user.get("pk", user.get("id", "")))
        if not pk:
            return None

        # Fetch detailed info + highlights in parallel
        info_task = self.get_user_info(pk)
        highlights_task = self.get_user_highlights(pk)
        info, highlights = await asyncio.gather(info_task, highlights_task, return_exceptions=True)

        if isinstance(info, Exception):
            logger.warning("get_user_info failed for %s: %s", username, info)
            info = None
        if isinstance(highlights, Exception):
            logger.warning("get_highlights failed for %s: %s", username, highlights)
            highlights = []

        if not info:
            # Fallback: use data from web_profile_info
            info = {
                "pk": pk,
                "username": user.get("username", username),
                "full_name": user.get("full_name", ""),
                "biography": user.get("biography", ""),
                "profile_pic_url": user.get("profile_pic_url", ""),
                "hd_profile_pic_url": (user.get("hd_profile_pic_url_info", {}) or {}).get("url", ""),
                "is_verified": user.get("is_verified", False),
                "is_private": user.get("is_private", False),
                "is_business": user.get("is_business", False),
                "follower_count": user.get("edge_followed_by", {}).get("count", user.get("follower_count", 0)),
                "following_count": user.get("edge_follow", {}).get("count", user.get("following_count", 0)),
                "media_count": user.get("edge_owner_to_timeline_media", {}).get("count", user.get("media_count", 0)),
                "external_url": user.get("external_url", ""),
                "category": user.get("category_name", user.get("category", "")),
            }

        info["highlights"] = highlights if not isinstance(highlights, Exception) else []
        return info

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
