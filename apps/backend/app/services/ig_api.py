"""Instagram Private API client — read-only queries via extracted sessions.

Uses the Bearer token + headers extracted by ScaleTweak on the iPhone.
All calls are GET-only (no writes, no csrftoken needed).

Session data comes from /tmp/scale_session.json on the iPhone, read via
SSH or cached in DB (compte.env.ig_session).

Usage:
    from app.services.ig_api import IGApiClient

    client = await IGApiClient.from_compte(db, compte_id)
    results = await client.search_users("nike")
    profile = await client.get_user_info(25025320)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx

from app.services.dispatch import _ssh_exec

logger = logging.getLogger("ig_api")

IG_BASE = "https://i.instagram.com"
IG_APP_ID = "124024574287414"  # iOS app ID


@dataclass
class IGApiClient:
    """Stateless client for IG private API calls."""

    authorization: str
    mid: str
    ig_did: str
    ds_user_id: str
    user_agent: str = "Instagram 454.1.0.0.21 (iPhone10,6; iOS 16_7_15; fr_FR; fr; scale=3.00; 1125x2436; 588848498)"
    www_claim: str = "0"
    extra_headers: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    async def from_compte(cls, db, compte_id: str | UUID) -> "IGApiClient | None":
        """Build a client from a compte's stored or live session."""
        from app.models.compte import Compte
        from app.models.iphone import IPhone

        compte = await db.get(Compte, UUID(str(compte_id)))
        if not compte or not compte.device_id:
            logger.warning("ig_api: compte %s not found or no device", compte_id)
            return None

        env = compte.env or {}

        # Try cached session first
        ig_session = env.get("ig_session")
        if ig_session and ig_session.get("authorization"):
            return cls._from_session(ig_session)

        # Otherwise, extract live from iPhone
        iphone = await db.get(IPhone, UUID(str(compte.device_id)))
        if not iphone or not iphone.ssh_port:
            logger.warning("ig_api: iPhone not found or no ssh_port for %s", compte_id)
            return None

        session = await cls._extract_live(iphone.ssh_port)
        if not session:
            return None

        # Cache in DB
        env["ig_session"] = session
        compte.env = {**env}  # trigger SQLAlchemy change detection
        await db.commit()

        return cls._from_session(session)

    @classmethod
    def _from_session(cls, session: dict) -> "IGApiClient":
        """Build client from a session dict."""
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
        )

    @classmethod
    async def _extract_live(cls, ssh_port: int, host: str = "127.0.0.1") -> dict | None:
        """Read /tmp/scale_session.json from the iPhone."""
        try:
            raw = await _ssh_exec(ssh_port, "cat /tmp/scale_session.json 2>/dev/null", host=host)
            if not raw or not raw.strip():
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning("ig_api: failed to read session: %s", e)
            return None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

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
        # Merge any extra headers captured from real IG requests
        for k, v in self.extra_headers.items():
            if k not in h:
                h[k] = v
        return h

    async def _get(self, path: str, params: dict | None = None) -> dict:
        """GET request to IG private API."""
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{IG_BASE}{path}",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, data: dict | None = None) -> dict:
        """POST request to IG private API (form-encoded)."""
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.post(
                f"{IG_BASE}{path}",
                headers=headers,
                content="&".join(f"{k}={v}" for k, v in (data or {}).items()),
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Recherche de comptes (autocomplete)
    # ------------------------------------------------------------------

    async def search_users(self, query: str, count: int = 10) -> list[dict]:
        """Search IG users — returns [{pk, username, full_name, profile_pic_url, is_verified}]."""
        data = await self._get("/api/v1/users/search/", {"q": query, "count": count})
        results = []
        for u in data.get("users", []):
            results.append({
                "pk": str(u.get("pk", "")),
                "username": u.get("username", ""),
                "full_name": u.get("full_name", ""),
                "profile_pic_url": u.get("profile_pic_url", ""),
                "is_verified": u.get("is_verified", False),
                "is_private": u.get("is_private", False),
                "follower_count": u.get("follower_count"),
            })
        return results

    # ------------------------------------------------------------------
    # Profil utilisateur
    # ------------------------------------------------------------------

    async def get_user_info(self, user_pk: int | str) -> dict | None:
        """Get full user profile info."""
        data = await self._get(f"/api/v1/users/{user_pk}/info/")
        u = data.get("user")
        if not u:
            return None
        return {
            "pk": str(u.get("pk", "")),
            "username": u.get("username", ""),
            "full_name": u.get("full_name", ""),
            "biography": u.get("biography", ""),
            "profile_pic_url": u.get("profile_pic_url", ""),
            "hd_profile_pic_url": u.get("hd_profile_pic_url_info", {}).get("url", ""),
            "is_verified": u.get("is_verified", False),
            "is_private": u.get("is_private", False),
            "follower_count": u.get("follower_count", 0),
            "following_count": u.get("following_count", 0),
            "media_count": u.get("media_count", 0),
            "external_url": u.get("external_url", ""),
            "category": u.get("category", ""),
        }

    # ------------------------------------------------------------------
    # Feed utilisateur (publications)
    # ------------------------------------------------------------------

    async def get_user_feed(self, user_pk: int | str, count: int = 12, max_id: str | None = None) -> dict:
        """Get a user's posts. Returns {items: [...], next_max_id: str|None}."""
        params = {"count": count}
        if max_id:
            params["max_id"] = max_id
        data = await self._get(f"/api/v1/feed/user/{user_pk}/", params)
        items = []
        for item in data.get("items", []):
            media = self._parse_media(item)
            if media:
                items.append(media)
        return {
            "items": items,
            "next_max_id": data.get("next_max_id"),
            "has_more": data.get("more_available", False),
        }

    # ------------------------------------------------------------------
    # Timeline (feed)
    # ------------------------------------------------------------------

    async def get_timeline(self, reason: str = "cold_start_fetch") -> dict:
        """Get the user's home feed."""
        data = await self._post("/api/v1/feed/timeline/", {
            "is_pull_to_refresh": "0",
            "reason": reason,
        })
        items = []
        for item in data.get("feed_items", data.get("items", [])):
            media = item.get("media_or_ad", item)
            parsed = self._parse_media(media)
            if parsed:
                items.append(parsed)
        return {
            "items": items,
            "next_max_id": data.get("next_max_id"),
        }

    # ------------------------------------------------------------------
    # Recherche de sons (musique)
    # ------------------------------------------------------------------

    async def search_music(self, query: str, count: int = 20) -> list[dict]:
        """Search music tracks — returns [{id, title, artist, cover_url, preview_url}]."""
        data = await self._post("/api/v1/music/search/", {
            "q": query,
            "search_surface": "clips_music_search",
            "count": str(count),
        })
        return self._parse_music_items(data)

    async def get_trending_music(self, count: int = 30) -> list[dict]:
        """Get trending music tracks."""
        data = await self._post("/api/v1/music/search/", {
            "q": "",
            "search_surface": "clips_music_search",
            "count": str(count),
        })
        return self._parse_music_items(data)

    # ------------------------------------------------------------------
    # Stats / Analytics
    # ------------------------------------------------------------------

    async def get_account_insights(self, user_pk: int | str) -> dict | None:
        """Get account insights (followers, reach, impressions).

        Note: requires a professional/creator account.
        """
        try:
            data = await self._get(f"/api/v1/insights/account_organic_insights/", {
                "ig_user_id": str(user_pk),
                "interval": "week",
            })
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 403):
                logger.info("insights not available for %s (personal account?)", user_pk)
                return None
            raise

    async def get_media_insights(self, media_pk: str) -> dict | None:
        """Get insights for a specific media (impressions, reach, engagement)."""
        try:
            data = await self._get(f"/api/v1/insights/media_organic_insights/{media_pk}/", {
                "ig_sig_key_version": "4",
            })
            return data
        except httpx.HTTPStatusError:
            return None

    # ------------------------------------------------------------------
    # Session verification
    # ------------------------------------------------------------------

    async def verify(self) -> dict:
        """Check if this session is still valid. Returns {valid, status, username}."""
        try:
            data = await self._get("/api/v1/accounts/current_user/", {"edit": "true"})
            user = data.get("user", {})
            return {
                "valid": True,
                "status": "active",
                "username": user.get("username"),
                "pk": str(user.get("pk", "")),
            }
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 401:
                return {"valid": False, "status": "expired", "username": None}
            elif code == 400:
                return {"valid": False, "status": "checkpoint", "username": None}
            return {"valid": False, "status": f"http_{code}", "username": None}
        except Exception as e:
            return {"valid": False, "status": str(e)[:100], "username": None}

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_media(self, item: dict) -> dict | None:
        """Parse a media item into a clean dict."""
        if not item or not item.get("pk"):
            return None
        user = item.get("user", {})
        caption = item.get("caption") or {}

        # Get best image
        image_url = ""
        candidates = item.get("image_versions2", {}).get("candidates", [])
        if candidates:
            image_url = candidates[0].get("url", "")
        # Carousel
        carousel = []
        for c in item.get("carousel_media", []):
            c_candidates = c.get("image_versions2", {}).get("candidates", [])
            if c_candidates:
                carousel.append(c_candidates[0].get("url", ""))

        return {
            "pk": str(item.get("pk", "")),
            "code": item.get("code", ""),
            "media_type": item.get("media_type"),  # 1=photo, 2=video, 8=carousel
            "image_url": image_url,
            "carousel_urls": carousel if carousel else None,
            "video_url": item.get("video_versions", [{}])[0].get("url") if item.get("video_versions") else None,
            "caption": caption.get("text", ""),
            "like_count": item.get("like_count", 0),
            "comment_count": item.get("comment_count", 0),
            "play_count": item.get("play_count"),
            "taken_at": item.get("taken_at"),
            "user": {
                "pk": str(user.get("pk", "")),
                "username": user.get("username", ""),
                "profile_pic_url": user.get("profile_pic_url", ""),
            },
        }

    @staticmethod
    def _parse_music_items(data: dict) -> list[dict]:
        """Parse music search results."""
        results = []
        for item in data.get("items", []):
            track = item.get("track", item.get("audio", item))
            results.append({
                "id": str(track.get("id", "")),
                "title": track.get("title", ""),
                "artist": track.get("subtitle", track.get("artist_name", "")),
                "cover_url": track.get("cover_artwork_uri",
                    track.get("cover_artwork_thumbnail_uri", "")),
                "preview_url": track.get("progressive_download_url",
                    track.get("dash_manifest", "")),
                "duration_ms": track.get("duration_in_ms", 0),
                "is_trending": track.get("is_trending", False),
            })
        return results
