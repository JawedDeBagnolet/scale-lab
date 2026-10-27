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
import json
import logging
import random
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
    scalectl_inject_session,
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

        Args:
            drv: IGDriver (or ThDriver for Threads)
            nav: unused legacy arg, kept for compat
        """
        if self.bundle == BUNDLE_THREADS:
            return await self._ensure_login_threads(drv, nav)
        elif self.bundle == BUNDLE_INSTAGRAM:
            return await self._ensure_login_instagram(drv, nav)
        return False

    async def _ensure_login_threads(self, drv, nav):
        """Check and login Threads if needed.

        Threads uses the same Instagram credentials — the flow is similar
        but the app UI is different. For now, we check screen state and
        attempt login if needed.
        """
        self.log("   [login] Threads login check")
        screen = await drv.detect_current_screen()

        if screen == "login":
            self.log("   [login] Threads: écran de login détecté, tentative...")
            return await self._do_ig_login(drv)

        self.log(f"   [login] Threads: pas sur l'écran de login (screen={screen})")
        return True

    async def _ensure_login_instagram(self, drv, nav):
        """Check and login Instagram if needed.

        Flow:
          1. Detect current screen via MCP accessibility tree
          2. If on login screen → perform full login (username, password, 2FA)
          3. If on feed/profile/etc → already logged in
          4. If on checkpoint/error → raise LoginRequired
        """
        self.log("   [login] Instagram login check")

        # Wait for the app to settle after container switch + relaunch
        await asyncio.sleep(2.0)

        screen = await drv.detect_current_screen()
        self.log(f"   [login] écran détecté: {screen}")

        if screen in ("feed", "reels", "own_profile", "explore", "post_view", "story", "profile"):
            self.log("   [login] IG: déjà connecté")
            return True

        if screen == "login":
            self.log("   [login] IG: écran de login, tentative de connexion...")
            return await self._do_ig_login(drv)

        # Unknown screen — might be a loading state or an in-between screen
        # Wait a bit and retry
        self.log("   [login] IG: écran inconnu, attente 3s...")
        await asyncio.sleep(3.0)
        screen = await drv.detect_current_screen()
        self.log(f"   [login] écran après attente: {screen}")

        if screen in ("feed", "reels", "own_profile", "explore", "post_view", "story", "profile"):
            return True

        if screen == "login":
            return await self._do_ig_login(drv)

        # Still unknown — might be checkpoint, age verification, etc.
        # Check for known blockers
        await drv.refresh_elements()
        all_text = " ".join((e.get("text") or "").lower() for e in drv.elements)

        if any(kw in all_text for kw in ("vérifier", "confirmer", "checkpoint", "suspect")):
            raise LoginRequired(
                f"Checkpoint détecté sur {self.username} — intervention manuelle requise"
            )

        if any(kw in all_text for kw in ("suspendu", "suspended", "disabled", "désactivé")):
            raise LoginRequired(
                f"Compte {self.username} suspendu ou désactivé"
            )

        # Last resort: try tapping "Se connecter" / "Log In" if visible
        if screen == "other":
            tapped = await drv.tap_element("Se connecter", refresh=False)
            if not tapped:
                tapped = await drv.tap_element("Log In", refresh=False)
            if tapped:
                await asyncio.sleep(2.0)
                screen = await drv.detect_current_screen()
                if screen == "login":
                    return await self._do_ig_login(drv)
                elif screen in ("feed", "reels", "own_profile"):
                    return True

        raise LoginRequired(
            f"État inconnu pour {self.username} — écran: {screen}"
        )

    async def _do_ig_login(self, drv) -> bool:
        """Perform the actual Instagram login flow via MCP UI automation.

        Steps:
          1. Load credentials from DB (encrypted)
          2. Find and tap username field, type username
          3. Find and tap password field, type password
          4. Tap "Se connecter" / "Log In"
          5. Handle 2FA if prompted
          6. Verify we land on feed
        """
        # Load credentials
        creds = await self._load_credentials()
        if not creds:
            raise LoginRequired(
                f"Pas de credentials pour {self.username} — "
                "ajoute-les via PATCH /comptes/{id} avec creds_encrypted"
            )

        username = creds.get("username") or self.username
        password = creds.get("password")
        two_fa_code = creds.get("two_fa")

        if not password:
            raise LoginRequired(f"Mot de passe manquant pour {self.username}")

        self.log(f"   [login] connexion {username}...")

        # Step 1: tap username field
        await drv.refresh_elements()

        # Look for username input field
        username_field = (
            drv.find_element("nom d'utilisateur", contains=True)
            or drv.find_element("username", contains=True)
            or drv.find_element("téléphone", contains=True)
            or drv.find_element("e-mail", contains=True)
            or drv.find_element("numéro de téléphone", contains=True)
        )

        if username_field:
            x = username_field.get("x", 0)
            y = username_field.get("y", 0)
            w = username_field.get("width", 0)
            h = username_field.get("height", 0)
            await drv.ht.tap(x, y, bounds=(w, h) if w > 0 else None)
            await asyncio.sleep(0.5)
        else:
            # Fallback: tap at typical username field position (top area)
            self.log("   [login] champ username non trouvé, tap position par défaut")
            await drv.ht.tap_pos(0.5, 0.35)
            await asyncio.sleep(0.5)

        # Clear any existing text and type username
        await drv.ht.type_text(username, interval=random.randint(40, 90))
        await asyncio.sleep(0.3)

        # Step 2: tap password field
        await drv.refresh_elements()
        password_field = (
            drv.find_element("mot de passe", contains=True)
            or drv.find_element("password", contains=True)
        )

        if password_field:
            x = password_field.get("x", 0)
            y = password_field.get("y", 0)
            w = password_field.get("width", 0)
            h = password_field.get("height", 0)
            await drv.ht.tap(x, y, bounds=(w, h) if w > 0 else None)
            await asyncio.sleep(0.5)
        else:
            self.log("   [login] champ password non trouvé, tap position par défaut")
            await drv.ht.tap_pos(0.5, 0.45)
            await asyncio.sleep(0.5)

        await drv.ht.type_text(password, interval=random.randint(30, 70))
        await asyncio.sleep(0.3)

        # Step 3: tap login button
        tapped = (
            await drv.tap_element("Se connecter")
            or await drv.tap_element("Connexion")
            or await drv.tap_element("Log In")
            or await drv.tap_element("Log in")
        )

        if not tapped:
            self.log("   [login] bouton login non trouvé, tap position par défaut")
            await drv.ht.tap_pos(0.5, 0.60)

        # Wait for response (network round-trip)
        self.log("   [login] attente réponse serveur...")
        await asyncio.sleep(4.0)

        # Step 4: check what happened
        screen = await drv.detect_current_screen()
        self.log(f"   [login] écran post-login: {screen}")

        if screen in ("feed", "reels", "own_profile", "explore"):
            self.log(f"   [login] ✓ connecté en tant que {username}")
            return True

        # Check for 2FA
        await drv.refresh_elements()
        all_text = " ".join((e.get("text") or "").lower() for e in drv.elements)

        if any(kw in all_text for kw in (
            "code de sécurité", "security code", "authentification",
            "code de vérification", "verification code", "deux facteurs",
            "two-factor", "confirmer votre identité", "confirm your identity",
            "code à 6 chiffres", "6-digit code",
        )):
            self.log("   [login] 2FA détecté")
            if two_fa_code:
                return await self._handle_2fa(drv, two_fa_code)
            else:
                raise LoginRequired(
                    f"2FA requis pour {self.username} mais pas de code 2FA configuré"
                )

        # Check for checkpoint / suspicious activity
        if any(kw in all_text for kw in ("vérifier", "suspect", "checkpoint", "confirm")):
            raise LoginRequired(
                f"Checkpoint IG après login de {self.username} — intervention manuelle requise"
            )

        # Check for wrong password
        if any(kw in all_text for kw in (
            "mot de passe incorrect", "incorrect password",
            "réessayer", "try again", "identifiants",
        )):
            raise LoginRequired(
                f"Mot de passe incorrect pour {self.username}"
            )

        # Still on login? Try one more wait
        if screen == "login":
            await asyncio.sleep(3.0)
            screen = await drv.detect_current_screen()
            if screen in ("feed", "reels", "own_profile"):
                self.log(f"   [login] ✓ connecté (retardé) en tant que {username}")
                return True

        raise LoginRequired(
            f"Login échoué pour {self.username} — écran: {screen}"
        )

    async def _handle_2fa(self, drv, two_fa_code: str) -> bool:
        """Handle 2FA code entry.

        Supports static backup codes and TOTP (if pyotp available).
        """
        self.log("   [login] saisie du code 2FA...")

        # If it looks like a TOTP secret (base32, 16+ chars), generate code
        code = two_fa_code
        if len(two_fa_code) >= 16 and two_fa_code.isalnum():
            try:
                import pyotp
                totp = pyotp.TOTP(two_fa_code)
                code = totp.now()
                self.log(f"   [login] TOTP généré: {code[:2]}****")
            except ImportError:
                self.log("   [login] pyotp non installé, utilisation du code brut")
            except Exception:
                self.log("   [login] erreur TOTP, utilisation du code brut")

        # Find the code input field
        await drv.refresh_elements()
        code_field = (
            drv.find_element("code", contains=True)
            or drv.find_element("sécurité", contains=True)
            or drv.find_element("security", contains=True)
        )

        if code_field:
            x = code_field.get("x", 0)
            y = code_field.get("y", 0)
            await drv.ht.tap(x, y)
            await asyncio.sleep(0.3)
        else:
            # Fallback: tap center of screen
            await drv.ht.tap_pos(0.5, 0.4)
            await asyncio.sleep(0.3)

        await drv.ht.type_text(code, interval=random.randint(50, 100))
        await asyncio.sleep(0.5)

        # Submit
        tapped = (
            await drv.tap_element("Confirmer")
            or await drv.tap_element("Confirm")
            or await drv.tap_element("Suivant")
            or await drv.tap_element("Next")
            or await drv.tap_element("Envoyer")
            or await drv.tap_element("Submit")
        )

        if not tapped:
            await drv.ht.tap_pos(0.5, 0.6)

        # Wait and check
        await asyncio.sleep(4.0)
        screen = await drv.detect_current_screen()

        if screen in ("feed", "reels", "own_profile", "explore"):
            self.log(f"   [login] ✓ 2FA validé, connecté")
            return True

        raise LoginRequired(
            f"2FA échoué pour {self.username} — écran post-2FA: {screen}"
        )

    async def _load_credentials(self) -> dict | None:
        """Load account credentials from the database.

        Returns dict with username, password, two_fa or None.
        """
        async with AsyncSessionLocal() as db:
            compte = await db.get(Compte, self.compte_id)
            if not compte:
                return None

            creds = compte.creds_encrypted
            if not creds:
                return None

            # For now, creds are stored as plain JSONB
            # TODO: implement Fernet decryption when encryption is enabled
            return {
                "username": compte.handle,
                "password": creds.get("password"),
                "two_fa": creds.get("two_fa"),
                "token": creds.get("token"),
            }

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
