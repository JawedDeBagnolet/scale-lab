"""MTOUCH service — multi-touch gestures and media import on iPhone.

MTOUCH is a tweak running on port 8091 on the iPhone. We reach it
via SSH (port 2223) + curl on-device, because MCP's run_command is
broken on rootless jailbreak (no /bin/sh).

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

from app.services.dispatch import _ssh_exec, DEFAULT_SSH_PORT

logger = logging.getLogger("mtouch")

MTOUCH_PORT = 8091


async def _mtouch_call(
    endpoint: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    mcp_port: int = 18090,
    host: str = "127.0.0.1",
    timeout: float = 15,
) -> dict | None:
    """Call a MTOUCH HTTP endpoint via SSH + curl on-device.

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

    ok, output = await _ssh_exec(DEFAULT_SSH_PORT, cmd, timeout=timeout, host=host)
    if not ok:
        logger.warning("mtouch %s %s: SSH failed: %s", method, endpoint, str(output)[:80])
        return None

    try:
        if not isinstance(output, str):
            output = output.decode("utf-8", errors="replace")
        if not output.strip():
            logger.warning("mtouch %s %s: empty output", method, endpoint)
            return None
        return json.loads(output)
    except json.JSONDecodeError:
        logger.warning("mtouch %s %s: invalid JSON: %s", method, endpoint, str(output)[:100])
        return None
    except Exception as e:
        logger.warning("mtouch %s %s: parse error: %s", method, endpoint, e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════════════════════

async def mtouch_health(
    mcp_port: int = 18090,
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
    mcp_port: int = 18090,
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
    mcp_port: int = 18090,
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
    mcp_port: int = 18090,
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
    mcp_port: int = 18090,
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
