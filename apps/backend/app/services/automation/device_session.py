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

DEFAULT_MCP_PORT = 18090
DEFAULT_SSH_PORT = 2223

# Lock screen markers (iOS FR locale)
_LOCK_MARKERS = ("lampe torche", "appareil photo", "afficher les notifications")

# Labels de boutons popup a dismiss apres login / dans les ecrans inconnus
# Ne taper que si y > 400 pour eviter de taper dans un champ de formulaire
POPUP_DISMISS_LABELS = [
    "OK", "Plus tard", "Pas maintenant", "Ne pas autoriser",
    "Fermer", "Ignorer", "Enregistrer", "Continuer",
    "Passer", "Non merci",
    "Continuer avec Instagram", "Essayer d'une autre façon",
]

# ── Per-device FIFO queue ────────────────────────────────────────────────────
# Each iPhone gets a FIFO queue. Orders wait their turn indefinitely.
# Between sessions, the proxy IP is rotated via the provider's API.
#
# The queue is backed by an asyncio.Lock (simple FIFO — asyncio.Lock is fair,
# awaiters are served in order). No timeout rejection: orders wait until
# their turn comes. The lock is held for the entire session duration.

_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()
_queue_positions: dict[str, int] = {}  # device_id → number of waiting orders


async def _device_lock(device_id: str) -> asyncio.Lock:
    """Get or create the per-device FIFO lock."""
    async with _locks_guard:
        if device_id not in _locks:
            _locks[device_id] = asyncio.Lock()
            _queue_positions[device_id] = 0
        return _locks[device_id]


def get_queue_position(device_id: str) -> int:
    """Return the number of orders waiting for this device."""
    return _queue_positions.get(device_id, 0)


async def _rotate_proxy_ip(device_id: str, log: Callable = logger.info) -> bool:
    """Call the proxy rotation API to get a new IP before the next session.

    Looks up the proxy assigned to this iPhone and calls its rotation_url.
    Returns True if rotation succeeded (or no rotation needed).
    """
    from app.db import AsyncSessionLocal
    from app.models.iphone import IPhone
    from app.models.proxy import Proxy

    async with AsyncSessionLocal() as db:
        iphone = await db.get(IPhone, device_id)
        if not iphone or not iphone.proxy_id:
            log(f"   [proxy] pas de proxy assigné au device {device_id}")
            return True  # no proxy = nothing to rotate

        proxy = await db.get(Proxy, iphone.proxy_id)
        if not proxy or not proxy.rotation_url:
            log(f"   [proxy] proxy {proxy.ip if proxy else '?'} sans rotation_url")
            return True  # no rotation URL = skip

    # Call the rotation API
    import httpx
    log(f"   [proxy] rotation IP via {proxy.rotation_url[:60]}...")
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(proxy.rotation_url)
            if resp.status_code == 200:
                log(f"   [proxy] ✓ IP rotée — {resp.text[:100]}")
                return True
            else:
                log(f"   [proxy] ⚠ rotation HTTP {resp.status_code}: {resp.text[:100]}")
                return False
    except Exception as e:
        log(f"   [proxy] ⚠ rotation échouée: {str(e)[:100]}")
        return False


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
        "get_ui_elements",
        params={"clickable_only": False, "max_elements": 25},
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
        device_id = self.ctx["device_id"]

        # FIFO queue: acquire per-device lock (no timeout — orders wait their turn)
        self._lock = await _device_lock(device_id)
        _queue_positions[device_id] = _queue_positions.get(device_id, 0) + 1
        pos = _queue_positions[device_id]
        if self._lock.locked():
            self.log(f"   [queue] file d'attente position #{pos} pour {self.ctx['device_label']}")
        await self._lock.acquire()
        self._lock_acquired = True
        _queue_positions[device_id] = max(0, _queue_positions.get(device_id, 1) - 1)

        try:
            # Rotate proxy IP before this session
            await _rotate_proxy_ip(device_id, self.log)

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
          1. Ensure Instagram is in foreground
          2. Detect current screen via MCP accessibility tree
          3. If on login screen → perform full login (username, password, 2FA)
          4. If on feed/profile/etc → already logged in
          5. If on checkpoint/error → raise LoginRequired
        """
        self.log("   [login] Instagram login check")

        # Ensure Instagram is actually in foreground
        from app.services.dispatch import mcp_call, DEFAULT_MCP_PORT
        mcp_port = self.ctx.get("mcp_port", DEFAULT_MCP_PORT)
        frontmost = await mcp_call(mcp_port, "get_frontmost_app")
        if frontmost:
            try:
                import json
                content = frontmost.get("content", [{}])
                app_data = json.loads(content[0].get("text", "{}")) if content else {}
                current_bundle = app_data.get("bundleId", "")
            except Exception:
                current_bundle = ""
            if current_bundle != "com.burbn.instagram":
                self.log("   [login] IG pas au premier plan, lancement...")
                await mcp_call(mcp_port, "launch_app", {"bundle_id": "com.burbn.instagram"}, timeout=15)
                await asyncio.sleep(2.0)

        # Wait for the app to settle after container switch + relaunch
        await asyncio.sleep(2.0)

        screen = await drv.detect_current_screen()
        self.log(f"   [login] écran détecté: {screen}")

        if screen in ("feed", "reels", "own_profile", "explore", "post_view", "story", "profile"):
            self.log("   [login] IG: déjà connecté")
            return True

        if screen == "onboarding":
            self.log("   [login] IG: écran d'onboarding, tap sur J'ai déjà un profil...")
            tapped = await drv.tap_element("J'ai déjà un profil")
            if not tapped:
                tapped = await drv.tap_element("Log In")
            if not tapped:
                # Fallback: use MCP tap_element which searches accessibility + OCR
                from app.services.dispatch import mcp_call
                mcp_port = self.ctx.get("mcp_port", DEFAULT_MCP_PORT)
                r = await mcp_call(mcp_port, "tap_element", {"text": "profil", "match": "contains"}, timeout=10)
                if not r or not (r.get("structuredContent", {}) or {}).get("tapped"):
                    # Last resort: tap at known coordinates for "J'ai déjà un profil" button
                    self.log("   [login] tap_element échoué, tap coordonnées directes (185, 706)")
                    await mcp_call(mcp_port, "tap_screen", {"x": 185, "y": 706}, timeout=5)
                    tapped = True
            await asyncio.sleep(2.0)
            screen = await drv.detect_current_screen()
            self.log(f"   [login] écran après onboarding: {screen}")
            if screen == "login":
                return await self._do_ig_login(drv)
            elif screen in ("feed", "reels", "own_profile"):
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

        if screen == "onboarding":
            self.log("   [login] IG: onboarding (retry), tap J'ai déjà un profil...")
            await drv.tap_element("J'ai déjà un profil")
            await asyncio.sleep(2.0)
            screen = await drv.detect_current_screen()
            if screen == "login":
                return await self._do_ig_login(drv)

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

        # Step 1: tap username field via MCP tap_element (coords are 0,0 in tree)
        from app.services.dispatch import mcp_call
        mcp_port = self.ctx.get("mcp_port", DEFAULT_MCP_PORT)

        # Try MCP tap_element with various labels
        username_tapped = False
        for label in [
            "Nom de profil", "e-mail", "numéro de mobile",  # page login v2
            "nom d'utilisateur", "username", "téléphone",    # page login v1
            "numéro de téléphone",                           # page login v1 alt
        ]:
            self.log(f"   [login] recherche champ username: '{label}'")
            r = await mcp_call(mcp_port, "tap_element", {"text": label, "match": "contains"}, timeout=8)
            if r and r.get("content"):
                try:
                    import json
                    tap_data = json.loads(r["content"][0].get("text", "{}"))
                    if tap_data.get("tapped"):
                        self.log(f"   [login] ✓ champ username trouvé via '{label}'")
                        username_tapped = True
                        break
                except Exception:
                    pass

        if not username_tapped:
            self.log("   [login] champ username non trouvé par MCP, tap position par défaut (187, 295)")
            await mcp_call(mcp_port, "tap_screen", {"x": 187, "y": 295}, timeout=5)

        await asyncio.sleep(0.5)

        # Clear any existing text and type username
        self.log(f"   [login] saisie username: {username}")
        await drv.ht.type_text(username, interval=random.randint(40, 90))
        await asyncio.sleep(0.5)

        # Step 2: tap password field via MCP tap_element
        password_tapped = False
        for label in ["Mot de passe", "password", "Password"]:
            self.log(f"   [login] recherche champ password: '{label}'")
            r = await mcp_call(mcp_port, "tap_element", {"text": label, "match": "contains"}, timeout=8)
            if r and r.get("content"):
                try:
                    tap_data = json.loads(r["content"][0].get("text", "{}"))
                    if tap_data.get("tapped"):
                        self.log(f"   [login] ✓ champ password trouvé via '{label}'")
                        password_tapped = True
                        break
                except Exception:
                    pass

        if not password_tapped:
            self.log("   [login] champ password non trouvé par MCP, tap position par défaut (187, 365)")
            await mcp_call(mcp_port, "tap_screen", {"x": 187, "y": 365}, timeout=5)

        await asyncio.sleep(0.5)

        self.log("   [login] saisie password...")
        await drv.ht.type_text(password, interval=random.randint(30, 70))
        await asyncio.sleep(0.5)

        # Step 3: tap login button via MCP tap_element
        login_tapped = False
        for label in ["Se connecter", "Connexion", "Log In", "Log in"]:
            r = await mcp_call(mcp_port, "tap_element", {"text": label}, timeout=8)
            if r and r.get("content"):
                try:
                    tap_data = json.loads(r["content"][0].get("text", "{}"))
                    if tap_data.get("tapped"):
                        self.log(f"   [login] ✓ bouton login trouvé: '{label}'")
                        login_tapped = True
                        break
                except Exception:
                    pass

        if not login_tapped:
            self.log("   [login] bouton login non trouvé, tap position par défaut (187, 440)")
            await mcp_call(mcp_port, "tap_screen", {"x": 187, "y": 440}, timeout=5)

        # Step 4: post-login loop — handle popups, 2FA, etc.
        # Instagram shows 2-3 intermediate screens before reaching feed
        self.log("   [login] attente réponse serveur...")
        await asyncio.sleep(4.0)

        return await self._post_login_loop(drv, username, two_fa_code)

    async def _post_login_loop(
        self, drv, username: str, two_fa_code: str | None = None, max_steps: int = 15
    ) -> bool:
        """Boucle post-login : gère les popups, 2FA, écrans inconnus.

        Itère jusqu'à 15 fois pour traverser les écrans intermédiaires
        (save login, notifications, 2FA, etc.) jusqu'au feed.
        """
        from app.services.dispatch import mcp_call
        mcp_port = self.ctx.get("mcp_port", DEFAULT_MCP_PORT)

        for step in range(max_steps):
            screen = await drv.detect_current_screen()
            self.log(f"   [post-login] step {step+1}/{max_steps} — écran: {screen}")

            # ── Succès : on est sur le feed ──
            if screen in ("feed", "reels", "own_profile", "explore", "post_view", "story", "profile"):
                self.log(f"   [login] ✓ connecté en tant que {username}")
                return True

            # ── Save login popup ──
            if screen == "save_login":
                self.log("   [post-login] popup 'Enregistrer les infos'")
                tapped = await self._mcp_tap_first(mcp_port, [
                    "Enregistrer", "Plus tard", "Save", "Not Now"
                ])
                if not tapped:
                    await mcp_call(mcp_port, "tap_screen", {"x": 187, "y": 680}, timeout=5)
                await asyncio.sleep(2.0)
                continue

            # ── Notifications popup ──
            if screen == "notif_popup":
                self.log("   [post-login] popup 'Notifications'")
                await self._mcp_tap_first(mcp_port, [
                    "Plus tard", "Pas maintenant", "Not Now", "Skip"
                ])
                await asyncio.sleep(2.0)
                continue

            # ── 2FA notification check ──
            if screen == "2fa_notif":
                self.log("   [post-login] 2FA notification check — tap 'Essayer d'une autre façon'")
                tapped = await self._mcp_tap_first(mcp_port, [
                    "Essayer d'une autre",      # sans "façon" (cédille peut poser problème)
                    "Essayer d’une autre",  # apostrophe typographique
                    "Try Another Way",
                ])
                if not tapped:
                    # Fallback: tap par texte exact via MCP
                    self.log("   [post-login] tap_element échoué, essai avec texte partiel...")
                    r = await mcp_call(mcp_port, "tap_element", {"text": "autre", "match": "contains"}, timeout=8)
                    tapped2 = False
                    if r and r.get("content"):
                        try:
                            tap_data = json.loads(r["content"][0].get("text", "{}"))
                            tapped2 = tap_data.get("tapped", False)
                        except Exception:
                            pass
                    if not tapped2:
                        # Dernier recours: coordonnées connues du bouton
                        self.log("   [post-login] fallback coordonnées directes")
                        await mcp_call(mcp_port, "tap_screen", {"x": 187, "y": 706}, timeout=5)
                await asyncio.sleep(2.0)
                continue

            # ── 2FA method choice ──
            if screen == "2fa_choice":
                self.log("   [post-login] 2FA choix de méthode — sélection 'Application d'authentification'")
                tapped = await self._mcp_tap_first(mcp_port, [
                    "Application d'authentification",  # apostrophe standard
                    "Application d’authentification",  # apostrophe typographique
                    "Authentication App",
                ])
                if not tapped:
                    # Fallback: recherche partielle sans apostrophe
                    self.log("   [post-login] tap_element échoué, essai texte partiel 'authentification'")
                    r = await mcp_call(mcp_port, "tap_element", {"text": "authentification", "match": "contains"}, timeout=8)
                    tapped2 = False
                    if r and r.get("content"):
                        try:
                            tap_data = json.loads(r["content"][0].get("text", "{}"))
                            tapped2 = tap_data.get("tapped", False)
                            if tapped2:
                                self.log("   [tap] ✓ 'authentification' trouvé et tappé")
                        except Exception:
                            pass
                    if not tapped2:
                        # Coordonnées connues du bouton (index 4, y:292 dans le dump)
                        self.log("   [post-login] fallback coordonnées (187, 333)")
                        await mcp_call(mcp_port, "tap_screen", {"x": 187, "y": 333}, timeout=5)
                await asyncio.sleep(1.5)
                # Maintenant taper "Continuer"
                await self._mcp_tap_first(mcp_port, ["Continuer", "Continue"])
                await asyncio.sleep(2.0)
                continue

            # ── 2FA code entry ──
            if screen == "2fa_code":
                self.log("   [post-login] 2FA code entry")
                if not two_fa_code:
                    raise LoginRequired(
                        f"2FA requis pour {self.username} mais pas de code 2FA configuré"
                    )
                return await self._handle_2fa(drv, two_fa_code)

            # ── Checkpoint / suspicious ──
            if screen == "checkpoint":
                raise LoginRequired(
                    f"Checkpoint IG après login de {self.username} — intervention manuelle requise"
                )

            # ── Login error (wrong password) ──
            if screen == "login_error":
                raise LoginRequired(
                    f"Mot de passe incorrect pour {self.username}"
                )

            # ── Still on login screen ──
            if screen == "login":
                self.log("   [post-login] encore sur login, attente 3s...")
                await asyncio.sleep(3.0)
                continue

            # ── Onboarding (new container) ──
            if screen == "onboarding":
                self.log("   [post-login] onboarding, tap 'J'ai déjà un profil'")
                await self._mcp_tap_first(mcp_port, [
                    "J'ai déjà un profil", "Log In", "profil"
                ])
                await asyncio.sleep(2.0)
                continue

            # ── Unknown screen → recovery ──
            if screen == "other":
                self.log("   [post-login] écran inconnu, tentative de recovery...")
                recovered = await self._handle_unknown_screen(drv, mcp_port)
                if recovered and recovered not in ("other", "unknown"):
                    continue  # re-enter the loop with the new screen
                # Dump l'arbre pour debug
                elements = await drv.ht.get_elements()
                self.log("   [post-login] dump arbre d'accessibilité:")
                for el in elements[:15]:
                    t = (el.get("text") or "")[:60]
                    if t:
                        self.log(f"     {el.get('type','?')} | {t}")
                # One more chance
                if step < max_steps - 1:
                    await asyncio.sleep(3.0)
                    continue

        raise LoginRequired(
            f"Login échoué pour {self.username} — écran: {screen} après {max_steps} étapes"
        )

    async def _mcp_tap_first(self, mcp_port: int, labels: list[str]) -> bool:
        """Tap le premier label trouvé via MCP tap_element."""
        from app.services.dispatch import mcp_call
        import json
        for label in labels:
            r = await mcp_call(mcp_port, "tap_element", {"text": label, "match": "contains"}, timeout=8)
            if r and r.get("content"):
                try:
                    tap_data = json.loads(r["content"][0].get("text", "{}"))
                    if tap_data.get("tapped"):
                        self.log(f"   [tap] ✓ '{label}' trouvé et tappé")
                        return True
                except Exception:
                    pass
        return False

    async def _handle_unknown_screen(self, drv, mcp_port: int, max_retries: int = 3) -> str | None:
        """Tente de récupérer d'un écran inconnu en cherchant des boutons popup."""
        from app.services.dispatch import mcp_call

        for attempt in range(max_retries):
            await asyncio.sleep(3.0)
            screen = await drv.detect_current_screen()
            if screen != "other":
                self.log(f"   [recovery] écran résolu après attente: {screen}")
                return screen

            # Chercher un bouton popup via MCP tap_element
            for dismiss_label in POPUP_DISMISS_LABELS:
                r = await mcp_call(
                    mcp_port, "tap_element",
                    {"text": dismiss_label, "match": "contains"},
                    timeout=5,
                )
                if r and r.get("content"):
                    try:
                        import json
                        tap_data = json.loads(r["content"][0].get("text", "{}"))
                        if tap_data.get("tapped"):
                            self.log(f"   [recovery] popup dismissé: '{dismiss_label}'")
                            await asyncio.sleep(2.0)
                            break
                    except Exception:
                        pass

        # Dernier check
        screen = await drv.detect_current_screen()
        return screen

    async def _handle_2fa(self, drv, two_fa_code: str) -> bool:
        """Handle 2FA code entry.

        Supports static backup codes and TOTP (if pyotp available).
        After 2FA validation, continues through post-login loop
        to handle save_login / notification popups.
        """
        from app.services.dispatch import mcp_call
        mcp_port = self.ctx.get("mcp_port", DEFAULT_MCP_PORT)

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

        # Tap the code input field — tap_screen direct au centre du champ
        # (tap_element sur "Code" tape sur le label, pas le champ input)
        # Coordonnées connues: (32, 501) 275x20 → centre = (169, 511)
        self.log("   [login] tap champ code 2FA (169, 511)")
        await mcp_call(mcp_port, "tap_screen", {"x": 169, "y": 511}, timeout=5)
        await asyncio.sleep(1.0)  # attendre que le clavier s'ouvre

        # Type the code — d'abord essayer input_text (injection directe),
        # puis fallback type_text (clavier) si le champ n'est pas focus
        self.log(f"   [login] saisie code 2FA: {code[:2]}****")
        input_result = await mcp_call(mcp_port, "input_text", {"text": code}, timeout=8)
        if not input_result:
            self.log("   [login] input_text échoué, fallback type_text")
            await drv.ht.type_text(code, interval=random.randint(60, 120), realistic=False)
        await asyncio.sleep(0.5)

        # NE PAS taper "Faire confiance" — la checkbox est cochée par défaut,
        # taper dessus la décoche et IG redemandera le 2FA à chaque connexion
        await asyncio.sleep(0.3)

        # Submit — le bouton sur IG est "Continuer", pas "Confirmer"
        self.log("   [login] validation du code 2FA...")
        tapped = await self._mcp_tap_first(mcp_port, [
            "Continuer", "Continue",   # IG 2FA
            "Confirmer", "Confirm",    # variante
            "Suivant", "Next",         # variante
            "Envoyer", "Submit",       # variante
        ])
        if not tapped:
            self.log("   [login] bouton validation non trouvé, tap position par défaut")
            await mcp_call(mcp_port, "tap_screen", {"x": 187, "y": 734}, timeout=5)

        # Continue through post-login loop to handle remaining popups
        self.log("   [login] attente validation 2FA...")
        await asyncio.sleep(4.0)

        # Re-enter post-login loop for save_login, notifications, etc.
        return await self._post_login_loop(drv, self.username, None, max_steps=10)

    async def _load_credentials(self) -> dict | None:
        """Load account credentials from the database.

        Returns dict with username, password, two_fa or None.
        """
        async with AsyncSessionLocal() as db:
            compte = await db.get(Compte, self.compte_id)
            if not compte:
                return None

            creds_raw = compte.creds_encrypted
            if not creds_raw:
                return None

            # Decrypt via Fernet (handles both encrypted and legacy plaintext)
            from app.crypto import decrypt_creds
            creds = decrypt_creds(creds_raw)
            if not creds:
                return None

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
