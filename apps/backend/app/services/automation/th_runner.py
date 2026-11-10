"""Async TH runner — dispatches Threads task types to ported th_iphone modules.

Each task type maps to a handler that creates a THDriver + THNavigator
from the ported th_iphone package and delegates to the rich interaction
modules ported from the VPS.

Task types:
    th_feed      Browse Threads feed (scroll, like, reply, repost, profile visits)
    th_warmup    Warm up account (gentle feed browse)
    th_post      Publish a thread (UI or API)
    th_reply     Reply to a thread
    th_config    Profile config changes (name, bio, photo, links, privacy)
    th_profile   Visit one or more profiles
    th_login     Force SSO login via Instagram
    th_create    Create a new Threads account
    th_health    Health check (app responsive + session valid)
    th_extract   Extract session tokens from device
"""

import asyncio
import logging
import random
from typing import Callable
from uuid import UUID

from app.services.automation.device_session import (
    BUNDLE_THREADS,
    DeviceSession,
    DeviceLocked,
    DeviceUnavailable,
    LoginRequired,
)
from app.services.automation.human_touch import HumanTouch
from app.services.automation.scroll_engine import ScrollEngine

logger = logging.getLogger("automation.th_runner")

# ── Task dispatch table ──────────────────────────────────────────────────────

TASK_HANDLERS: dict[str, Callable] = {}


def _handler(name: str):
    def wrap(fn):
        TASK_HANDLERS[name] = fn
        return fn
    return wrap


# ── Abort support ────────────────────────────────────────────────────────────

class AbortedError(Exception):
    """Raised when a run is aborted mid-session."""
    pass


def _check_abort(abort_event: asyncio.Event | None):
    """Raise AbortedError if the run was aborted."""
    if abort_event and abort_event.is_set():
        raise AbortedError("Run avorté")


# ── Driver/Navigator factory ─────────────────────────────────────────────────

def _make_driver_nav(sess: DeviceSession, log: Callable):
    """Create a THDriver + THNavigator from the ported th_iphone package.

    Uses HumanTouch + ScrollEngine from the DeviceSession's MCP port,
    then wraps them in the ported THDriver which has the full set of
    methods the interact modules expect (parse_visible_posts, ensure_screen,
    tap_pos, type_text, etc.)
    """
    from app.services.automation.th_iphone.driver import THDriver
    from app.services.automation.th_iphone.navigator import THNavigator

    ht = HumanTouch(sess.mcp_port, host="127.0.0.1", log=log)
    scroller = ScrollEngine(ht, log=log)
    drv = THDriver(ht, scroller, lang="fr", log=log)
    nav = THNavigator(drv, log=log)
    return drv, nav


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_th_task(
    compte_id: UUID,
    action_type: str,
    values: dict | None = None,
    preset_ids: list | None = None,
    *,
    log: Callable = logger.info,
    abort_event: asyncio.Event | None = None,
) -> tuple[bool, str]:
    """Run a Threads task for the given account.

    Returns (success, message).
    """
    values = values or {}
    preset_ids = preset_ids or []

    handler = TASK_HANDLERS.get(action_type)
    if not handler:
        return False, f"Type de tâche TH inconnu : {action_type}"

    log(f"[th_runner] {action_type} pour compte={compte_id}")

    try:
        async with DeviceSession(compte_id, BUNDLE_THREADS, log=log) as sess:
            sess._abort_event = abort_event

            drv, nav = _make_driver_nav(sess, log)

            # Ensure login
            await sess.ensure_login(drv, None)

            _check_abort(abort_event)

            # Resolve behavior presets and apply overrides
            if preset_ids:
                from app.services.automation.th_iphone.behavior.presets import (
                    resolve_behavior, apply_behavior,
                )
                behavior = await resolve_behavior(preset_ids=preset_ids, log=log)
                values = apply_behavior(dict(values), behavior, log=log)

            result = await handler(drv, nav, sess, values, preset_ids, log)
            return result

    except AbortedError:
        log(f"[th_runner] ⛔ run avorté pour compte={compte_id}")
        return False, "Run avorté par l'utilisateur"
    except DeviceLocked as e:
        return False, f"iPhone verrouillé : {e}"
    except DeviceUnavailable as e:
        return False, f"iPhone indisponible : {e}"
    except LoginRequired as e:
        return False, f"Login requis : {e}"
    except Exception as e:
        logger.exception("th_runner error for %s/%s", compte_id, action_type)
        return False, f"Erreur : {str(e)[:200]}"


# ── Feed session ─────────────────────────────────────────────────────────────

@_handler("th_feed")
async def _feed_session(drv, nav, sess, values, preset_ids, log):
    """Browse Threads feed with realistic behavior — delegates to ported module."""
    from app.services.automation.th_iphone.interact.feed_session import run_feed_session
    from app.services.automation.th_iphone.behavior.presets import resolve_behavior, apply_behavior

    # Load and apply behavior preset
    behavior = await resolve_behavior(preset_ids or None, platform="th")
    if behavior:
        apply_behavior(values, behavior, log=log)

    result = await run_feed_session(drv, nav, config=values, log=log)

    if isinstance(result, dict):
        parts = []
        if result.get("posts_seen"):
            parts.append(f"{result['posts_seen']} posts")
        if result.get("likes"):
            parts.append(f"{result['likes']} likes")
        if result.get("reposts"):
            parts.append(f"{result['reposts']} reposts")
        if result.get("replies_read"):
            parts.append(f"{result['replies_read']} replies lus")
        if result.get("duration_s"):
            parts.append(f"{result['duration_s']}s")
        msg = "Feed : " + ", ".join(parts) if parts else "Feed terminé"
        return True, msg

    return True, str(result) if result else "Feed terminé"


# ── Warmup ───────────────────────────────────────────────────────────────────

@_handler("th_warmup")
async def _warmup(drv, nav, sess, values, preset_ids, log):
    """Gentle account warmup — short feed browse with low interaction."""
    from app.services.automation.th_iphone.interact.feed_session import run_feed_session

    warmup_cfg = {
        "duration_min": values.get("duration_min", 1),
        "duration_max": values.get("duration_max", 3),
        "like_pct": 0.06,
        "reply_read_pct": 0.03,
        "repost_pct": 0,
        "visit_profile_pct": 0,
    }
    warmup_cfg.update({k: v for k, v in values.items() if k in warmup_cfg})

    result = await run_feed_session(drv, nav, config=warmup_cfg, log=log)

    duration = result.get("duration_s", "?") if isinstance(result, dict) else "?"
    msg = f"Warmup terminé ({duration}s)"
    log(f"   [th_warmup] {msg}")
    return True, msg


# ── Post ─────────────────────────────────────────────────────────────────────

@_handler("th_post")
async def _post(drv, nav, sess, values, preset_ids, log):
    """Publish a thread — via UI automation or API."""
    from app.services.automation.th_iphone.interact.publish import publish_thread

    text = values.get("text", values.get("caption", ""))
    media_index = values.get("media_index")

    if not text and media_index is None:
        return False, "text ou media_index requis pour th_post"

    result = await publish_thread(drv, nav, caption=text, media_index=media_index, log=log)

    if isinstance(result, dict):
        ok = result.get("ok", False)
        msg = f"Thread publié ({len(text)} chars)" if ok else f"Échec publication : {result.get('error', '?')}"
        return ok, msg
    elif isinstance(result, bool):
        if result:
            return True, f"Thread publié ({len(text)} chars)"
        return False, "Échec publication du thread"

    return True, f"Thread publié ({len(text)} chars)"


# ── Reply ────────────────────────────────────────────────────────────────────

@_handler("th_reply")
async def _reply(drv, nav, sess, values, preset_ids, log):
    """Reply to a thread — via UI automation."""
    from app.services.automation.th_iphone.interact.publish import publish_reply

    text = values.get("text", "")
    post = values.get("post", {})

    if not text:
        return False, "text requis pour th_reply"

    result = await publish_reply(drv, nav, post=post, reply_text=text, log=log)

    if isinstance(result, bool):
        if result:
            return True, f"Réponse publiée ({len(text)} chars)"
        return False, "Échec publication de la réponse"

    return True, f"Réponse publiée ({len(text)} chars)"


# ── Profile visit ────────────────────────────────────────────────────────────

@_handler("th_profile")
async def _profile(drv, nav, sess, values, preset_ids, log):
    """Visit one or more profiles on Threads."""
    from app.services.automation.th_iphone.interact.profile_session import (
        run_profile_session,
        visit_single_profile,
    )

    username = values.get("username")
    targets = values.get("targets", [])

    if username and not targets:
        targets = [username]

    if not targets:
        return False, "username ou targets requis pour th_profile"

    if len(targets) == 1:
        # Single profile visit
        result = await visit_single_profile(drv, nav, targets[0], values, log)
        msg = f"Profil @{targets[0]} visité"
        if isinstance(result, dict):
            if result.get("followed"):
                msg += " + suivi"
            if result.get("followers"):
                msg += f" ({result['followers']} followers)"
        return True, msg
    else:
        # Multi-profile session
        result = await run_profile_session(drv, nav, targets, config=values, log=log)
        if isinstance(result, dict):
            visited = result.get("visited", len(targets))
            follows = result.get("follows", 0)
            msg = f"{visited} profils visités, {follows} follows"
            return True, msg
        return True, f"{len(targets)} profils visités"


# ── Config ───────────────────────────────────────────────────────────────────

@_handler("th_config")
async def _config(drv, nav, sess, values, preset_ids, log):
    """Apply profile config changes — name, bio, photo, links, privacy."""
    from app.services.automation.th_iphone.interact.profile_config import full_profile_setup

    result = await full_profile_setup(
        drv, nav,
        name=values.get("name"),
        bio=values.get("bio"),
        photo_index=values.get("photo_index"),
        link_url=values.get("link_url"),
        link_title=values.get("link_title"),
        private=values.get("private"),
        log=log,
    )

    if isinstance(result, dict):
        changes = [k for k, v in result.items() if v]
        msg = f"Config appliquée : {', '.join(changes)}" if changes else "Aucun changement"
        return True, msg

    return True, "Config appliquée"


# ── Login (SSO via Instagram) ────────────────────────────────────────────────

@_handler("th_login")
async def _login(drv, nav, sess, values, preset_ids, log):
    """Force SSO login to Threads via Instagram account."""
    from app.services.automation.th_iphone.interact.account_login import threads_sso_login

    result = await threads_sso_login(drv, nav, log=log)

    if isinstance(result, bool):
        if result:
            return True, "Connecté via SSO Instagram"
        return False, "Échec du login SSO"

    return True, "Connecté"


# ── Account creation ─────────────────────────────────────────────────────────

@_handler("th_create")
async def _create(drv, nav, sess, values, preset_ids, log):
    """Create a new Threads account."""
    from app.services.automation.th_iphone.interact.account_create import create_threads_account

    username = values.get("username", "")
    password = values.get("password", "")

    if not username or not password:
        return False, "username et password requis pour th_create"

    totp_secret = values.get("totp_secret")
    private = values.get("private", False)

    result = await create_threads_account(
        drv, nav,
        username=username,
        password=password,
        totp_secret=totp_secret,
        private=private,
        log=log,
    )

    if isinstance(result, dict):
        ok = result.get("ok", False)
        msg = f"Compte créé" if ok else f"Échec création : {result.get('error', '?')}"
        return ok, msg
    elif isinstance(result, bool):
        return result, "Compte créé" if result else "Échec création"

    return True, "Compte créé"


# ── Health check ─────────────────────────────────────────────────────────────

@_handler("th_health")
async def _health(drv, nav, sess, values, preset_ids, log):
    """Full health check — app responsive + session valid."""
    from app.services.automation.th_iphone.interact.session_extract import full_health_check

    result = await full_health_check(drv, log=log)

    if isinstance(result, dict):
        ok = result.get("ok", True)
        status = result.get("status", "unknown")
        msg = f"Health: {status}"
        if result.get("followers") is not None:
            msg += f" | {result['followers']} followers"
        if result.get("posts") is not None:
            msg += f" | {result['posts']} posts"
        return ok, msg

    # Fallback: just check elements are visible
    await drv.get_elements(refresh=True)
    screen = await drv.detect_current_screen()
    n = len(drv._elements_cache or [])
    msg = f"Health OK — écran={screen}, {n} éléments"
    log(f"   [th_health] {msg}")
    return True, msg


# ── Session extraction ───────────────────────────────────────────────────────

@_handler("th_extract")
async def _extract(drv, nav, sess, values, preset_ids, log):
    """Extract session tokens from device."""
    from app.services.automation.th_iphone.interact.session_extract import extract_session_from_device

    result = await extract_session_from_device(drv, log=log)

    if isinstance(result, dict):
        has_session = bool(result.get("sessionid"))
        msg = f"Session extraite (user_id={result.get('user_id', '?')})" if has_session else "Pas de session trouvée"
        return has_session, msg

    return False, "Extraction échouée"


# ── Frontend action-name aliases ─────────────────────────────────────────────
# The Scenarios frontend uses short identifiers that differ from handler names.

_ALIASES: dict[str, str] = {
    "thi_feed": "th_feed",
    "thi_prof": "th_profile",
    "thi_conf": "th_config",
    "thi_post": "th_post",
}

for _alias, _canonical in _ALIASES.items():
    if _canonical in TASK_HANDLERS:
        TASK_HANDLERS[_alias] = TASK_HANDLERS[_canonical]
