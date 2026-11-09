"""Async IG runner — dispatches Instagram task types to ported ig_iphone modules.

Each task type maps to a handler that uses DeviceSession + IGDriver + IGNavigator
to perform the action on the iPhone. The actual interaction logic lives in the
ig_iphone/ package (ported from VPS); this file is the async dispatcher.

Task types:
    ig_feed          Browse feed (scroll, like, comment)
    ig_reels         Browse reels
    ig_stories       View stories
    ig_profile       Visit a profile
    ig_post          Publish a post (photo/video/carousel)
    ig_story_post    Publish a story
    ig_reel_post     Publish a reel
    ig_warmup        Warm up account (gentle feed browse)
    ig_login         Force login
    ig_config        Profile config changes
    ig_switch_pro    Switch to professional account
    ig_highlight_*   Highlight CRUD
    ig_banner_*      Banner CRUD
    ig_media_import  Import media to device gallery
    ig_story_sticker Add sticker to story
"""

import asyncio
import logging
from typing import Callable
from uuid import UUID

from app.services.automation.device_session import (
    BUNDLE_INSTAGRAM,
    DeviceSession,
    DeviceLocked,
    DeviceUnavailable,
    LoginRequired,
)
from app.services.automation.ig_driver import IGDriver
from app.services.automation.ig_iphone.navigator import IGNavigator
from app.services.automation.ig_iphone.health import check_account_health

logger = logging.getLogger("automation.ig_runner")

# ── Task dispatch table ──────────────────────────────────────────────────────

TASK_HANDLERS: dict[str, Callable] = {}


def _handler(name: str):
    """Decorator to register a task handler."""
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


# ── Health check helper ──────────────────────────────────────────────────────

async def _ensure_healthy(sess: DeviceSession, log: Callable) -> tuple[bool, str] | None:
    """Check account health before a session. Returns (False, msg) if unhealthy, None if OK."""
    health = await check_account_health(sess.compte_id, log=log)
    if not health["ok"]:
        return False, f"Compte en {health['status']} — session annulée"
    return None


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_ig_task(
    compte_id: UUID,
    action_type: str,
    values: dict | None = None,
    preset_ids: list | None = None,
    *,
    log: Callable = logger.info,
    abort_event: asyncio.Event | None = None,
) -> tuple[bool, str]:
    """Run an Instagram task for the given account.

    Returns (success, message).
    """
    values = values or {}
    preset_ids = preset_ids or []

    handler = TASK_HANDLERS.get(action_type)
    if not handler:
        return False, f"Type de tâche IG inconnu : {action_type}"

    log(f"[ig_runner] {action_type} pour compte={compte_id}")

    try:
        async with DeviceSession(compte_id, BUNDLE_INSTAGRAM, log=log) as sess:
            # Store abort_event on session so handlers can access it
            sess._abort_event = abort_event
            sess._preset_ids = preset_ids

            drv = IGDriver(mcp_port=sess.mcp_port, log=log)
            nav = IGNavigator(drv, log=log)

            # Ensure login
            await sess.ensure_login(drv, None)

            _check_abort(abort_event)

            # Run the handler
            result = await handler(drv, nav, sess, values, log)
            return result

    except AbortedError:
        log(f"[ig_runner] ⛔ run avorté pour compte={compte_id}")
        return False, "Run avorté par l'utilisateur"
    except DeviceLocked as e:
        return False, f"iPhone verrouillé : {e}"
    except DeviceUnavailable as e:
        return False, f"iPhone indisponible : {e}"
    except LoginRequired as e:
        return False, f"Login requis : {e}"
    except Exception as e:
        logger.exception("ig_runner error for %s/%s", compte_id, action_type)
        return False, f"Erreur : {str(e)[:200]}"


# ── Helper: format stats dict into (bool, str) ──────────────────────────────

def _fmt(stats: dict, label: str, keys: list[str] | None = None) -> tuple[bool, str]:
    """Format a stats dict from a ported module into the runner's (bool, str)."""
    if not stats:
        return False, f"{label} : pas de résultat"
    parts = []
    for k in (keys or list(stats.keys())):
        v = stats.get(k)
        if v is not None and k not in ("started_at", "ended_at", "duration_s", "type"):
            parts.append(f"{k}={v}")
    dur = stats.get("duration_s", 0)
    msg = f"{label} : {', '.join(parts)}" + (f" en {dur}s" if dur else "")
    return True, msg


# ══════════════════════════════════════════════════════════════════════════════
#  INTERACTION SESSIONS
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_feed")
async def _feed_session(drv, nav, sess, values, log):
    """Browse IG feed."""
    blocked = await _ensure_healthy(sess, log)
    if blocked:
        return blocked

    from app.services.automation.ig_iphone.interact.feed_session import run_feed_session
    abort_fn = lambda: _check_abort(getattr(sess, '_abort_event', None))
    stats = await run_feed_session(drv, nav, config=values, log=log, abort_check=abort_fn)
    return _fmt(stats, "Feed", ["posts_seen", "likes", "saves", "comments_read"])


@_handler("ig_reels")
async def _reels_session(drv, nav, sess, values, log):
    """Browse IG reels."""
    blocked = await _ensure_healthy(sess, log)
    if blocked:
        return blocked

    from app.services.automation.ig_iphone.interact.reels_session import run_reels_session
    abort_fn = lambda: _check_abort(getattr(sess, '_abort_event', None))
    stats = await run_reels_session(drv, nav, config=values, log=log, abort_check=abort_fn)
    return _fmt(stats, "Reels", [
        "reels_watched", "likes", "follows", "saves",
        "comments_read", "sponsored_skipped", "fast_skipped",
    ])


@_handler("ig_stories")
async def _stories_session(drv, nav, sess, values, log):
    """View stories from feed tray."""
    blocked = await _ensure_healthy(sess, log)
    if blocked:
        return blocked

    from app.services.automation.ig_iphone.interact.story_view import watch_stories
    stats = await watch_stories(drv, nav, config=values, log=log)
    return _fmt(stats, "Stories", ["stories_watched", "likes"])


@_handler("ig_profile")
async def _profile_visit(drv, nav, sess, values, log):
    """Visit a user profile."""
    blocked = await _ensure_healthy(sess, log)
    if blocked:
        return blocked

    username = values.get("username")
    if not username:
        return False, "username requis pour ig_profile"

    from app.services.automation.ig_iphone.interact.profile_visit import visit_profile
    stats = await visit_profile(drv, nav, username, config=values, log=log)
    return _fmt(stats, f"Profil @{username}", ["behavior", "likes", "follows"])


@_handler("ig_warmup")
async def _warmup(drv, nav, sess, values, log):
    """Gentle account warmup — feed + stories + maybe reels."""
    blocked = await _ensure_healthy(sess, log)
    if blocked:
        return blocked

    from app.services.automation.ig_iphone.interact.feed_session import run_feed_session
    from app.services.automation.ig_iphone.interact.story_view import watch_stories
    from app.services.automation.ig_iphone.interact.reels_session import run_reels_session
    import random

    duration = values.get("duration", 90)
    results = []

    # Phase 1: Feed (60% of time)
    log("\n--- Phase 1: Feed ---")
    feed_cfg = {**values, "duration_min": 0, "duration_max": 0}
    feed_cfg["duration"] = int(duration * 0.6)
    feed_cfg["like_pct"] = values.get("like_pct", 0.08)
    stats = await run_feed_session(drv, nav, config=feed_cfg, log=log)
    results.append(("feed", stats))

    _check_abort(getattr(sess, '_abort_event', None))

    # Phase 2: Stories (80% chance)
    if random.random() < 0.8:
        log("\n--- Phase 2: Stories ---")
        story_cfg = {**values, "max_stories": values.get("stories_max", 6)}
        stats = await watch_stories(drv, nav, config=story_cfg, log=log)
        results.append(("stories", stats))

    _check_abort(getattr(sess, '_abort_event', None))

    # Phase 3: Reels (40% chance)
    if random.random() < 0.4:
        log("\n--- Phase 3: Reels ---")
        reels_cfg = {**values, "duration_min": 0, "duration_max": 0}
        reels_cfg["duration"] = int(duration * 0.2)
        stats = await run_reels_session(drv, nav, config=reels_cfg, log=log)
        results.append(("reels", stats))

    msg = f"Warmup terminé ({duration}s, {len(results)} phases)"
    log(f"   [ig_warmup] {msg}")
    return True, msg


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLICATIONS
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_post")
async def _publish_post(drv, nav, sess, values, log):
    """Publish a feed post (photo/video/carousel)."""
    from app.services.automation.ig_iphone.interact.publish import (
        publish_feed_post, publish_carousel,
    )
    from app.services.automation.ig_iphone.media import push_media_via_mcp

    # Transfer media to iPhone if URLs provided
    media_urls = values.get("media_urls", [])
    if media_urls:
        for url in media_urls:
            result = await push_media_via_mcp(drv, url, log=log)
            if not result:
                return False, f"ig_post: échec pipeline média"
        await asyncio.sleep(2.0)

    caption = values.get("caption", "")
    location = values.get("location")
    photo_count = len(media_urls) if media_urls else 1

    if photo_count > 1:
        stats = await publish_carousel(drv, nav, caption=caption, photo_count=photo_count, log=log)
    else:
        stats = await publish_feed_post(drv, nav, caption=caption, location=location, log=log)

    published = stats.get("published", False)
    msg = f"Post {'publié' if published else 'échoué'}"
    if caption:
        msg += f" ({len(caption)} chars)"
    return published, msg


@_handler("ig_story_post")
async def _publish_story(drv, nav, sess, values, log):
    """Publish a story."""
    from app.services.automation.ig_iphone.interact.publish import publish_story
    from app.services.automation.ig_iphone.media import push_media_via_mcp

    media_url = values.get("media_url")
    if media_url:
        result = await push_media_via_mcp(drv, media_url, log=log)
        if not result:
            return False, "ig_story_post: échec pipeline média"
        await asyncio.sleep(2.0)

    caption = values.get("text", values.get("caption"))
    stickers = values.get("stickers")
    stats = await publish_story(drv, nav, caption=caption, stickers=stickers, log=log)

    published = stats.get("published", False)
    return published, "Story publiée" if published else "Story : échec publication"


@_handler("ig_reel_post")
async def _publish_reel(drv, nav, sess, values, log):
    """Publish a reel."""
    from app.services.automation.ig_iphone.interact.publish import publish_reel
    from app.services.automation.ig_iphone.media import push_media_via_mcp

    media_url = values.get("media_url")
    if media_url:
        result = await push_media_via_mcp(drv, media_url, log=log)
        if not result:
            return False, "ig_reel_post: échec pipeline média"
        await asyncio.sleep(2.0)

    caption = values.get("caption", "")
    stats = await publish_reel(drv, nav, caption=caption, log=log)

    published = stats.get("published", False)
    msg = "Reel publié" if published else "Reel : échec publication"
    if caption and published:
        msg += f" ({len(caption)} chars)"
    return published, msg


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_login")
async def _login(drv, nav, sess, values, log):
    """Force login attempt (handled by DeviceSession.ensure_login above)."""
    log("   [ig_login] Connexion réussie")
    return True, "Connecté"


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_config")
async def _config(drv, nav, sess, values, log):
    """Apply profile config changes."""
    from app.services.automation.ig_iphone.config.profile_config import configure_profile
    result = await configure_profile(drv, nav, log=log, **values)
    if result:
        return True, "Profil configuré"
    return False, "ig_config : échec de la configuration"


@_handler("ig_switch_pro")
async def _switch_pro(drv, nav, sess, values, log):
    """Switch to professional account."""
    from app.services.automation.ig_iphone.config.switch_pro import switch_to_pro
    category = values.get("category", "Artiste")
    account_type = values.get("account_type", "Creator")
    ok = await switch_to_pro(drv, nav, category=category, account_type=account_type, log=log)
    return ok, "Compte pro activé" if ok else "Switch pro : échec"


# ══════════════════════════════════════════════════════════════════════════════
#  HIGHLIGHTS
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_highlight_create")
async def _highlight_create(drv, nav, sess, values, log):
    from app.services.automation.ig_iphone.config.highlights import create_highlight
    name = values.get("name", "Highlight")
    story_indices = values.get("story_indices")
    ok = await create_highlight(drv, nav, name=name, story_indices=story_indices, log=log)
    return ok, f"Highlight '{name}' créé" if ok else "Highlight : échec création"


@_handler("ig_highlight_modify")
async def _highlight_modify(drv, nav, sess, values, log):
    from app.services.automation.ig_iphone.config.highlights import modify_highlight
    idx = values.get("index", 0)
    new_name = values.get("new_name")
    ok = await modify_highlight(drv, nav, highlight_index=idx, new_name=new_name, log=log)
    return ok, "Highlight modifié" if ok else "Highlight : échec modification"


@_handler("ig_highlight_delete")
async def _highlight_delete(drv, nav, sess, values, log):
    from app.services.automation.ig_iphone.config.highlights import delete_highlight
    idx = values.get("index", 0)
    ok = await delete_highlight(drv, nav, highlight_index=idx, log=log)
    return ok, "Highlight supprimé" if ok else "Highlight : échec suppression"


# ══════════════════════════════════════════════════════════════════════════════
#  BANNERS
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_banner_add")
async def _banner_add(drv, nav, sess, values, log):
    banner_type = values.get("type", "music")
    if banner_type == "music":
        from app.services.automation.ig_iphone.config.banners import add_music_banner
        song = values.get("song")
        ok = await add_music_banner(drv, nav, song=song, log=log)
    else:
        from app.services.automation.ig_iphone.config.banners import add_fill_banner
        text_content = values.get("text", "")
        ok = await add_fill_banner(drv, nav, text_content=text_content, log=log)
    return ok, "Bannière ajoutée" if ok else "Bannière : échec ajout"


@_handler("ig_banner_modify")
async def _banner_modify(drv, nav, sess, values, log):
    from app.services.automation.ig_iphone.config.banners import modify_banner
    banner_text = values.get("banner_text", "")
    new_content = values.get("new_content")
    ok = await modify_banner(drv, nav, banner_text=banner_text, new_content=new_content, log=log)
    return ok, "Bannière modifiée" if ok else "Bannière : échec modification"


@_handler("ig_banner_remove")
async def _banner_remove(drv, nav, sess, values, log):
    from app.services.automation.ig_iphone.config.banners import remove_banner
    banner_text = values.get("banner_text", "")
    ok = await remove_banner(drv, nav, banner_text=banner_text, log=log)
    return ok, "Bannière supprimée" if ok else "Bannière : échec suppression"


# ══════════════════════════════════════════════════════════════════════════════
#  MEDIA IMPORT
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_media_import")
async def _media_import(drv, nav, sess, values, log):
    """Import media from R2/URL to device gallery."""
    from app.services.automation.ig_iphone.media import push_media_via_mcp

    media_urls = values.get("media_urls", [])
    if not media_urls:
        return False, "ig_media_import: media_urls requis"

    imported = 0
    errors = 0
    for url in media_urls:
        result = await push_media_via_mcp(drv, url, log=log)
        if result:
            imported += 1
        else:
            errors += 1

    if imported == 0:
        return False, f"ig_media_import: aucun média importé ({errors} erreurs)"
    msg = f"{imported} média(s) importé(s)"
    if errors:
        msg += f" ({errors} erreurs)"
    return True, msg


# ══════════════════════════════════════════════════════════════════════════════
#  STORY STICKER
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_story_sticker")
async def _story_sticker(drv, nav, sess, values, log):
    """Add a sticker to a story in creation."""
    sticker_type = values.get("sticker_type", "link")

    from app.services.automation.ig_iphone.interact import story_stickers as ss

    if sticker_type == "link":
        ok = await ss.add_link_sticker(drv, url=values.get("url", ""), text=values.get("text"), log=log)
    elif sticker_type == "poll":
        ok = await ss.add_poll_sticker(drv, question=values.get("question", ""), options=values.get("options"), log=log)
    elif sticker_type == "question":
        ok = await ss.add_question_sticker(drv, question=values.get("question"), log=log)
    elif sticker_type == "location":
        ok = await ss.add_location_sticker(drv, location=values.get("location", ""), log=log)
    elif sticker_type == "music":
        ok = await ss.add_music_sticker(drv, song=values.get("song"), artist=values.get("artist"), log=log)
    else:
        return False, f"ig_story_sticker: type inconnu '{sticker_type}'"

    return ok, f"Sticker {sticker_type} ajouté" if ok else f"Sticker {sticker_type} : échec"


# ══════════════════════════════════════════════════════════════════════════════
#  FRONTEND ALIASES
# ══════════════════════════════════════════════════════════════════════════════
# The Scenarios frontend stores short identifiers (igi_feed, igi_prof, …)
# that differ from the canonical handler names.

_ALIASES: dict[str, str] = {
    "igi_feed":  "ig_feed",
    "igi_prof":  "ig_profile",
    "igi_reels": "ig_reels",
    "igi_conf":  "ig_config",
    "igi_camp":  "ig_post",
}

for _alias, _canonical in _ALIASES.items():
    if _canonical in TASK_HANDLERS:
        TASK_HANDLERS[_alias] = TASK_HANDLERS[_canonical]
