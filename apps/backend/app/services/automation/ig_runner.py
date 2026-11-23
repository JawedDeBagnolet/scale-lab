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


# ── Session extraction after login ─────────────────────────────────────

async def _maybe_extract_session(sess, log):
    """After login, extract and store the API session for all comptes.

    ScaleTweak writes /tmp/scale_session.json 15s after app launch.
    We read it, verify it, and store it in Compte.session_data so:
    - Scraper comptes: IGScraperClient can use it for private API calls
    - Regular comptes: profile-live can use the account's own session
      for accurate pro status, category, etc.
    """
    try:
        from app.db import AsyncSessionLocal
        from app.models.compte import Compte

        async with AsyncSessionLocal() as db:
            compte = await db.get(Compte, sess.compte_id)
            if not compte:
                return

        is_scraper = compte.is_scraper
        tag = "[scraper]" if is_scraper else "[session]"
        log(f"   {tag} extraction de session après login...")
        from app.services.session_extract import extract_and_store
        session = await extract_and_store(
            str(sess.compte_id),
            mcp_port=sess.ctx.get("mcp_port", 8090),
            ssh_port=sess.ctx.get("ssh_port", 2223),
            host=sess.ctx.get("host", "127.0.0.1"),
            platform="ig",
        )
        if session:
            log(f"   {tag} ✓ session extraite et stockée (ds_user_id={session.get('ds_user_id', '?')})")
            from app.services.comptes import _log as emit_log
            await emit_log("comptes", "session", "success", compte.handle, f"Session extraite — ds_user_id={session.get('ds_user_id', '?')}")
        else:
            log(f"   {tag} ⚠ extraction de session échouée — sera réessayé au prochain login")
            from app.services.comptes import _log as emit_log
            await emit_log("comptes", "session", "error", compte.handle, "Extraction de session échouée après login", code="SESSION_EXTRACT_FAILED")
            # Only mark scraper accounts as needing reconnection
            if is_scraper:
                async with AsyncSessionLocal() as db2:
                    c = await db2.get(Compte, sess.compte_id)
                    if c:
                        c.status = "session"
                        await db2.commit()
                        log(f"   {tag} statut mis à jour → session (à reconnecter)")
    except Exception as e:
        log(f"   [session] ⚠ erreur extraction session: {str(e)[:150]}")
        try:
            from app.services.comptes import _log as emit_log
            await emit_log("comptes", "session", "error", str(sess.compte_id), f"Erreur extraction session: {str(e)[:150]}", code="SESSION_EXTRACT_ERROR")
        except Exception:
            pass


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

            # Change RTI posture for this session (randomizes gravity/motion)
            await drv.ht.change_posture()

            # Ensure login
            await sess.ensure_login(drv, None)

            # Extract & store session ONLY on explicit login tasks (not every run)
            # Avoids consuming proxy credits for session extraction on routine tasks
            if action_type == "ig_login":
                await _maybe_extract_session(sess, log)

            _check_abort(abort_event)

            # Resolve behavior presets and apply overrides
            if preset_ids:
                from app.services.automation.ig_iphone.behavior.presets import (
                    resolve_behavior, apply_behavior,
                )
                behavior = await resolve_behavior(preset_ids=preset_ids, log=log)
                values = apply_behavior(dict(values), behavior, log=log)
                if behavior:
                    values["_preset_name"] = behavior.get("name", "")
                    values["_preset_id"] = behavior.get("id", "")

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
        import traceback
        tb = traceback.format_exc()
        logger.error("ig_runner error for %s/%s\n%s", compte_id, action_type, tb)
        log(f"[ig_runner] ✗ ERREUR: {str(e)[:200]}")
        log(tb)
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
    from app.services.automation.ig_iphone.media import push_media_to_gallery, cleanup_gallery_via_mtouch
    from app.config import settings

    # Resolve spoof context (market from persona)
    market = values.get("market", "FR")
    phone_id = values.get("phone_id", str(sess.compte_id))
    auth_header = "Bearer %s" % settings.api_secret

    # Transfer media to iPhone gallery (with EXIF spoof)
    media_urls = values.get("media_urls", [])
    media_count = 0
    if media_urls:
        for url in media_urls:
            result = await push_media_to_gallery(
                url, auth_header=auth_header, spoof=True,
                market=market, phone_id=phone_id, log=log,
            )
            if not result or not result.get("success"):
                return False, f"ig_post: échec pipeline média ({url[:40]})"
            media_count += 1
        await asyncio.sleep(2.0)

    caption = values.get("caption", "")
    location = values.get("location")
    first_comment = values.get("first_comment")
    audio_query = values.get("audio_query")
    username = values.get("username", "")
    photo_count = media_count if media_count else 1

    if photo_count > 1:
        stats = await publish_carousel(drv, nav, caption=caption, photo_count=photo_count, audio_query=audio_query, first_comment=first_comment, username=username, log=log)
    else:
        stats = await publish_feed_post(drv, nav, caption=caption, first_comment=first_comment, location=location, username=username, log=log)

    published = stats.get("published", False)

    # Auto-cleanup gallery after publication
    if published and media_count > 0:
        try:
            ok = await cleanup_gallery_via_mtouch(media_count, log=log)
            if ok:
                log("   ✓ galerie nettoyee (%d medias)" % media_count)
        except Exception:
            pass

    # Mini session feed post-publication (parait naturel)
    if published and values.get("feed_session", True):
        try:
            from app.services.automation.ig_iphone.interact.feed_session import run_feed_session
            feed_min = values.get("feed_duration_min", 1)  # minutes
            feed_max = values.get("feed_duration_max", 2)
            log("\n--- Session feed post-publication (%d-%d min) ---" % (feed_min, feed_max))
            feed_cfg = {"duration_min": feed_min, "duration_max": feed_max, "like_pct": 0.05}
            await run_feed_session(drv, nav, config=feed_cfg, log=log)
        except Exception as e:
            log("   ⚠ session feed echouee: %s" % str(e)[:100])

    msg = f"Post {'publié' if published else 'échoué'}"
    if caption:
        msg += f" ({len(caption)} chars)"
    return published, msg


@_handler("ig_story_post")
async def _publish_story(drv, nav, sess, values, log):
    """Publish a story."""
    from app.services.automation.ig_iphone.interact.publish import publish_story
    from app.services.automation.ig_iphone.media import push_media_to_gallery, cleanup_gallery_via_mtouch
    from app.config import settings

    media_url = values.get("media_url")
    pushed = False
    if media_url:
        result = await push_media_to_gallery(
            media_url, auth_header="Bearer %s" % settings.api_secret,
            spoof=True, market=values.get("market", "FR"),
            phone_id=values.get("phone_id", str(sess.compte_id)), log=log,
        )
        if not result or not result.get("success"):
            return False, "ig_story_post: échec pipeline média"
        pushed = True
        await asyncio.sleep(2.0)

    caption = values.get("text", values.get("caption"))
    stickers = values.get("stickers")
    stats = await publish_story(drv, nav, caption=caption, stickers=stickers, log=log)

    published = stats.get("published", False)
    if published and pushed:
        try:
            await cleanup_gallery_via_mtouch(1, log=log)
        except Exception:
            pass

    return published, "Story publiée" if published else "Story : échec publication"


@_handler("ig_reel_post")
async def _publish_reel(drv, nav, sess, values, log):
    """Publish a reel."""
    from app.services.automation.ig_iphone.interact.publish import publish_reel
    from app.services.automation.ig_iphone.media import push_media_to_gallery, cleanup_gallery_via_mtouch
    from app.config import settings

    media_url = values.get("media_url")
    pushed = False
    if media_url:
        result = await push_media_to_gallery(
            media_url, auth_header="Bearer %s" % settings.api_secret,
            spoof=True, market=values.get("market", "FR"),
            phone_id=values.get("phone_id", str(sess.compte_id)), log=log,
        )
        if not result or not result.get("success"):
            return False, "ig_reel_post: échec pipeline média"
        pushed = True
        await asyncio.sleep(2.0)

    caption = values.get("caption", "")
    audio_query = values.get("audio_query")
    username = values.get("username", "")
    stats = await publish_reel(drv, nav, caption=caption, audio_query=audio_query, username=username, log=log)

    published = stats.get("published", False)
    if published and pushed:
        try:
            await cleanup_gallery_via_mtouch(1, log=log)
        except Exception:
            pass

    # Mini session feed post-publication
    if published and values.get("feed_session", True):
        try:
            from app.services.automation.ig_iphone.interact.feed_session import run_feed_session
            feed_min = values.get("feed_duration_min", 1)
            feed_max = values.get("feed_duration_max", 2)
            log("\n--- Session feed post-publication (%d-%d min) ---" % (feed_min, feed_max))
            feed_cfg = {"duration_min": feed_min, "duration_max": feed_max, "like_pct": 0.05}
            await run_feed_session(drv, nav, config=feed_cfg, log=log)
        except Exception as e:
            log("   ⚠ session feed echouee: %s" % str(e)[:100])

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
#  Photo push helper (profile photo → Camera Roll)
# ══════════════════════════════════════════════════════════════════════════════

async def _push_profile_photo(photo_url: str, sess, log) -> bool:
    """Download profile photo from R2 and push to iPhone Camera Roll.

    Flow: R2 (via gateway auth) → VPS /tmp → SCP to iPhone → MTOUCH import

    Args:
        photo_url: Full URL to the media (e.g. https://api.scalelab.win/media/...)
        sess: DeviceSession with ctx containing mcp_port, ssh_port
        log: Logging callable

    Returns:
        True if the photo was successfully imported into Camera Roll.
    """
    import os
    import uuid as _uuid

    from app.config import settings
    from app.services.media_pipeline import transfer_to_iphone, import_to_gallery
    from app.services.dispatch import DEFAULT_SSH_PORT, DEFAULT_MCP_PORT

    mcp_port = sess.ctx.get("mcp_port", DEFAULT_MCP_PORT)
    ssh_port = sess.ctx.get("ssh_port", DEFAULT_SSH_PORT)

    # 1. Download from R2 via gateway (needs Bearer auth)
    tmp_dir = "/tmp/scale_media"
    os.makedirs(tmp_dir, exist_ok=True)

    ext = ".jpg"
    if ".png" in photo_url.lower():
        ext = ".png"
    elif ".webp" in photo_url.lower():
        ext = ".webp"
    local_path = f"{tmp_dir}/pp_{_uuid.uuid4().hex[:8]}{ext}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30, verify=False) as client:
            headers = {"Authorization": f"Bearer {settings.api_secret}"}
            resp = await client.get(photo_url, headers=headers, follow_redirects=True)
            if resp.status_code != 200:
                log("   [photo] download failed HTTP %d from %s" % (resp.status_code, photo_url[:60]))
                return False
            with open(local_path, "wb") as f:
                f.write(resp.content)

        size_kb = os.path.getsize(local_path) / 1024
        log("   [photo] downloaded %.0f KB" % size_kb)

        if size_kb < 1:
            log("   [photo] file too small (%.0f KB), aborting" % size_kb)
            return False

        # 2. Transfer to iPhone via SSH tunnel
        iphone_path = await transfer_to_iphone(local_path, ssh_port)
        if not iphone_path:
            log("   [photo] transfer to iPhone failed")
            return False
        log("   [photo] on iPhone: %s" % iphone_path)

        # 3. Import to Camera Roll via gallery service (port 8191) + MTOUCH fallback
        imported = await import_to_gallery(iphone_path, mcp_port, ssh_port)
        if imported:
            log("   [photo] ✓ imported to Camera Roll")
            await asyncio.sleep(2)  # let Photos index the new asset
            return True
        else:
            log("   [photo] ⚠ MTOUCH import failed")
            return False

    except Exception as e:
        log("   [photo] error: %s" % str(e)[:150])
        return False
    finally:
        # Cleanup VPS temp file
        try:
            if os.path.isfile(local_path):
                os.remove(local_path)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@_handler("ig_config")
async def _config(drv, nav, sess, values, log):
    """Apply profile config changes."""
    from app.services.automation.ig_iphone.config.profile_config import configure_profile
    config = values.get("config", values)

    # photo_url is handled inside configure_profile (push to gallery + spoof + UI selection)
    # Inject spoof context (market, phone_id) so configure_profile can pass them to the spoofer
    if isinstance(config, dict) and config.get("photo_url"):
        try:
            from app.db import async_session
            from app.models.compte import Compte
            from app.models.persona import Persona
            async with async_session() as db:
                compte = await db.get(Compte, sess.compte_id)
                if compte and compte.persona_id:
                    persona = await db.get(Persona, compte.persona_id)
                    if persona and persona.market:
                        config["market"] = persona.market
                config["phone_id"] = str(sess.compte_id)
        except Exception:
            pass  # defaults to FR in configure_profile

    requested = list(config.keys()) if isinstance(config, dict) else []
    # Remove spoof context keys from requested (they're not profile fields)
    for _k in ("market", "phone_id", "device"):
        if _k in requested:
            requested.remove(_k)
    # photo_url will become photo_index inside configure_profile — track it as photo_url
    if "photo_index" in requested:
        requested.remove("photo_index")
        requested.append("photo")
    result = await configure_profile(drv, nav, log=log, **values)
    if result:
        # Check actual values — False means the field was attempted but failed
        succeeded = [k for k, v in result.items() if v]
        failed = [k for k, v in result.items() if not v]
        # Also catch fields that were requested but not even attempted
        missing = [k for k in requested if k not in result]
        failed.extend(missing)
        if failed and not succeeded:
            return False, "Échec configuration: %s" % failed
        if failed:
            return False, "Profil partiellement configuré: %s OK, %s échoué" % (succeeded, failed)
        return True, "Profil configuré: %s" % succeeded
    return False, "ig_config: aucun champ configuré (demandés: %s)" % requested


@_handler("ig_screen_dump")
async def _screen_dump(drv, nav, sess, values, log):
    """Dump accessibility tree of all key screens for atlas building."""
    mode = values.get("mode", "current")
    if mode == "all":
        from app.services.automation.ig_iphone.config.screen_atlas import dump_all_screens
        results = await dump_all_screens(drv, nav, log=log)
        return True, "Atlas: %d écrans dumpés" % len(results)
    else:
        from app.services.automation.ig_iphone.config.screen_atlas import dump_current_screen
        await dump_current_screen(drv, nav, log=log)
        return True, "Dump écran courant OK"


@_handler("ig_switch_pro")
async def _switch_pro(drv, nav, sess, values, log):
    """Switch to professional account."""
    from app.services.automation.ig_iphone.config.switch_pro import switch_to_pro
    category = values.get("category", "Artiste")
    account_type = values.get("account_type", "Creator")
    ok = await switch_to_pro(drv, nav, category=category, account_type=account_type, log=log)
    return ok, "Compte pro activé" if ok else "Switch pro : échec"


@_handler("ig_enable_hd")
async def _enable_hd(drv, nav, sess, values, log):
    """Active l'upload en qualité optimale dans les paramètres IG."""
    from app.services.automation.ig_iphone.interact.settings import enable_hd_upload
    result = await enable_hd_upload(drv, nav, log=log)
    if result.get("already_enabled"):
        return True, "Upload HD : déjà activé"
    return result.get("success", False), "Upload HD : %s" % result.get("message", "inconnu")


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
