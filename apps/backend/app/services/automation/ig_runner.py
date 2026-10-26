"""Async IG runner — dispatches Instagram task types to the IGDriver.

Ported from VPS ig_runner.py. Each task type maps to a handler function
that uses DeviceSession + IGDriver to perform the action on the iPhone.

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
import random
from typing import Any, Callable
from uuid import UUID

from app.services.automation.device_session import (
    BUNDLE_INSTAGRAM,
    DeviceSession,
    DeviceLocked,
    DeviceUnavailable,
    LoginRequired,
)
from app.services.automation.ig_driver import IGDriver

logger = logging.getLogger("automation.ig_runner")

# ── Task dispatch table ──────────────────────────────────────────────────────

TASK_HANDLERS: dict[str, Callable] = {}


def _handler(name: str):
    """Decorator to register a task handler."""
    def wrap(fn):
        TASK_HANDLERS[name] = fn
        return fn
    return wrap


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_ig_task(
    compte_id: UUID,
    action_type: str,
    values: dict | None = None,
    preset_ids: list | None = None,
    *,
    log: Callable = logger.info,
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
            drv = IGDriver(mcp_port=sess.mcp_port, log=log)

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
        logger.exception("ig_runner error for %s/%s", compte_id, action_type)
        return False, f"Erreur : {str(e)[:200]}"


# ── Feed session ─────────────────────────────────────────────────────────────

@_handler("ig_feed")
async def _feed_session(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Browse IG feed with realistic scrolling and interactions."""
    duration = values.get("duration", 120)  # seconds
    like_prob = values.get("like_probability", 0.15)
    comment_prob = values.get("comment_probability", 0.03)

    log(f"   [ig_feed] session {duration}s, like={like_prob}, comment={comment_prob}")

    # Navigate to feed
    await drv.go_home()
    await drv.wait(1.0, 2.0)

    import time
    start = time.monotonic()
    posts_seen = 0
    likes = 0
    comments = 0

    while (time.monotonic() - start) < duration:
        # Scroll down
        await drv.scroll_down()
        await drv.wait(0.8, 2.5)

        # Detect posts
        posts = await drv.detect_visible_posts()
        posts_seen += len(posts)

        for post in posts:
            # Random like
            if random.random() < like_prob:
                centered = await drv.center_post(post)
                if centered:
                    await drv.like_post()
                    likes += 1
                    await drv.wait(0.5, 1.5)

            # Random comment
            if random.random() < comment_prob:
                comment_text = values.get("comment_text")
                if comment_text:
                    centered = await drv.center_post(post)
                    if centered:
                        await drv.type_comment(comment_text)
                        await drv.submit_comment()
                        comments += 1
                        await drv.wait(1.0, 3.0)

        # Reading pause
        await drv.reading_pause(random.randint(50, 200))

    msg = f"Feed : {posts_seen} posts, {likes} likes, {comments} comments en {duration}s"
    log(f"   [ig_feed] {msg}")
    return True, msg


# ── Reels session ────────────────────────────────────────────────────────────

@_handler("ig_reels")
async def _reels_session(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Browse IG reels."""
    duration = values.get("duration", 60)
    like_prob = values.get("like_probability", 0.10)

    await drv.go_reels()
    await drv.wait(1.0, 2.0)

    import time
    start = time.monotonic()
    reels_seen = 0
    likes = 0

    while (time.monotonic() - start) < duration:
        reels_seen += 1
        watch_time = random.uniform(3.0, 15.0)
        await asyncio.sleep(watch_time)

        if random.random() < like_prob:
            await drv.like_post()
            likes += 1
            await drv.wait(0.3, 0.8)

        # Swipe up to next reel
        await drv.ht.swipe(
            drv.ht.screen_w / 2,
            drv.ht.screen_h * 0.75,
            drv.ht.screen_w / 2,
            drv.ht.screen_h * 0.15,
            duration=random.randint(400, 800),
        )
        await drv.wait(0.5, 1.0)

    msg = f"Reels : {reels_seen} vus, {likes} likes en {duration}s"
    log(f"   [ig_reels] {msg}")
    return True, msg


# ── Story viewing ────────────────────────────────────────────────────────────

@_handler("ig_stories")
async def _stories_session(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """View stories from the feed story tray."""
    max_stories = values.get("max_stories", 10)

    await drv.go_home()
    await drv.wait(1.0, 2.0)

    # Tap first story in tray
    ok = await drv.open_story()
    if not ok:
        return True, "Pas de stories disponibles"

    await drv.wait(1.5, 3.0)
    stories_viewed = 0

    for _ in range(max_stories):
        screen = await drv.detect_current_screen()
        if screen != "story":
            break

        stories_viewed += 1
        # Watch story for realistic duration
        await asyncio.sleep(random.uniform(2.0, 6.0))
        # Next story
        await drv.next_story()
        await drv.wait(0.5, 1.0)

    # Close story
    await drv.close_story()
    await drv.wait(0.5, 1.0)

    msg = f"Stories : {stories_viewed} vues"
    log(f"   [ig_stories] {msg}")
    return True, msg


# ── Profile visit ────────────────────────────────────────────────────────────

@_handler("ig_profile")
async def _profile_visit(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Visit a user profile and optionally follow."""
    username = values.get("username")
    follow = values.get("follow", False)

    if not username:
        return False, "username requis pour ig_profile"

    # Navigate to search
    await drv.go_search()
    await drv.wait(0.5, 1.0)

    # Search for user
    await drv.tap_element("Rechercher", contains=True)
    await drv.wait(0.3, 0.5)
    await drv.ht.type_text(username)
    await drv.wait(1.0, 2.0)

    # Tap on the search result
    await drv.tap_element(username, contains=True)
    await drv.wait(1.5, 3.0)

    # Get profile stats
    stats = await drv.get_profile_stats()

    # Follow if requested
    if follow:
        await drv.follow_user()
        await drv.wait(0.5, 1.0)

    msg = f"Profil {username} visité"
    if stats:
        msg += f" ({stats.get('followers', '?')} followers)"
    if follow:
        msg += " + suivi"
    log(f"   [ig_profile] {msg}")
    return True, msg


# ── Post publication ─────────────────────────────────────────────────────────

@_handler("ig_post")
async def _publish_post(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Publish an IG post (photo, video, or carousel).

    This is a stub — the full publish flow requires:
    - Media import from R2 to device gallery
    - Gallery selection
    - Caption typing
    - Hashtag insertion
    - Location tagging
    - Sharing

    These need the VPS ig_iphone/interact/publish.py module.
    """
    log("   [ig_post] Publication — flow complet en attente des modules publish")
    # TODO: implement when ig_iphone/interact/publish.py is ported
    return False, "ig_post pas encore implémenté — modules publish nécessaires"


@_handler("ig_story_post")
async def _publish_story(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Publish an IG story."""
    log("   [ig_story_post] Story — flow complet en attente des modules publish")
    return False, "ig_story_post pas encore implémenté"


@_handler("ig_reel_post")
async def _publish_reel(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Publish an IG reel."""
    log("   [ig_reel_post] Reel — flow complet en attente des modules publish")
    return False, "ig_reel_post pas encore implémenté"


# ── Warmup ───────────────────────────────────────────────────────────────────

@_handler("ig_warmup")
async def _warmup(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Gentle account warmup — browse feed, view a few stories."""
    duration = values.get("duration", 90)

    log(f"   [ig_warmup] session {duration}s")

    # Short feed browse
    feed_result = await _feed_session(
        drv, sess,
        {"duration": int(duration * 0.6), "like_probability": 0.08, "comment_probability": 0},
        log,
    )

    # View a few stories
    story_result = await _stories_session(
        drv, sess,
        {"max_stories": 5},
        log,
    )

    msg = f"Warmup terminé ({duration}s)"
    log(f"   [ig_warmup] {msg}")
    return True, msg


# ── Login ────────────────────────────────────────────────────────────────────

@_handler("ig_login")
async def _login(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Force login attempt."""
    log("   [ig_login] Tentative de connexion")
    # Login is handled by DeviceSession.ensure_login
    # If we reach here, login was already successful
    return True, "Connecté"


# ── Config ───────────────────────────────────────────────────────────────────

@_handler("ig_config")
async def _config(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Apply profile config changes."""
    log("   [ig_config] Config — en attente des modules config")
    return False, "ig_config pas encore implémenté"


@_handler("ig_switch_pro")
async def _switch_pro(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Switch to professional account."""
    log("   [ig_switch_pro] Switch pro — en attente des modules config")
    return False, "ig_switch_pro pas encore implémenté"


# ── Highlights ───────────────────────────────────────────────────────────────

@_handler("ig_highlight_create")
async def _highlight_create(drv, sess, values, log):
    return False, "ig_highlight_create pas encore implémenté"


@_handler("ig_highlight_modify")
async def _highlight_modify(drv, sess, values, log):
    return False, "ig_highlight_modify pas encore implémenté"


@_handler("ig_highlight_delete")
async def _highlight_delete(drv, sess, values, log):
    return False, "ig_highlight_delete pas encore implémenté"


# ── Banners ──────────────────────────────────────────────────────────────────

@_handler("ig_banner_add")
async def _banner_add(drv, sess, values, log):
    return False, "ig_banner_add pas encore implémenté"


@_handler("ig_banner_modify")
async def _banner_modify(drv, sess, values, log):
    return False, "ig_banner_modify pas encore implémenté"


@_handler("ig_banner_remove")
async def _banner_remove(drv, sess, values, log):
    return False, "ig_banner_remove pas encore implémenté"


# ── Media import ─────────────────────────────────────────────────────────────

@_handler("ig_media_import")
async def _media_import(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Import media from R2 to device gallery.

    This needs the VPS media_transfer module for:
    - Download from R2
    - EXIF metadata spoofing
    - Gallery injection via crane
    """
    log("   [ig_media_import] Import — en attente du module media_transfer")
    return False, "ig_media_import pas encore implémenté"


# ── Story sticker ────────────────────────────────────────────────────────────

@_handler("ig_story_sticker")
async def _story_sticker(drv, sess, values, log):
    return False, "ig_story_sticker pas encore implémenté"
