"""Async DeviceSession — context manager for iPhone automation tasks.

Ported from VPS iphone_device.py. Handles:
  - Per-device asyncio lock (one task at a time per physical iPhone)
  - Account → device + container resolution from PostgreSQL
  - Container switch via ScaleTweak (SSH → scalectl on iPhone)
  - Lock screen detection via MCP
  - App kill on exit (SSH → killall)
  - Auto-login dispatch

Usage:
    async with DeviceSession(compte_id, BUNDLE_INSTAGRAM) as sess:
        drv = IGDriver(mcp_port=sess.mcp_port, log=sess.log)
        ...
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import UUID

from app.db import AsyncSessionLocal
from app.models.compte import Compte
from app.models.iphone import IPhone
from app.services.dispatch import (
    mcp_call,
    scalectl_kill_app,
    scalectl_list_containers,
    scalectl_switch_container,
)

logger = logging.getLogger("automation.device")

# ── Constants ────────────────────────────────────────────────────────────────

BUNDLE_THREADS = "com.burbn.barcelona"
BUNDLE_INSTAGRAM = "com.burbn.instagram"

DEFAULT_MCP_PORT = 8190
DEFAULT_SSH_PORT = 2222

# Lock screen markers (iOS FR locale)
_LOCK_MARKERS = ("lampe torche", "appareil photo", "afficher les notifications")

# ── Per-device locks ─────────────────────────────────────────────────────────
# One asyncio.Lock per device_id, shared across all runners in the process.
# Two tasks on the same iPhone wait for each other, even if one is IG and
# the other is Threads.

_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


async def _device_lock(device_id: str) -> asyncio.Lock:
    """Get or create the per-device asyncio lock."""
    async with _locks_guard:
        if device_id not in _locks:
            _locks[device_id] = asyncio.Lock()
        return _locks[device_id]


# ── Exceptions ───────────────────────────────────────────────────────────────

class DeviceLocked(RuntimeError):
    """Device screen is locked — no UI automation possible."""


class ContainerNotFound(RuntimeError):
    """Target container UUID not found on device."""


class LoginRequired(RuntimeError):
    """Account not logged in and login failed or impossible."""


class DeviceUnavailable(RuntimeError):
    """Device not found, inactive, or unreachable."""


# ── Account resolution ───────────────────────────────────────────────────────

async def resolve_account_device(
    compte_id: UUID,
    log: Callable = logger.info,
) -> dict[str, Any]:
    """Resolve account → device + container from PostgreSQL.

    Returns a context dict with:
        device_id, device_label, container_uuid, username,
        mcp_port, ssh_port, mcp_url, connection_type
    """
    async with AsyncSessionLocal() as db:
        compte = await db.get(Compte, compte_id)
        if not compte:
            raise DeviceUnavailable(f"Compte {compte_id} introuvable")

        if not compte.device_id:
            raise DeviceUnavailable(
                f"Compte {compte.handle} n'a pas d'iPhone assigné — "
                "associe-le via l'interface Comptes"
            )

        # Load the iPhone
        try:
            device_uid = UUID(compte.device_id)
        except (ValueError, TypeError):
            raise DeviceUnavailable(
                f"device_id invalide pour {compte.handle}: {compte.device_id}"
            )

        iphone = await db.get(IPhone, device_uid)
        if not iphone:
            raise DeviceUnavailable(
                f"iPhone {compte.device_id} introuvable en base"
            )

        if iphone.status not in ("online", None):
            log(f"   [device] iPhone '{iphone.name}' status={iphone.status}")

        # Container UUID from env JSONB
        env = compte.env or {}
        container_uuid = (
            env.get("container_uuid")
            or env.get("iphone", {}).get("id")
            or env.get("env_id")
            or ""
        )
        if not container_uuid:
            raise DeviceUnavailable(
                f"Compte {compte.handle} sans container UUID — "
                "associe un container via POST /comptes/{id} avec env.container_uuid"
            )

        conn_type = iphone.connection_type or "usb"
        mcp_port = iphone.mcp_port or DEFAULT_MCP_PORT
        ssh_port = iphone.ssh_port or DEFAULT_SSH_PORT

        return {
            "device_id": str(iphone.id),
            "device_label": iphone.name,
            "container_uuid": container_uuid,
            "username": compte.handle,
            "compte_id": str(compte.id),
            "connection_type": conn_type,
            "mcp_port": mcp_port,
            "ssh_port": ssh_port,
            "mcp_url": f"http://127.0.0.1:{mcp_port}/mcp",
        }


# ── Lock screen detection ────────────────────────────────────────────────────

async def _probe_ui(mcp_port: int) -> list[dict] | None:
    """Quick MCP probe — returns UI elements or None if unreachable."""
    result = await mcp_call(
        mcp_port,
        "tools/call",
        params={"name": "get_ui_elements", "arguments": {"clickable_only": False, "max_elements": 25}},
        timeout=8,
    )
    if result is None:
        return None
    try:
        content = result.get("content", [{}])
        if content and isinstance(content, list):
            import json
            raw = content[0].get("text", "")
            return json.loads(raw).get("elements", [])
    except Exception:
        pass
    return None


async def is_device_locked(mcp_port: int, log: Callable = logger.info) -> bool:
    """True if device screen is locked OR MCP is unreachable."""
    els = await _probe_ui(mcp_port)
    if els is None:
        log("   [device] MCP muet → appareil verrouillé, en veille ou injoignable")
        return True
    texts = " ".join((e.get("text") or "").lower() for e in els)
    hits = [m for m in _LOCK_MARKERS if m in texts]
    if len(hits) >= 2:
        log(f"   [device] écran verrouillé détecté ({', '.join(hits)})")
        return True
    return False


# ── Container switch ─────────────────────────────────────────────────────────

async def switch_device_container(
    ctx: dict,
    bundle: str,
    log: Callable = logger.info,
) -> bool:
    """Switch to the account's container via ScaleTweak (SSH → scalectl).

    Verifies the UUID exists in the plist BEFORE switching to avoid
    operating on the wrong container.
    """
    uuid = ctx["container_uuid"]
    ssh_port = ctx["ssh_port"]

    # Get container list from plist
    containers = await scalectl_list_containers(ssh_port, bundle)
    if not containers:
        raise ContainerNotFound(
            f"Aucun container sur {ctx['device_label']} — "
            "scalectl injoignable ou plist vide"
        )

    # Verify container exists
    known_uuids = {c["uuid"] for c in containers}
    if uuid not in known_uuids:
        raise ContainerNotFound(
            f"Container {uuid} introuvable sur {ctx['device_label']} "
            f"({len(known_uuids)} containers connus)"
        )

    # Check if already active
    active = next((c for c in containers if c.get("active")), None)
    if active and active["uuid"] == uuid:
        log(f"   [scalectl] container {uuid[:8]} déjà actif, skip switch")
        return True

    log(f"   [scalectl] bascule {ctx.get('username', ctx['device_id'])} → {uuid[:8]} ({bundle})")

    ok = await scalectl_switch_container(ssh_port, uuid, bundle)
    if not ok:
        raise RuntimeError(f"Bascule container KO pour {uuid}")

    return True


# ── DeviceSession ────────────────────────────────────────────────────────────

class DeviceSession:
    """Async context manager for iPhone automation tasks.

    Takes the per-device lock, switches to the right container,
    and releases everything on exit (including app kill).

    Usage:
        async with DeviceSession(compte_id, BUNDLE_INSTAGRAM) as sess:
            drv = IGDriver(mcp_port=sess.mcp_port)
            await sess.ensure_login(drv, nav)
            ...
    """

    def __init__(
        self,
        compte_id: UUID | str,
        bundle: str,
        *,
        log: Callable = logger.info,
        switch: bool = True,
        lock_timeout: float = 900,
        kill_on_exit: bool = True,
    ):
        self.compte_id = UUID(str(compte_id))
        self.bundle = bundle
        self.log = log
        self.switch = switch
        self.lock_timeout = lock_timeout
        self.kill_on_exit = kill_on_exit
        self.ctx: dict[str, Any] | None = None
        self._lock: asyncio.Lock | None = None
        self._lock_acquired = False

    async def __aenter__(self) -> "DeviceSession":
        # Resolve account → device
        self.ctx = await resolve_account_device(self.compte_id, log=self.log)

        # Acquire per-device lock
        self._lock = await _device_lock(self.ctx["device_id"])
        try:
            self._lock_acquired = await asyncio.wait_for(
                self._lock.acquire(),
                timeout=self.lock_timeout,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"iPhone {self.ctx['device_label']} occupé depuis plus de "
                f"{self.lock_timeout}s — une autre tâche est en cours"
            )

        try:
            # Check lock screen before switching (avoids 45s hang on uiopen)
            if await is_device_locked(self.ctx["mcp_port"], self.log):
                raise DeviceLocked(
                    f"iPhone {self.ctx['device_label']} verrouillé — "
                    "déverrouille-le et mets Verrouillage automatique sur Jamais"
                )

            # Switch container
            if self.switch:
                await switch_device_container(self.ctx, self.bundle, self.log)

        except Exception:
            # Release lock on any setup failure
            if self._lock_acquired:
                self._lock.release()
                self._lock_acquired = False
            raise

        return self

    async def __aexit__(self, exc_type, exc, tb):
        # Kill app before releasing lock
        if self.ctx and self.kill_on_exit:
            try:
                await scalectl_kill_app(self.ctx["ssh_port"], self.bundle)
            except Exception as e:
                self.log(f"   [scalectl] kill KO: {str(e)[:80]}")

        # Release lock
        if self._lock_acquired and self._lock:
            try:
                self._lock.release()
            except RuntimeError:
                pass
            self._lock_acquired = False

        return False

    async def ensure_login(self, drv, nav):
        """Connect the account if not already logged in.

        Call this right after constructing the driver, before any action.
        Raises LoginRequired if login fails.
        """
        if self.bundle == BUNDLE_THREADS:
            return await self._ensure_login_threads(drv, nav)
        elif self.bundle == BUNDLE_INSTAGRAM:
            return await self._ensure_login_instagram(drv, nav)
        return False

    async def _ensure_login_threads(self, drv, nav):
        """Check and login Threads if needed."""
        # Will be implemented when th_iphone interaction modules are ported
        self.log("   [login] Threads login check — stub")
        return False

    async def _ensure_login_instagram(self, drv, nav):
        """Check and login Instagram if needed."""
        # Will be implemented when ig_iphone auth modules are ported
        self.log("   [login] Instagram login check — stub")
        return False

    # ── Convenience properties ─────────────────────────────────────────

    @property
    def mcp_port(self) -> int:
        return self.ctx["mcp_port"] if self.ctx else DEFAULT_MCP_PORT

    @property
    def ssh_port(self) -> int:
        return self.ctx["ssh_port"] if self.ctx else DEFAULT_SSH_PORT

    @property
    def mcp_url(self) -> str:
        return self.ctx["mcp_url"] if self.ctx else f"http://127.0.0.1:{DEFAULT_MCP_PORT}/mcp"

    @property
    def device_id(self) -> str:
        return self.ctx["device_id"] if self.ctx else ""

    @property
    def device_label(self) -> str:
        return self.ctx.get("device_label", "") if self.ctx else ""

    @property
    def username(self) -> str:
        return self.ctx.get("username", "") if self.ctx else ""

    @property
    def container_uuid(self) -> str:
        return self.ctx.get("container_uuid", "") if self.ctx else ""

    @property
    def connection_type(self) -> str:
        return self.ctx.get("connection_type", "tunnel") if self.ctx else "tunnel"
