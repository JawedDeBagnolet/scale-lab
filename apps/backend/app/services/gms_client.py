"""GetMySocial API v3 client.

Base URL: https://api.getmysocial.com
Auth: Authorization: Bearer <gms_live_*>
"""

import httpx

GMS_BASE = "https://api.getmysocial.com"
TIMEOUT = 12.0


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


async def test_connection(api_key: str) -> dict:
    """Test the API key by calling GET /v3/_ping.

    Returns {"ok": True, ...} on success or {"ok": False, "error": "..."} on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            # Try _ping first (health check)
            r = await c.get(f"{GMS_BASE}/v3/_ping", headers=_headers(api_key))
            if r.status_code == 200:
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                return {"ok": True, "ping": data}
            if r.status_code == 401:
                return {"ok": False, "error": "Cle API invalide"}
            if r.status_code == 403:
                body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                err = body.get("error", {})
                if isinstance(err, dict) and err.get("code") == "plan_required":
                    return {"ok": False, "error": "Plan sans acces API"}
                return {"ok": False, "error": "Acces refuse"}
            # Fallback: try listing links with limit=1
            r2 = await c.get(
                f"{GMS_BASE}/v3/links",
                headers=_headers(api_key),
                params={"limit": 1},
            )
            if r2.status_code == 200:
                return {"ok": True}
            return {"ok": False, "error": f"Erreur {r.status_code}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Timeout - serveur GMS injoignable"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def get_status(api_key: str) -> dict:
    """Get account status: link count, plan info, etc."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as c:
            headers = _headers(api_key)

            # Fetch links (just count)
            r_links = await c.get(
                f"{GMS_BASE}/v3/links",
                headers=headers,
                params={"limit": 1},
            )
            link_count = 0
            landing_count = 0
            if r_links.status_code == 200:
                data = r_links.json()
                # To get total count, we need to page through or use overview
                # For now, fetch up to 100 to count
                r_all = await c.get(
                    f"{GMS_BASE}/v3/links",
                    headers=headers,
                    params={"limit": 100},
                )
                if r_all.status_code == 200:
                    all_data = r_all.json()
                    links = all_data.get("data", [])
                    link_count = len(links)
                    landing_count = sum(
                        1 for lk in links if lk.get("type") == "landing"
                    )
                    # If has_more, there are more links
                    if all_data.get("has_more"):
                        link_count = f"{link_count}+"

            # Fetch teams
            r_teams = await c.get(
                f"{GMS_BASE}/v3/teams",
                headers=headers,
                params={"limit": 1},
            )
            team_count = 0
            if r_teams.status_code == 200:
                team_data = r_teams.json()
                team_count = len(team_data.get("data", []))

            # Fetch groups
            r_groups = await c.get(
                f"{GMS_BASE}/v3/groups",
                headers=headers,
                params={"limit": 100},
            )
            group_count = 0
            if r_groups.status_code == 200:
                group_data = r_groups.json()
                group_count = len(group_data.get("data", []))

            return {
                "ok": True,
                "link_count": link_count,
                "landing_count": landing_count,
                "team_count": team_count,
                "group_count": group_count,
            }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def list_links(
    api_key: str,
    limit: int = 25,
    cursor: str | None = None,
    sort: str = "-created",
    group_id: str | None = None,
    team_id: str | None = None,
) -> dict:
    """List links (paginated)."""
    params: dict = {"limit": limit, "sort": sort}
    if cursor:
        params["cursor"] = cursor
    if group_id:
        params["group_id"] = group_id
    if team_id:
        params["team_id"] = team_id

    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(
            f"{GMS_BASE}/v3/links",
            headers=_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        return r.json()


async def get_link(api_key: str, link_id: str) -> dict:
    """Get a single link by ID."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(
            f"{GMS_BASE}/v3/links/{link_id}",
            headers=_headers(api_key),
        )
        r.raise_for_status()
        return r.json()


async def get_analytics_overview(
    api_key: str,
    timeframe: str = "today",
    link_id: str | None = None,
    team_id: str | None = None,
) -> dict:
    """Get analytics overview."""
    params: dict = {"timeframe": timeframe}
    if link_id:
        params["link_id"] = link_id
    if team_id:
        params["team_id"] = team_id

    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(
            f"{GMS_BASE}/v3/analytics/overview",
            headers=_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        return r.json()


async def get_analytics_time_series(
    api_key: str,
    timeframe: str = "7",
    interval: str = "day",
    metric: str = "pageviews",
    link_id: str | None = None,
) -> dict:
    """Get analytics time series."""
    params: dict = {
        "timeframe": timeframe,
        "interval": interval,
        "metric": metric,
    }
    if link_id:
        params["link_id"] = link_id

    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(
            f"{GMS_BASE}/v3/analytics/time-series",
            headers=_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        return r.json()


async def list_groups(api_key: str, team_id: str | None = None) -> dict:
    """List groups."""
    params: dict = {"limit": 100}
    if team_id:
        params["team_id"] = team_id

    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(
            f"{GMS_BASE}/v3/groups",
            headers=_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        return r.json()
