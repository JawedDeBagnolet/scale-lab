"""Session extraction — read cookies/tokens from iPhone via MCP.

ScaleTweak automatically extracts sessions to /tmp/scale_session.json
after 15s of app launch. This service reads that file via SSH and
optionally verifies the session via IG private API.

Ported from VPS th_iphone/interact/session_extract.py.
"""

import json
import logging
from typing import Any

from app.services.dispatch import mcp_call, _ssh_exec, DEFAULT_MCP_PORT, DEFAULT_SSH_PORT

logger = logging.getLogger("session_extract")


async def extract_session(
    mcp_port: int = DEFAULT_MCP_PORT,
    ssh_port: int = DEFAULT_SSH_PORT,
    *,
    host: str = "127.0.0.1",
) -> dict | None:
    """Read the session JSON extracted by ScaleTweak on the iPhone.

    Returns dict with: sessionid, csrftoken, ds_user_id, mid, ig_did,
    authorization (Bearer IGT:2:...) or None if not found.
    """
    # Method 1: Read via MCP run_command (faster, no SSH needed for this)
    result = await mcp_call(
        mcp_port, "run_command",
        {"command": "cat /tmp/scale_session.json 2>/dev/null || echo '{}'"},
        timeout=10, host=host,
    )
    if result:
        try:
            content = result.get("content", [{}])
            if content and isinstance(content, list):
                raw = content[0].get("text", "{}")
                data = json.loads(raw)
                if data.get("sessionid") or data.get("authorization"):
                    logger.info("session extracted via MCP: user=%s", data.get("ds_user_id", "?"))
                    return data
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse session JSON via MCP: %s", e)

    # Method 2: Read via SSH (fallback)
    ok, output = await _ssh_exec(
        ssh_port,
        "cat /tmp/scale_session.json 2>/dev/null || echo '{}'",
        host=host, timeout=10,
    )
    if ok and output:
        try:
            text = output if isinstance(output, str) else output.decode()
            data = json.loads(text.strip())
            if data.get("sessionid") or data.get("authorization"):
                logger.info("session extracted via SSH: user=%s", data.get("ds_user_id", "?"))
                return data
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to parse session JSON via SSH: %s", e)

    logger.warning("No session found on device (mcp_port=%d, ssh_port=%d)", mcp_port, ssh_port)
    return None


async def verify_session(
    session: dict,
    *,
    platform: str = "ig",
    proxy_url: str | None = None,
) -> dict:
    """Verify a session is still valid via the IG/Threads private API.

    Also extracts csrftoken from the API response if not already present.
    Uses Scrapigo proxy if available to avoid datacenter IP blocks.

    Returns: {"valid": bool, "status": str, "username": str|None, "csrftoken": str|None}
    """
    import httpx

    sessionid = session.get("sessionid", "")
    csrftoken = session.get("csrftoken", "")
    ds_user_id = session.get("ds_user_id", "")
    mid = session.get("mid", "")
    authorization = session.get("authorization", "")

    if not sessionid and not authorization:
        return {"valid": False, "status": "no_session", "username": None, "csrftoken": None}

    # Auto-resolve proxy via Scrapigo if not provided
    if not proxy_url:
        try:
            from app.services.scrapigo import get_scrapigo_client
            sg = await get_scrapigo_client()
            if sg:
                logger.info("verify_session: Scrapigo client OK, generating proxy...")
                proxy_obj = await sg.get_proxy_for_account(ds_user_id or "verify", country="FR")
                if proxy_obj:
                    proxy_url = proxy_obj.url
                    logger.info("verify_session: using Scrapigo proxy %s:%s", proxy_obj.host, proxy_obj.port)
                else:
                    logger.warning("verify_session: Scrapigo proxy generation returned None")
            else:
                logger.warning("verify_session: no Scrapigo client (key missing?)")
        except Exception as e:
            logger.warning("verify_session: Scrapigo proxy error: %s", e)

    cookie_parts = []
    if sessionid:
        cookie_parts.append(f"sessionid={sessionid}")
    if csrftoken:
        cookie_parts.append(f"csrftoken={csrftoken}")
    if ds_user_id:
        cookie_parts.append(f"ds_user_id={ds_user_id}")
    if mid:
        cookie_parts.append(f"mid={mid}")

    headers = {
        "Cookie": "; ".join(cookie_parts),
        "User-Agent": "Barcelona 341.0.0.36.109 Android" if platform == "th" else "Instagram 321.0.0.39.109 Android",
        "X-IG-App-ID": "238260118697367" if platform == "th" else "936619743392459",
    }
    if authorization:
        headers["Authorization"] = authorization

    try:
        logger.info("verify_session: proxy=%s", proxy_url[:30] if proxy_url else "NONE (direct)")
        async with httpx.AsyncClient(timeout=15, verify=False, proxy=proxy_url) as client:
            url = "https://i.instagram.com/api/v1/feed/timeline/"
            resp = await client.get(url, headers=headers)
            logger.info("verify_session: HTTP %s (via %s)", resp.status_code, "proxy" if proxy_url else "direct")

            # Extract csrftoken from response cookies or headers
            extracted_csrf = None
            for cookie_header in resp.headers.get_list("set-cookie"):
                if "csrftoken=" in cookie_header:
                    extracted_csrf = cookie_header.split("csrftoken=")[1].split(";")[0]
                    break
            if not extracted_csrf:
                extracted_csrf = resp.headers.get("x-csrftoken")

            if resp.status_code == 200:
                data = resp.json()
                username = data.get("user", {}).get("username")
                return {"valid": True, "status": "active", "username": username, "csrftoken": extracted_csrf}
            elif resp.status_code == 401:
                return {"valid": False, "status": "expired", "username": None, "csrftoken": extracted_csrf}
            elif resp.status_code == 400:
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                if "checkpoint" in str(body):
                    return {"valid": False, "status": "checkpoint", "username": None, "csrftoken": extracted_csrf}
                return {"valid": False, "status": "error_400", "username": None, "csrftoken": extracted_csrf}
            else:
                return {"valid": False, "status": f"http_{resp.status_code}", "username": None, "csrftoken": extracted_csrf}

    except Exception as e:
        logger.warning("Session verification failed: %s", e)
        return {"valid": False, "status": f"error: {str(e)[:100]}", "username": None, "csrftoken": None}


async def extract_and_store(
    compte_id: str,
    mcp_port: int = DEFAULT_MCP_PORT,
    ssh_port: int = DEFAULT_SSH_PORT,
    *,
    host: str = "127.0.0.1",
    platform: str = "ig",
) -> dict | None:
    """Extract session, verify it, and store in DB for the given account.

    Returns the session dict if valid, None otherwise.
    """
    from uuid import UUID
    from app.db import AsyncSessionLocal
    from app.models.compte import Compte

    session = await extract_session(mcp_port, ssh_port, host=host)
    if not session:
        return None

    # Verify the session
    check = await verify_session(session, platform=platform)
    logger.info(
        "session verify for %s: valid=%s status=%s",
        compte_id, check["valid"], check["status"],
    )

    if not check["valid"]:
        return None

    # Merge csrftoken from API response into session data
    if check.get("csrftoken") and not session.get("csrftoken"):
        session["csrftoken"] = check["csrftoken"]
        logger.info("csrftoken extracted from API response for %s", compte_id)

    # Store in DB (update the compte's session_data field if it exists)
    try:
        async with AsyncSessionLocal() as db:
            compte = await db.get(Compte, UUID(str(compte_id)))
            if compte and hasattr(compte, "session_data"):
                compte.session_data = session
                await db.commit()
                logger.info("session stored for compte %s", compte_id)
    except Exception as e:
        logger.warning("Failed to store session for %s: %s", compte_id, e)

    return session
