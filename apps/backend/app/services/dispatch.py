"""iPhone command dispatch — dual mode USB + network tunnel.

Two connection modes:

  USB (legacy):
    VPS ──USB──> iPhone (jailbroken, agent on port 8765)
    Uses pymobiledevice3 UsbmuxTcpForwarder to create a local TCP port.

  Tunnel (network):
    iPhone ──reverse-SSH──> VPS (MCP on 127.0.0.1:<mcp_port>, SSH on 127.0.0.1:<ssh_port>)
    Direct HTTP to the MCP JSON-RPC server exposed by the SSH tunnel.
    Container management via SSH → scalectl CLI on the iPhone.
    No pymobiledevice3 needed — the ports are already forwarded.

The on-device MCP agent (iOS accessibility driver) exposes:
  POST /mcp          — JSON-RPC (get_ui_elements, perform_action, etc.)
The on-device scale-agent (USB mode) exposes:
  POST /execute      — run a command
  GET  /status       — health check
  POST /abort        — cancel current action

ScaleTweak (tunnel mode) — container management via SSH:
  scalectl --list <bundle>                         — list containers
  scalectl --switch <bundle> <uuid|name:N|default> — switch active container
  scalectl --create <bundle> <name> [country] [persona] — create container
  scalectl --delete <bundle> <uuid>                — delete container
  scalectl --inject <bundle> <uuid> <file.json>    — inject session/fingerprint
  scalectl --status                                — global status

The engine decides which path to take based on iPhone.connection_type.
"""

import asyncio
import json
import logging
import plistlib
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger("dispatch")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# USB agent port on the iPhone
AGENT_PORT = 8765
# Default MCP / SSH ports for tunnel mode (overridden per device)
DEFAULT_MCP_PORT = 8190
DEFAULT_SSH_PORT = 2222

# Timeouts (seconds)
COMMAND_TIMEOUT = 30
TUNNEL_TIMEOUT = 10
MCP_TIMEOUT = 60       # MCP actions can be slow (UI automation)
SSH_TIMEOUT = 15        # scalectl commands are fast

# ScaleTweak plist path on the iPhone
SCALE_PLIST_PATH = "/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist"

# Bundle → process name mapping (for killall)
BUNDLE_TO_PROCESS = {
    "com.burbn.instagram": "Instagram",
    "com.burbn.barcelona": "Barcelona",
}

# Bundle → URL scheme mapping (for uiopen after kill)
BUNDLE_TO_URL_SCHEME = {
    "com.burbn.instagram": "instagram://",
    "com.burbn.barcelona": "barcelona://",
}

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
# Shared HTTP client (for MCP tunnel mode)
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
# TUNNEL MODE — MCP via HTTP
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


# ═══════════════════════════════════════════════════════════════════════════
# SSH EXECUTION — run commands on iPhone via reverse SSH tunnel
# ═══════════════════════════════════════════════════════════════════════════

async def _ssh_exec(
    ssh_port: int,
    command: str,
    *,
    timeout: float = SSH_TIMEOUT,
    host: str = "127.0.0.1",
    user: str = "root",
    binary: bool = False,
) -> tuple[bool, str | bytes]:
    """Execute a command on iPhone via SSH tunnel.

    Args:
        ssh_port: Local port forwarded to iPhone's SSH (via reverse tunnel)
        command: Shell command to execute on iPhone
        timeout: Max seconds to wait
        host: SSH host (default 127.0.0.1 — reverse tunnel)
        user: SSH user on iPhone (default root)
        binary: If True, return raw stdout bytes instead of decoded string

    Returns:
        (success: bool, output: str | bytes)
    """
    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=5",
                "-o", "BatchMode=yes",
                "-o", "LogLevel=ERROR",
                "-p", str(ssh_port),
                f"{user}@{host}",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=timeout,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

        if proc.returncode == 0:
            return True, stdout if binary else stdout.decode("utf-8", errors="replace").strip()
        else:
            err = stderr.decode("utf-8", errors="replace").strip()
            out = stdout.decode("utf-8", errors="replace").strip()
            return False, err or out or f"SSH exit code {proc.returncode}"

    except asyncio.TimeoutError:
        return False, f"SSH timeout ({timeout}s)"
    except FileNotFoundError:
        return False, "ssh binary not found on VPS"
    except Exception as e:
        return False, f"SSH error: {e}"


async def _ssh_check(
    ssh_port: int,
    *,
    host: str = "127.0.0.1",
) -> bool:
    """Quick SSH connectivity check."""
    ok, _ = await _ssh_exec(ssh_port, "echo ok", timeout=5, host=host)
    return ok


# ═══════════════════════════════════════════════════════════════════════════
# SCALECTL — container management via SSH → scalectl on iPhone
# ═══════════════════════════════════════════════════════════════════════════

async def scalectl_list_containers(
    ssh_port: int,
    bundle: str = "com.burbn.instagram",
    *,
    host: str = "127.0.0.1",
) -> list[dict]:
    """List all containers for a bundle by reading the ScaleTweak plist.

    Reads the plist directly (binary or XML) for full UUID fidelity,
    since scalectl --list truncates UUIDs to 8 chars in its output.
    """
    # Read plist as binary data via SSH
    ok, raw = await _ssh_exec(
        ssh_port,
        f"cat {SCALE_PLIST_PATH}",
        binary=True,
        host=host,
        timeout=10,
    )
    if not ok:
        err = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        logger.warning("scalectl list: cannot read plist: %s", err)
        return []

    try:
        raw_bytes = raw if isinstance(raw, bytes) else raw.encode()
        config = plistlib.loads(raw_bytes)
    except Exception as e:
        logger.warning("scalectl list: plist parse error: %s", e)
        return []

    app_config = config.get(bundle, {})
    if not isinstance(app_config, dict):
        return []

    containers_map = app_config.get("containers", {})
    active_uuid = app_config.get("active", "")

    result = []
    for uuid, meta in containers_map.items():
        if not isinstance(meta, dict):
            continue
        entry = {
            "uuid": uuid,
            "name": meta.get("name", ""),
            "active": uuid == active_uuid,
        }
        # Include geo/carrier metadata if present
        for key in ("country", "carrier", "timezone", "locale", "mcc", "mnc", "device_name"):
            if key in meta:
                entry[key] = meta[key]
        # Include proxy config if present
        if "proxy" in meta:
            entry["proxy"] = meta["proxy"]
        result.append(entry)

    return result


async def scalectl_switch_container(
    ssh_port: int,
    container_uuid: str,
    bundle: str = "com.burbn.instagram",
    *,
    host: str = "127.0.0.1",
    relaunch: bool = True,
    relaunch_delay: float = 2.0,
) -> bool:
    """Switch the iPhone to a specific container via scalectl.

    Flow:
      1. scalectl --switch <bundle> <uuid>  → writes new active UUID to plist
      2. killall <process>                   → force-close the app
      3. uiopen <url-scheme>                 → relaunch (Tweak.x picks up new UUID)
      4. Wait for app startup
    """
    # Step 1: scalectl --switch
    ok, output = await _ssh_exec(
        ssh_port,
        f"scalectl --switch {bundle} {container_uuid}",
        host=host,
    )
    if not ok:
        logger.warning("scalectl switch failed: %s", output)
        return False

    if "Not found" in str(output):
        logger.warning("scalectl switch: container %s not found", container_uuid)
        return False

    logger.info("scalectl: switched %s → %s", bundle, container_uuid)

    if not relaunch:
        return True

    # Step 2: Kill the app
    process_name = BUNDLE_TO_PROCESS.get(bundle)
    if process_name:
        await _ssh_exec(ssh_port, f"killall -9 {process_name}", host=host, timeout=5)
        await asyncio.sleep(0.5)

    # Step 3: Relaunch via uiopen
    url_scheme = BUNDLE_TO_URL_SCHEME.get(bundle)
    if url_scheme:
        await _ssh_exec(ssh_port, f"uiopen '{url_scheme}'", host=host, timeout=5)

    # Step 4: Wait for app startup + Tweak.x constructor
    await asyncio.sleep(relaunch_delay)

    return True


async def scalectl_kill_app(
    ssh_port: int,
    bundle: str = "com.burbn.instagram",
    *,
    host: str = "127.0.0.1",
) -> bool:
    """Kill an app on the iPhone via SSH."""
    process_name = BUNDLE_TO_PROCESS.get(bundle)
    if not process_name:
        logger.warning("Unknown bundle for kill: %s", bundle)
        return False

    ok, output = await _ssh_exec(
        ssh_port,
        f"killall -9 {process_name}",
        host=host,
        timeout=5,
    )
    # killall returns 1 if process not found — that's OK (already dead)
    if not ok and "No matching processes" not in str(output):
        logger.warning("kill_app failed for %s: %s", process_name, output)
    return True


async def scalectl_create_container(
    ssh_port: int,
    bundle: str,
    name: str,
    country: str = "FR",
    persona: str | None = None,
    *,
    host: str = "127.0.0.1",
) -> str | None:
    """Create a new container via scalectl.

    Returns the container UUID on success, None on failure.
    """
    cmd = f"scalectl --create {bundle} '{name}' {country}"
    if persona:
        cmd += f" '{persona}'"

    ok, output = await _ssh_exec(ssh_port, cmd, host=host)
    if not ok:
        logger.warning("scalectl create failed: %s", output)
        return None

    # Parse output: "Created: <name> -> <uuid_8chars>"
    # We need the full UUID — re-read plist to find it by name
    containers = await scalectl_list_containers(ssh_port, bundle, host=host)
    for c in containers:
        if c.get("name") == name:
            return c["uuid"]

    logger.warning("scalectl create: container '%s' not found after creation", name)
    return None


async def scalectl_delete_container(
    ssh_port: int,
    bundle: str,
    container_uuid: str,
    *,
    host: str = "127.0.0.1",
) -> bool:
    """Delete a container via scalectl."""
    ok, output = await _ssh_exec(
        ssh_port,
        f"scalectl --delete {bundle} {container_uuid}",
        host=host,
    )
    if not ok:
        logger.warning("scalectl delete failed: %s", output)
        return False
    return True


async def scalectl_inject_session(
    ssh_port: int,
    bundle: str,
    container_uuid: str,
    session_data: dict,
    *,
    host: str = "127.0.0.1",
) -> bool:
    """Inject session cookies + fingerprint into a container.

    Writes a temporary JSON file on the iPhone, runs scalectl --inject,
    then cleans up the temp file.

    session_data should contain:
      {
        "session": {"sessionid": "...", "csrftoken": "...", "ds_user_id": "...", "mid": "...", "ig_did": "..."},
        "fingerprint": {"device_id": "...", "family_device_id": "...", "user_agent": "..."},
        "proxy": "http://user:pass@host:port"  (optional)
      }
    """
    json_str = json.dumps(session_data)
    tmp_path = f"/tmp/scale_inject_{container_uuid[:8]}.json"

    # Write JSON to temp file on iPhone
    # Escape single quotes in JSON for shell safety
    escaped = json_str.replace("'", "'\\''")
    ok, _ = await _ssh_exec(
        ssh_port,
        f"echo '{escaped}' > {tmp_path}",
        host=host,
    )
    if not ok:
        logger.warning("scalectl inject: failed to write temp JSON")
        return False

    # Run scalectl --inject
    ok, output = await _ssh_exec(
        ssh_port,
        f"scalectl --inject {bundle} {container_uuid} {tmp_path}",
        host=host,
        timeout=10,
    )

    # Cleanup temp file
    await _ssh_exec(ssh_port, f"rm -f {tmp_path}", host=host, timeout=5)

    if not ok:
        logger.warning("scalectl inject failed: %s", output)
        return False

    logger.info("scalectl: injected session into %s/%s", bundle, container_uuid[:8])
    return True


async def scalectl_status(
    ssh_port: int,
    *,
    host: str = "127.0.0.1",
) -> dict | None:
    """Get scalectl global status."""
    ok, output = await _ssh_exec(ssh_port, "scalectl --status", host=host)
    if not ok:
        return None
    # Parse text output into a dict
    result: dict[str, Any] = {"raw": output}
    for line in output.split("\n"):
        line = line.strip()
        if ":" in line and "containers" in line:
            parts = line.split(":")
            if len(parts) >= 2:
                app_id = parts[0].strip()
                result[app_id] = parts[1].strip()
    return result


# ═══════════════════════════════════════════════════════════════════════════
# TUNNEL PROBE — check MCP + SSH connectivity
# ═══════════════════════════════════════════════════════════════════════════

async def tunnel_probe(
    mcp_port: int = DEFAULT_MCP_PORT,
    ssh_port: int = DEFAULT_SSH_PORT,
    host: str = "127.0.0.1",
) -> dict:
    """Probe MCP + SSH endpoints to check if the tunnel is alive.

    Returns a dict suitable for TunnelProbeResult.
    """
    result = {
        "reachable": False,
        "mcp_port": mcp_port,
        "ssh_port": ssh_port,
        "mcp_ok": False,
        "ssh_ok": False,
        "containers": None,
        "error": None,
    }

    # Probe MCP
    mcp_result = await mcp_call(mcp_port, "get_ui_elements", host=host)
    result["mcp_ok"] = mcp_result is not None

    # Probe SSH + scalectl
    ssh_ok = await _ssh_check(ssh_port, host=host)
    result["ssh_ok"] = ssh_ok
    if ssh_ok:
        containers = await scalectl_list_containers(ssh_port, host=host)
        result["containers"] = containers

    result["reachable"] = result["mcp_ok"] or result["ssh_ok"]
    if not result["reachable"]:
        result["error"] = f"Neither MCP (:{mcp_port}) nor SSH (:{ssh_port}) reachable"

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
    ssh_port: int | None = None,
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
        ssh_port: SSH port (tunnel mode only)
        timeout: Max seconds to wait

    Returns:
        (success: bool, message: str, result: dict | None)
    """
    if connection_type == "tunnel":
        return await _dispatch_tunnel(
            command,
            mcp_port=mcp_port or DEFAULT_MCP_PORT,
            ssh_port=ssh_port or DEFAULT_SSH_PORT,
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
    ssh_port: int,
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
    ssh_port: int | None = None,
) -> dict | None:
    """Check if the agent is running and get its status.

    Returns a status dict or None if unreachable.
    """
    if connection_type == "tunnel":
        # Probe both MCP and SSH
        probe = await tunnel_probe(
            mcp_port=mcp_port or DEFAULT_MCP_PORT,
            ssh_port=ssh_port or DEFAULT_SSH_PORT,
        )
        if probe["reachable"]:
            return {
                "connection_type": "tunnel",
                "mcp_ok": probe["mcp_ok"],
                "ssh_ok": probe["ssh_ok"],
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
