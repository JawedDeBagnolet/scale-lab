"""iPhone command dispatch — sends orders to on-device agents via USB tunnel.

Architecture:
  VPS  ──USB──>  iPhone (jailbroken, running scale-agent on port 8765)

The on-device agent exposes a simple HTTP API:
  POST /execute   — run a command (follow, like, comment, etc.)
  GET  /status    — device + account health
  POST /abort     — cancel current action

Communication uses pymobiledevice3's TCP tunnel over USB, so no network
needed on the iPhone side (only USB cable).

When the agent is not yet installed/running, commands are queued in-memory
and a warning is logged.  The engine treats "agent not ready" as a
recoverable error so the run can retry on the next tick.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger("dispatch")

# Port the on-device agent listens on
AGENT_PORT = 8765
# Timeout for a single command (seconds)
COMMAND_TIMEOUT = 30
# Timeout for establishing the USB tunnel
TUNNEL_TIMEOUT = 10

# Cache: udid -> (tunnel_port, created_at)
_tunnel_cache: dict[str, tuple[int, datetime]] = {}
# Cache TTL (seconds) — tunnels are re-established after this
_TUNNEL_TTL = 300

_PYMOBILE_AVAILABLE = False

try:
    from pymobiledevice3.usbmux import list_devices as _usbmux_list
    from pymobiledevice3.tcp_forwarder import UsbmuxTcpForwarder
    _PYMOBILE_AVAILABLE = True
except ImportError:
    logger.warning("pymobiledevice3 not installed — dispatch unavailable")


# ---------------------------------------------------------------------------
# USB tunnel management
# ---------------------------------------------------------------------------

async def _get_tunnel_port(udid: str) -> int | None:
    """Get or create a TCP tunnel to the agent on the iPhone.

    Returns the local port number, or None if the tunnel cannot be
    established (device disconnected, agent not running, etc.).
    """
    if not _PYMOBILE_AVAILABLE:
        return None

    # Check cache
    if udid in _tunnel_cache:
        port, created = _tunnel_cache[udid]
        age = (datetime.now(UTC) - created).total_seconds()
        if age < _TUNNEL_TTL:
            return port

    # Create a new tunnel
    try:
        loop = asyncio.get_event_loop()
        port = await asyncio.wait_for(
            loop.run_in_executor(None, _create_tunnel, udid),
            timeout=TUNNEL_TIMEOUT,
        )
        if port:
            _tunnel_cache[udid] = (port, datetime.now(UTC))
        return port
    except asyncio.TimeoutError:
        logger.warning("Tunnel timeout for device %s", udid)
        return None
    except Exception as e:
        logger.warning("Tunnel error for device %s: %s", udid, e)
        return None


def _create_tunnel(udid: str) -> int | None:
    """Blocking: create a TCP forwarder for the given UDID.

    Returns the local port that forwards to AGENT_PORT on the device.
    """
    try:
        forwarder = UsbmuxTcpForwarder(
            serial=udid,
            dst_port=AGENT_PORT,
            src_port=0,  # auto-assign
        )
        forwarder.start()
        return forwarder.local_port
    except Exception as e:
        logger.warning("Failed to create USB tunnel to %s: %s", udid, e)
        return None


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

async def dispatch_command(
    udid: str,
    command: dict[str, Any],
    *,
    timeout: float = COMMAND_TIMEOUT,
) -> tuple[bool, str, dict | None]:
    """Send a command to the on-device agent and wait for the result.

    Args:
        udid: Device UDID (from iPhone.telemetry.udid)
        command: Command payload (action, platform, account_id, handle, values, preset_ids)
        timeout: Max seconds to wait for a response

    Returns:
        (success: bool, message: str, result: dict | None)
    """
    port = await _get_tunnel_port(udid)
    if port is None:
        return False, "Cannot establish USB tunnel — device offline or agent not installed", None

    payload = json.dumps(command).encode()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port),
            timeout=5,
        )
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
        # Clear cached tunnel — it's likely stale
        _tunnel_cache.pop(udid, None)
        return False, f"Agent not reachable on device: {e}", None

    try:
        # Simple HTTP/1.1 request — the agent is a minimal HTTP server
        req = (
            f"POST /execute HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n"
            f"\r\n"
        ).encode() + payload

        writer.write(req)
        await writer.drain()

        # Read response
        response_data = await asyncio.wait_for(
            reader.read(8192),
            timeout=timeout,
        )

        writer.close()
        await writer.wait_closed()

        # Parse HTTP response
        return _parse_response(response_data)

    except asyncio.TimeoutError:
        writer.close()
        return False, f"Command timed out after {timeout}s", None
    except Exception as e:
        try:
            writer.close()
        except Exception:
            pass
        return False, f"Dispatch error: {e}", None


def _parse_response(data: bytes) -> tuple[bool, str, dict | None]:
    """Parse a raw HTTP response from the on-device agent."""
    try:
        text = data.decode("utf-8", errors="replace")
        # Split headers from body
        parts = text.split("\r\n\r\n", 1)
        if len(parts) < 2:
            return False, "Invalid response from agent", None

        status_line = parts[0].split("\r\n")[0]
        body = parts[1]

        # Parse status code
        status_code = int(status_line.split(" ")[1])

        result = json.loads(body) if body.strip() else {}

        if 200 <= status_code < 300:
            msg = result.get("message", "OK")
            return True, msg, result
        else:
            msg = result.get("error", f"Agent returned {status_code}")
            return False, msg, result

    except (json.JSONDecodeError, ValueError, IndexError) as e:
        return False, f"Failed to parse agent response: {e}", None


async def check_agent_status(udid: str) -> dict | None:
    """Check if the agent is running and get its status.

    Returns a status dict or None if unreachable.
    """
    port = await _get_tunnel_port(udid)
    if port is None:
        return None

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port),
            timeout=5,
        )

        req = (
            f"GET /status HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"\r\n"
        ).encode()

        writer.write(req)
        await writer.drain()

        data = await asyncio.wait_for(reader.read(4096), timeout=5)
        writer.close()
        await writer.wait_closed()

        ok, msg, result = _parse_response(data)
        return result if ok else None

    except Exception:
        return None


async def abort_action(udid: str) -> bool:
    """Tell the agent to abort the current action."""
    port = await _get_tunnel_port(udid)
    if port is None:
        return False

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port),
            timeout=5,
        )

        req = (
            f"POST /abort HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        ).encode()

        writer.write(req)
        await writer.drain()

        data = await asyncio.wait_for(reader.read(4096), timeout=5)
        writer.close()
        await writer.wait_closed()

        ok, _, _ = _parse_response(data)
        return ok

    except Exception:
        return False
