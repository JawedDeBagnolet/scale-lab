"""iPhone command dispatch — dual mode USB + network tunnel.

Two connection modes:

  USB (legacy):
    VPS ──USB──> iPhone (jailbroken, agent on port 8765)
    Uses pymobiledevice3 UsbmuxTcpForwarder to create a local TCP port.

  Tunnel (network):
    iPhone ──reverse-SSH──> VPS (MCP on 127.0.0.1:<mcp_port>, crane on 127.0.0.1:<crane_port>)
    Direct HTTP to the MCP JSON-RPC server exposed by the SSH tunnel.
    No pymobiledevice3 needed — the ports are already forwarded.

The on-device MCP agent (iOS accessibility driver) exposes:
  POST /mcp          — JSON-RPC (get_ui_elements, perform_action, etc.)
The on-device scale-agent (USB mode) exposes:
  POST /execute      — run a command
  GET  /status       — health check
  POST /abort        — cancel current action

The crane-controller (tunnel mode only) exposes:
  POST /sequence     — switch container
  GET  /inventory    — list containers
  POST /kill         — kill app

The engine decides which path to take based on iPhone.connection_type.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger("dispatch")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# USB agent port on the iPhone
AGENT_PORT = 8765
# Default MCP / crane ports for tunnel mode (overridden per device)
DEFAULT_MCP_PORT = 8190
DEFAULT_CRANE_PORT = 8180

# Timeouts (seconds)
COMMAND_TIMEOUT = 30
TUNNEL_TIMEOUT = 10
MCP_TIMEOUT = 60       # MCP actions can be slow (UI automation)
CRANE_TIMEOUT = 10

# USB tunnel cache: udid -> (local_port, created_at)
_tunnel_cache: dict[str, tuple[int, datetime]] = {}
_TUNNEL_TTL = 300

_PYMOBILE_AVAILABLE = False

try:
    from pymobiledevice3.usbmux import list_devices as _usbmux_list
    from pymobiledevice3.tcp_forwarder import UsbmuxTcpForwarder
    _PYMOBILE_AVAILABLE = True
except ImportError:
    logger.warning("pymobiledevice3 not installed — USB dispatch unavailable")


# ---------------------------------------------------------------------------
# Shared HTTP client (for tunnel mode)
# ---------------------------------------------------------------------------

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Lazy singleton — avoids creating the client at import time."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=httpx.Timeout(MCP_TIMEOUT))
    return _http_client


# ═══════════════════════════════════════════════════════════════════════════
# USB MODE — pymobiledevice3 tunnel
# ═══════════════════════════════════════════════════════════════════════════

async def _get_usb_tunnel_port(udid: str) -> int | None:
    """Get or create a TCP tunnel to the USB agent on the iPhone."""
    if not _PYMOBILE_AVAILABLE:
        return None

    if udid in _tunnel_cache:
        port, created = _tunnel_cache[udid]
        age = (datetime.now(UTC) - created).total_seconds()
        if age < _TUNNEL_TTL:
            return port

    try:
        loop = asyncio.get_event_loop()
        port = await asyncio.wait_for(
            loop.run_in_executor(None, _create_usb_tunnel, udid),
            timeout=TUNNEL_TIMEOUT,
        )
        if port:
            _tunnel_cache[udid] = (port, datetime.now(UTC))
        return port
    except asyncio.TimeoutError:
        logger.warning("USB tunnel timeout for device %s", udid)
        return None
    except Exception as e:
        logger.warning("USB tunnel error for device %s: %s", udid, e)
        return None


def _create_usb_tunnel(udid: str) -> int | None:
    """Blocking: create a TCP forwarder for the given UDID."""
    try:
        forwarder = UsbmuxTcpForwarder(
            serial=udid,
            dst_port=AGENT_PORT,
            src_port=0,
        )
        forwarder.start()
        return forwarder.local_port
    except Exception as e:
        logger.warning("Failed to create USB tunnel to %s: %s", udid, e)
        return None


async def _usb_raw_request(
    udid: str,
    method: str,
    path: str,
    body: bytes | None = None,
    timeout: float = COMMAND_TIMEOUT,
) -> tuple[bool, str, dict | None]:
    """Send a raw HTTP request to the USB agent."""
    port = await _get_usb_tunnel_port(udid)
    if port is None:
        return False, "Cannot establish USB tunnel — device offline or agent not installed", None

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port),
            timeout=5,
        )
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
        _tunnel_cache.pop(udid, None)
        return False, f"Agent not reachable on device: {e}", None

    try:
        content_headers = ""
        if body:
            content_headers = (
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
            )
        else:
            if method == "POST":
                content_headers = "Content-Length: 0\r\n"

        req = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"{content_headers}"
            f"\r\n"
        ).encode()
        if body:
            req += body

        writer.write(req)
        await writer.drain()

        response_data = await asyncio.wait_for(
            reader.read(8192),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()

        return _parse_http_response(response_data)

    except asyncio.TimeoutError:
        writer.close()
        return False, f"Command timed out after {timeout}s", None
    except Exception as e:
        try:
            writer.close()
        except Exception:
            pass
        return False, f"Dispatch error: {e}", None


def _parse_http_response(data: bytes) -> tuple[bool, str, dict | None]:
    """Parse a raw HTTP response from the on-device agent."""
    try:
        text = data.decode("utf-8", errors="replace")
        parts = text.split("\r\n\r\n", 1)
        if len(parts) < 2:
            return False, "Invalid response from agent", None

        status_line = parts[0].split("\r\n")[0]
        body = parts[1]

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


# ═══════════════════════════════════════════════════════════════════════════
# TUNNEL MODE — direct HTTP to MCP / crane-controller
# ═══════════════════════════════════════════════════════════════════════════

async def mcp_call(
    mcp_port: int,
    method: str,
    params: dict | None = None,
    *,
    timeout: float = MCP_TIMEOUT,
    host: str = "127.0.0.1",
) -> dict | None:
    """Send a JSON-RPC call to the MCP server exposed via SSH tunnel.

    Returns the result dict on success, None on failure.
    """
    url = f"http://{host}:{mcp_port}/mcp"
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1,
    }
    try:
        client = _get_http_client()
        resp = await asyncio.wait_for(
            client.post(url, json=payload),
            timeout=timeout,
        )
        data = resp.json()
        if "error" in data:
            logger.warning("MCP error on %s: %s", method, data["error"])
            return None
        return data.get("result")
    except asyncio.TimeoutError:
        logger.warning("MCP timeout on %s (port %d)", method, mcp_port)
        return None
    except Exception as e:
        logger.warning("MCP call failed (%s port %d): %s", method, mcp_port, e)
        return None


async def crane_call(
    crane_port: int,
    path: str,
    payload: dict | None = None,
    *,
    host: str = "127.0.0.1",
) -> dict | None:
    """HTTP call to crane-controller exposed via SSH tunnel.

    GET if payload is None, POST otherwise.
    """
    url = f"http://{host}:{crane_port}{path}"
    try:
        client = _get_http_client()
        if payload is not None:
            resp = await asyncio.wait_for(
                client.post(url, json=payload),
                timeout=CRANE_TIMEOUT,
            )
        else:
            resp = await asyncio.wait_for(
                client.get(url),
                timeout=CRANE_TIMEOUT,
            )
        if resp.status_code >= 400:
            logger.warning("Crane %s returned %d", path, resp.status_code)
            return None
        return resp.json()
    except Exception as e:
        logger.warning("Crane call failed (%s): %s", path, e)
        return None


async def tunnel_probe(
    mcp_port: int = DEFAULT_MCP_PORT,
    crane_port: int = DEFAULT_CRANE_PORT,
    host: str = "127.0.0.1",
) -> dict:
    """Probe MCP + crane endpoints to check if the tunnel is alive.

    Returns a dict suitable for TunnelProbeResult.
    """
    result = {
        "reachable": False,
        "mcp_port": mcp_port,
        "crane_port": crane_port,
        "mcp_ok": False,
        "crane_ok": False,
        "containers": None,
        "error": None,
    }

    # Probe MCP
    mcp_result = await mcp_call(mcp_port, "get_ui_elements", host=host)
    result["mcp_ok"] = mcp_result is not None

    # Probe crane
    crane_result = await crane_call(crane_port, "/inventory", host=host)
    result["crane_ok"] = crane_result is not None
    if crane_result:
        result["containers"] = crane_result.get("containers") or crane_result.get("data")

    result["reachable"] = result["mcp_ok"] or result["crane_ok"]
    if not result["reachable"]:
        result["error"] = f"Neither MCP (:{mcp_port}) nor crane (:{crane_port}) reachable"

    return result


# ═══════════════════════════════════════════════════════════════════════════
# UNIFIED DISPATCH API
# ═══════════════════════════════════════════════════════════════════════════

async def dispatch_command(
    udid: str,
    command: dict[str, Any],
    *,
    connection_type: str = "usb",
    mcp_port: int | None = None,
    crane_port: int | None = None,
    timeout: float = COMMAND_TIMEOUT,
) -> tuple[bool, str, dict | None]:
    """Send a command to the on-device agent.

    Dispatches via USB tunnel (pymobiledevice3) or network tunnel (MCP HTTP)
    depending on connection_type.

    Args:
        udid: Device UDID
        command: Command payload
        connection_type: "usb" or "tunnel"
        mcp_port: MCP port (tunnel mode only)
        crane_port: crane-controller port (tunnel mode only)
        timeout: Max seconds to wait

    Returns:
        (success: bool, message: str, result: dict | None)
    """
    if connection_type == "tunnel":
        return await _dispatch_tunnel(
            command,
            mcp_port=mcp_port or DEFAULT_MCP_PORT,
            crane_port=crane_port or DEFAULT_CRANE_PORT,
            timeout=timeout,
        )
    else:
        # USB mode — original behavior
        payload = json.dumps(command).encode()
        return await _usb_raw_request(udid, "POST", "/execute", payload, timeout)


async def _dispatch_tunnel(
    command: dict[str, Any],
    *,
    mcp_port: int,
    crane_port: int,
    timeout: float,
) -> tuple[bool, str, dict | None]:
    """Dispatch a command via the MCP tunnel.

    The MCP server on the iPhone runs the iOS automation directly.
    The command is translated to MCP JSON-RPC calls.
    """
    action = command.get("action", "")

    # For now, forward the entire command as an "execute" MCP call.
    # The on-device MCP server handles the routing internally.
    result = await mcp_call(
        mcp_port,
        "execute",
        params=command,
        timeout=timeout,
    )

    if result is not None:
        msg = result.get("message", "OK") if isinstance(result, dict) else "OK"
        return True, msg, result if isinstance(result, dict) else {"result": result}
    else:
        return False, "MCP execute failed — tunnel unreachable or action error", None


async def check_agent_status(
    udid: str,
    *,
    connection_type: str = "usb",
    mcp_port: int | None = None,
    crane_port: int | None = None,
) -> dict | None:
    """Check if the agent is running and get its status.

    Returns a status dict or None if unreachable.
    """
    if connection_type == "tunnel":
        # Probe both MCP and crane
        probe = await tunnel_probe(
            mcp_port=mcp_port or DEFAULT_MCP_PORT,
            crane_port=crane_port or DEFAULT_CRANE_PORT,
        )
        if probe["reachable"]:
            return {
                "connection_type": "tunnel",
                "mcp_ok": probe["mcp_ok"],
                "crane_ok": probe["crane_ok"],
                "containers": probe.get("containers"),
            }
        return None
    else:
        # USB mode
        ok, msg, result = await _usb_raw_request(udid, "GET", "/status", timeout=5)
        return result if ok else None


async def abort_action(
    udid: str,
    *,
    connection_type: str = "usb",
    mcp_port: int | None = None,
) -> bool:
    """Tell the agent to abort the current action."""
    if connection_type == "tunnel":
        result = await mcp_call(
            mcp_port or DEFAULT_MCP_PORT,
            "abort",
            timeout=5,
        )
        return result is not None
    else:
        ok, _, _ = await _usb_raw_request(udid, "POST", "/abort", timeout=5)
        return ok


# ═══════════════════════════════════════════════════════════════════════════
# CRANE-CONTROLLER helpers (tunnel mode)
# ═══════════════════════════════════════════════════════════════════════════

async def switch_container(
    crane_port: int,
    container_uuid: str,
    bundle: str = "com.burbn.instagram",
) -> bool:
    """Switch the iPhone to a specific container via crane-controller.

    This is the equivalent of VPS iphone_device.py's switch_container().
    """
    # First verify the container exists in inventory
    inventory = await crane_call(crane_port, "/inventory")
    if inventory is None:
        logger.warning("Cannot get crane inventory on port %d", crane_port)
        return False

    containers = inventory.get("containers") or inventory.get("data") or []
    found = any(
        c.get("uuid") == container_uuid or c.get("id") == container_uuid
        for c in containers
        if isinstance(c, dict)
    )
    if not found:
        logger.warning(
            "Container %s not found in inventory (port %d, %d containers)",
            container_uuid, crane_port, len(containers),
        )
        return False

    # Switch
    result = await crane_call(
        crane_port,
        "/sequence",
        payload={"uuid": container_uuid, "bundle": bundle},
    )
    if result is None:
        logger.warning("Container switch failed for %s", container_uuid)
        return False

    logger.info("Switched to container %s on crane :%d", container_uuid, crane_port)
    return True


async def kill_app(
    crane_port: int,
    bundle: str = "com.burbn.instagram",
) -> bool:
    """Kill an app via crane-controller."""
    result = await crane_call(crane_port, "/kill", payload={"bundle": bundle})
    return result is not None


async def list_containers(crane_port: int) -> list[dict]:
    """List all containers from crane-controller."""
    result = await crane_call(crane_port, "/inventory")
    if result is None:
        return []
    return result.get("containers") or result.get("data") or []
