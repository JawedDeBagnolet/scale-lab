"""Async TH runner — dispatches Threads task types to the THDriver.

Ported from VPS th_runner.py. Each task type maps to a handler function
that uses DeviceSession + THDriver to perform the action on the iPhone.

Task types:
    th_feed      Browse Threads feed (scroll, like, reply)
    th_warmup    Warm up account (gentle feed browse)
    th_post      Publish a thread
    th_reply     Reply to a thread
    th_config    Profile config changes
    th_profile   Visit a profile
    th_login     Force login
    th_health    Health check (is app responsive?)
"""

import asyncio
import logging
import random
from typing import Any, Callable
from uuid import UUID

from app.services.automation.device_session import (
    BUNDLE_THREADS,
    DeviceSession,
    DeviceLocked,
    DeviceUnavailable,
    LoginRequired,
)
from app.services.automation.th_driver import THDriver

logger = logging.getLogger("automation.th_runner")

# ── Task dispatch table ──────────────────────────────────────────────────────

TASK_HANDLERS: dict[str, Callable] = {}


def _handler(name: str):
    def wrap(fn):
        TASK_HANDLERS[name] = fn
        return fn
    return wrap


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_th_task(
    compte_id: UUID,
    action_type: str,
    values: dict | None = None,
    preset_ids: list | None = None,
    *,
    log: Callable = logger.info,
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
            drv = THDriver(mcp_port=sess.mcp_port, log=log)

            # Ensure login
            await sess.ensure_login(drv, None)

            # Run the handler
            result = await handler(drv, sess, values, log)
            return result

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
async def _feed_session(
    drv: THDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Browse Threads feed with realistic scrolling and interactions."""
    duration = values.get("duration", 90)
    like_prob = values.get("like_probability", 0.12)

    log(f"   [th_feed] session {duration}s, like={like_prob}")

    await drv.go_home()
    await drv.wait(1.0, 2.0)

    import time
    start = time.monotonic()
    scrolls = 0
    likes = 0

    while (time.monotonic() - start) < duration:
        await drv.scroll_down()
        scrolls += 1
        await drv.wait(1.0, 3.0)

        # Random like
        if random.random() < like_prob:
            await drv.like_post()
            likes += 1
            await drv.wait(0.5, 1.5)

        # Reading pause
        await drv.reading_pause(random.randint(30, 150))

    msg = f"Feed : {scrolls} scrolls, {likes} likes en {duration}s"
    log(f"   [th_feed] {msg}")
    return True, msg


# ── Warmup ───────────────────────────────────────────────────────────────────

@_handler("th_warmup")
async def _warmup(
    drv: THDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Gentle account warmup."""
    duration = values.get("duration", 60)

    result = await _feed_session(
        drv, sess,
        {"duration": duration, "like_probability": 0.06},
        log,
    )

    msg = f"Warmup terminé ({duration}s)"
    log(f"   [th_warmup] {msg}")
    return True, msg


# ── Post ─────────────────────────────────────────────────────────────────────

@_handler("th_post")
async def _post(
    drv: THDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Publish a thread."""
    text = values.get("text")
    if not text:
        return False, "text requis pour th_post"

    ok = await drv.compose_thread(text)
    if not ok:
        return False, "Impossible d'ouvrir le composeur"

    await drv.wait(0.5, 1.0)

    # Submit
    submitted = await drv.submit_thread()
    if not submitted:
        return False, "Impossible de publier"

    await drv.wait(2.0, 4.0)

    msg = f"Thread publié ({len(text)} chars)"
    log(f"   [th_post] {msg}")
    return True, msg


# ── Reply ────────────────────────────────────────────────────────────────────

@_handler("th_reply")
async def _reply(
    drv: THDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Reply to a thread."""
    text = values.get("text")
    if not text:
        return False, "text requis pour th_reply"

    # Open reply sheet
    ok = await drv.tap_reply_button()
    if not ok:
        return False, "Bouton reply introuvable"

    await drv.wait(0.5, 1.0)

    await drv.compose_reply(text)
    await drv.wait(0.3, 0.5)

    submitted = await drv.submit_thread()
    if not submitted:
        return False, "Impossible de publier la réponse"

    await drv.wait(1.0, 2.0)

    msg = f"Réponse publiée ({len(text)} chars)"
    log(f"   [th_reply] {msg}")
    return True, msg


# ── Profile visit ────────────────────────────────────────────────────────────

@_handler("th_profile")
async def _profile(
    drv: THDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Visit a profile on Threads."""
    username = values.get("username")
    if not username:
        return False, "username requis pour th_profile"

    await drv.go_search()
    await drv.wait(0.5, 1.0)

    await drv.tap_element("Search", contains=True)
    await drv.wait(0.3, 0.5)
    await drv.ht.type_text(username)
    await drv.wait(1.0, 2.0)

    await drv.tap_element(username, contains=True)
    await drv.wait(1.5, 3.0)

    stats = await drv.get_profile_stats()
    msg = f"Profil {username} visité"
    if stats:
        msg += f" ({stats.get('followers', '?')} followers)"
    log(f"   [th_profile] {msg}")
    return True, msg


# ── Config ───────────────────────────────────────────────────────────────────

@_handler("th_config")
async def _config(drv, sess, values, log):
    log("   [th_config] Config — en attente des modules config")
    return False, "th_config pas encore implémenté"


# ── Login ────────────────────────────────────────────────────────────────────

@_handler("th_login")
async def _login(drv, sess, values, log):
    log("   [th_login] Login géré par DeviceSession.ensure_login")
    return True, "Connecté"


# ── Health check ─────────────────────────────────────────────────────────────

@_handler("th_health")
async def _health(
    drv: THDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Check if Threads app is responsive."""
    await drv.refresh_elements()
    screen = await drv.detect_current_screen(refresh=False)
    n_elements = len(drv.elements)

    msg = f"Health OK — écran={screen}, {n_elements} éléments"
    log(f"   [th_health] {msg}")
    return True, msg
