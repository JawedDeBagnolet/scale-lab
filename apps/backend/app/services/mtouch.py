"""MTOUCH service — multi-touch gestures and media import on iPhone.

MTOUCH is a tweak running on port 8091 on the iPhone. Since the SSH
tunnel only forwards ports 2223 (SSH) and 18090 (MCP), we reach MTOUCH
by calling ios-mcp's `run_command` tool to curl localhost:8091 on-device.

Endpoints:
    GET  /health                           → health check
    POST /pinch  {cx, cy, scale, duration} → two-finger pinch (zoom)
    POST /rotate {cx, cy, angle, duration} → two-finger rotation
    POST /import {path}                    → import media into Camera Roll
    POST /tap    {x, y}                    → tap via MCP manager
"""

import json
import logging
from typing import Any

from app.services.dispatch import mcp_call, DEFAULT_MCP_PORT

logger = logging.getLogger("mtouch")

MTOUCH_PORT = 8091


async def _mtouch_call(
    endpoint: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    mcp_port: int = DEFAULT_MCP_PORT,
    host: str = "127.0.0.1",
    timeout: float = 15,
) -> dict | None:
    """Call a MTOUCH HTTP endpoint via MCP run_command + curl on-device.

    Returns parsed JSON response or None on failure.
    """
    url = f"http://127.0.0.1:{MTOUCH_PORT}{endpoint}"

    if method == "GET":
        cmd = f"curl -s --max-time 10 {url}"
    else:
        payload = json.dumps(data or {})
        # Escape single quotes in payload for shell
        payload_escaped = payload.replace("'", "'\\''")
        cmd = (
            f"curl -s --max-time 10 -X POST {url} "
            f"-H 'Content-Type: application/json' "
            f"-d '{payload_escaped}'"
        )

    result = await mcp_call(mcp_port, "run_command", {"command": cmd}, timeout=timeout, host=host)
    if result is None:
        logger.warning("mtouch %s %s: MCP run_command failed", method, endpoint)
        return None

    # Parse the MCP result — run_command returns content[].text with stdout
    try:
        content = result.get("content", [])
        if not content or not isinstance(content, list):
            logger.warning("mtouch %s %s: empty MCP content", method, endpoint)
            return None
        stdout = content[0].get("text", "")
        if not stdout.strip():
            logger.warning("mtouch %s %s: empty stdout", method, endpoint)
            return None
        return json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning("mtouch %s %s: invalid JSON: %s", method, endpoint, stdout[:100])
        return None
    except Exception as e:
        logger.warning("mtouch %s %s: parse error: %s", method, endpoint, e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════════════════════

async def mtouch_health(
    mcp_port: int = DEFAULT_MCP_PORT,
    host: str = "127.0.0.1",
) -> dict | None:
    """Check MTOUCH health. Returns {"ok": true, "service": "mtouch"} or None."""
    return await _mtouch_call("/health", mcp_port=mcp_port, host=host)


async def mtouch_pinch(
    cx: float,
    cy: float,
    scale: float,
    duration: int = 300,
    *,
    mcp_port: int = DEFAULT_MCP_PORT,
    host: str = "127.0.0.1",
) -> dict | None:
    """Two-finger pinch gesture.

    Args:
        cx, cy: Center coordinates of the pinch
        scale: Scale factor (>1 = zoom in, <1 = zoom out)
        duration: Duration in ms (default 300)
    """
    logger.info("mtouch pinch at (%.0f,%.0f) scale=%.2f dur=%dms", cx, cy, scale, duration)
    return await _mtouch_call(
        "/pinch",
        method="POST",
        data={"cx": cx, "cy": cy, "scale": scale, "duration": duration},
        mcp_port=mcp_port,
        host=host,
    )


async def mtouch_rotate(
    cx: float,
    cy: float,
    angle: float,
    duration: int = 300,
    *,
    mcp_port: int = DEFAULT_MCP_PORT,
    host: str = "127.0.0.1",
) -> dict | None:
    """Two-finger rotation gesture.

    Args:
        cx, cy: Center coordinates of the rotation
        angle: Rotation angle in degrees
        duration: Duration in ms (default 300)
    """
    logger.info("mtouch rotate at (%.0f,%.0f) angle=%.0f dur=%dms", cx, cy, angle, duration)
    return await _mtouch_call(
        "/rotate",
        method="POST",
        data={"cx": cx, "cy": cy, "angle": angle, "duration": duration},
        mcp_port=mcp_port,
        host=host,
    )


async def mtouch_import_media(
    path: str,
    *,
    mcp_port: int = DEFAULT_MCP_PORT,
    host: str = "127.0.0.1",
) -> dict | None:
    """Import a media file into the iPhone Camera Roll via PHPhotoLibrary.

    Args:
        path: Absolute path on the iPhone (e.g. /var/mobile/Media/th_media/photo.jpg)
    """
    logger.info("mtouch import_media: %s", path)
    return await _mtouch_call(
        "/import",
        method="POST",
        data={"path": path},
        mcp_port=mcp_port,
        host=host,
    )


async def mtouch_tap(
    x: float,
    y: float,
    *,
    mcp_port: int = DEFAULT_MCP_PORT,
    host: str = "127.0.0.1",
) -> dict | None:
    """Tap via MTOUCH (passes through to MCP manager).

    Args:
        x, y: Tap coordinates
    """
    return await _mtouch_call(
        "/tap",
        method="POST",
        data={"x": x, "y": y},
        mcp_port=mcp_port,
        host=host,
    )
