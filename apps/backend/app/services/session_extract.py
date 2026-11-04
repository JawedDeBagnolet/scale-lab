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
) -> dict:
    """Verify a session is still valid via the IG/Threads private API.

    Returns: {"valid": bool, "status": str, "username": str|None}
    """
    import httpx

    sessionid = session.get("sessionid", "")
    csrftoken = session.get("csrftoken", "")
    ds_user_id = session.get("ds_user_id", "")
    mid = session.get("mid", "")
    authorization = session.get("authorization", "")

    if not sessionid:
        return {"valid": False, "status": "no_session", "username": None}

    headers = {
        "Cookie": f"sessionid={sessionid}; csrftoken={csrftoken}; ds_user_id={ds_user_id}; mid={mid}",
        "User-Agent": "Barcelona 341.0.0.36.109 Android" if platform == "th" else "Instagram 321.0.0.39.109 Android",
        "X-IG-App-ID": "238260118697367" if platform == "th" else "936619743392459",
    }
    if authorization:
        headers["Authorization"] = authorization

    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            url = "https://i.instagram.com/api/v1/feed/timeline/"
            resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                username = data.get("user", {}).get("username")
                return {"valid": True, "status": "active", "username": username}
            elif resp.status_code == 401:
                return {"valid": False, "status": "expired", "username": None}
            elif resp.status_code == 400:
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                if "checkpoint" in str(body):
                    return {"valid": False, "status": "checkpoint", "username": None}
                return {"valid": False, "status": "error_400", "username": None}
            else:
                return {"valid": False, "status": f"http_{resp.status_code}", "username": None}

    except Exception as e:
        logger.warning("Session verification failed: %s", e)
        return {"valid": False, "status": f"error: {str(e)[:100]}", "username": None}


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
