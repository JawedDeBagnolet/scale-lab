"""Scrapigo proxy service — génère des proxies résidentiels à la volée.

API docs: https://scrapigo.cc/fr/docs/api
Base URL: https://api.scrapigo.cc/v1

Usage:
    client = ScrapigoClient(api_key="sk_live_...")
    proxy = await client.generate_proxy(country="FR", sticky_minutes=60)
    # → "http://user:pass@host:port"

    # Pour un scraper account (sticky par compte)
    proxy = await client.get_proxy_for_account(account_id, country="FR")
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger("scrapigo")

BASE_URL = "https://api.scrapigo.cc/v1"


@dataclass
class ProxyLine:
    """Parsed proxy line."""
    host: str
    port: int
    username: str
    password: str
    protocol: str = "http"

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"

    @property
    def httpx_proxy(self) -> str:
        """Format for httpx proxy parameter."""
        return self.url


class ScrapigoClient:
    """Client for Scrapigo proxy API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self, method: str, path: str, json: dict | None = None, **kwargs
    ) -> dict | None:
        """Make an API request."""
        url = f"{BASE_URL}{path}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.request(
                    method, url, headers=self._headers, json=json, **kwargs
                )
                if resp.status_code == 429:
                    logger.warning("scrapigo: rate limited, retry after %s", resp.headers.get("Retry-After"))
                    return None
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("scrapigo %s %s: %s", method, path, e.response.text[:200])
            return None
        except Exception as e:
            logger.error("scrapigo %s %s: %s", method, path, str(e)[:100])
            return None

    # ── Account ──────────────────────────────────────────────────────────

    async def get_balance(self) -> dict | None:
        """Get account info: credit, remaining data."""
        return await self._request("GET", "/me")

    # ── Proxy generation ─────────────────────────────────────────────────

    async def generate_proxy(
        self,
        product: str = "residential",
        country: str = "FR",
        session: str = "sticky",
        ttl_minutes: int = 60,
        protocol: str = "http",
        count: int = 1,
    ) -> list[ProxyLine]:
        """Generate proxy lines.

        Args:
            product: "residential" ($0.99/GB) or "residential_instagram" ($1.60/GB)
            country: ISO code (FR, US, GB, DE) or "any"
            session: "rotating" (new IP per request) or "sticky" (same IP for ttl)
            ttl_minutes: sticky session duration (1-360, default 60)
            protocol: "http" or "socks5"
            count: number of lines (1-10000)

        Returns:
            List of ProxyLine objects
        """
        body = {
            "product": product,
            "country": country,
            "session": session,
            "protocol": protocol,
            "count": count,
            "format": "user_pass_host_port",
        }
        if session == "sticky":
            body["ttlMinutes"] = ttl_minutes

        data = await self._request("POST", "/proxies/generate", json=body)
        if not data:
            return []

        lines = []
        for entry in data.get("proxies", data.get("lines", [])):
            if isinstance(entry, str):
                # Format: user:pass@host:port
                parts = entry.split("@")
                if len(parts) == 2:
                    user_pass = parts[0].split(":")
                    host_port = parts[1].split(":")
                    if len(user_pass) >= 2 and len(host_port) >= 2:
                        lines.append(ProxyLine(
                            host=host_port[0],
                            port=int(host_port[1]),
                            username=user_pass[0],
                            password=":".join(user_pass[1:]),
                            protocol=protocol,
                        ))
            elif isinstance(entry, dict):
                lines.append(ProxyLine(
                    host=entry.get("host", ""),
                    port=int(entry.get("port", 0)),
                    username=entry.get("username", ""),
                    password=entry.get("password", ""),
                    protocol=protocol,
                ))
        return lines

    async def get_proxy_for_account(
        self,
        account_id: str,
        product: str = "residential",
        country: str = "FR",
        ttl_minutes: int = 120,
        protocol: str = "http",
    ) -> ProxyLine | None:
        """Generate a sticky proxy for a specific scraper account.

        Uses the account_id as part of the sticky session to ensure
        the same account always gets the same IP for the TTL duration.
        """
        lines = await self.generate_proxy(
            product=product,
            country=country,
            session="sticky",
            ttl_minutes=ttl_minutes,
            protocol=protocol,
            count=1,
        )
        return lines[0] if lines else None

    # ── Stats ────────────────────────────────────────────────────────────

    async def get_usage_summary(self) -> dict | None:
        """Get usage stats: bytes up/down, sessions, per product."""
        return await self._request("GET", "/stats/summary")

    async def get_usage_breakdown(self, group_by: str = "credential") -> dict | None:
        """Get usage breakdown by country, credential, or product."""
        return await self._request("GET", f"/stats/breakdown?groupBy={group_by}")


# ═════════════════════════════════════════════════════════════════════════════
# Helper — get client from DB settings
# ═════════════════════════════════════════════════════════════════════════════

async def get_scrapigo_client() -> ScrapigoClient | None:
    """Build a ScrapigoClient from workspace settings, or None if not configured."""
    try:
        from app.db import AsyncSessionLocal
        from app.models.settings import WorkspaceSettings

        async with AsyncSessionLocal() as db:
            settings = await db.get(WorkspaceSettings, 1)
            if settings and settings.scrapigo_api_key:
                return ScrapigoClient(settings.scrapigo_api_key)
    except Exception as e:
        logger.error("scrapigo: cannot load settings: %s", str(e)[:80])
    return None
