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
import os
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
from app.services.dispatch import _ssh_exec

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


# ── Media transfer ───────────────────────────────────────────────────────────

async def _transfer_media_to_iphone(
    ssh_port: int,
    local_path: str,
    *,
    log: Callable = logger.info,
) -> str | None:
    """Transfer a media file from VPS to iPhone via SCP over SSH tunnel.

    The file is placed in /var/mobile/Media/DCIM/100APPLE/ on the iPhone
    so it appears in the Camera Roll.

    Returns the remote path on success, None on failure.
    """
    filename = os.path.basename(local_path)
    remote_dir = "/var/mobile/Media/DCIM/100APPLE"
    remote_path = f"{remote_dir}/{filename}"

    # Ensure target dir exists
    await _ssh_exec(ssh_port, f"mkdir -p {remote_dir}", timeout=5)

    # SCP the file
    log(f"   [media] transfert {filename} → iPhone")
    proc = await asyncio.create_subprocess_exec(
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
        "-o", "LogLevel=ERROR",
        "-P", str(ssh_port),
        local_path,
        f"root@127.0.0.1:{remote_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        log(f"   [media] SCP échoué: {err}")
        return None

    # Trigger iOS media library scan so the file appears in gallery
    await _ssh_exec(
        ssh_port,
        'su mobile -c "open com.apple.mobileslideshow" 2>/dev/null; '
        "sleep 1; "
        'killall -9 MobileSlideShow 2>/dev/null; '
        "true",
        timeout=10,
    )

    log(f"   [media] ✓ {filename} transféré")
    return remote_path


async def _download_r2_media(
    media_url: str,
    *,
    log: Callable = logger.info,
) -> str | None:
    """Download a media file from R2/URL to a local temp path.

    Returns local file path or None on failure.
    """
    import httpx
    import tempfile

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(media_url)
            resp.raise_for_status()

            # Determine extension from content-type
            ct = resp.headers.get("content-type", "")
            ext = ".jpg"
            if "video" in ct or "mp4" in ct:
                ext = ".mp4"
            elif "png" in ct:
                ext = ".png"
            elif "webp" in ct:
                ext = ".webp"
            elif "heic" in ct:
                ext = ".heic"

            tmp = tempfile.NamedTemporaryFile(
                suffix=ext, prefix="scale_media_", delete=False
            )
            tmp.write(resp.content)
            tmp.close()
            log(f"   [media] téléchargé {len(resp.content)} bytes → {tmp.name}")
            return tmp.name

    except Exception as e:
        log(f"   [media] erreur téléchargement R2: {e}")
        return None


# ── Post publication ─────────────────────────────────────────────────────────

@_handler("ig_post")
async def _publish_post(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Publish an IG post (photo, video, or carousel).

    values:
        media_urls: list[str]   — R2 URLs of media to post
        media_paths: list[str]  — local VPS paths (alternative to URLs)
        caption: str            — post caption (with hashtags)
        location: str | None    — location name to tag
        post_type: str          — "photo", "video", "carousel" (auto-detected if 1 media)
    """
    media_urls = values.get("media_urls", [])
    media_paths = values.get("media_paths", [])
    caption = values.get("caption", "")
    location = values.get("location")

    if not media_urls and not media_paths:
        return False, "ig_post: media_urls ou media_paths requis"

    # Step 1: Download from R2 if needed, then transfer to iPhone
    local_files = list(media_paths)
    for url in media_urls:
        local = await _download_r2_media(url, log=log)
        if not local:
            return False, f"ig_post: échec téléchargement {url}"
        local_files.append(local)

    # Step 2: Transfer each file to iPhone
    for f in local_files:
        remote = await _transfer_media_to_iphone(sess.ssh_port, f, log=log)
        if not remote:
            return False, f"ig_post: échec transfert {os.path.basename(f)} vers iPhone"

    # Cleanup R2 downloads (not user-provided paths)
    for url in media_urls:
        for f in local_files[len(media_paths):]:
            try:
                os.unlink(f)
            except OSError:
                pass

    # Step 3: Wait for media to appear in gallery
    await asyncio.sleep(2.0)

    # Step 4: UI automation — create new post
    log("   [ig_post] ouverture flow de publication...")

    # Tap the "+" create button (center of bottom bar or "Créer" / "Create")
    await drv.refresh_elements()
    tapped = (
        await drv.tap_element("Nouveau post", contains=True, refresh=False)
        or await drv.tap_element("Créer", contains=True, refresh=False)
        or await drv.tap_element("Create", contains=True, refresh=False)
    )

    if not tapped:
        # Fallback: tap the center bottom "+" button
        await drv.ht._ensure_screen()
        await drv.ht.tap(drv.ht.screen_w / 2, drv.ht.screen_h * 0.96)

    await asyncio.sleep(1.5)

    # If a menu appears (Post, Reel, Story), tap "Post" / "Publication"
    await drv.refresh_elements()
    all_text = " ".join((e.get("text") or "").lower() for e in drv.elements)
    if "publication" in all_text or "post" in all_text:
        tapped = (
            await drv.tap_element("Publication", refresh=False)
            or await drv.tap_element("Post", refresh=False)
        )
        if tapped:
            await asyncio.sleep(1.5)

    # Step 5: Gallery selection — tap first (most recent) photo/video
    log("   [ig_post] sélection du média dans la galerie...")
    await drv.refresh_elements()

    # For carousel (multiple media), we'd need to tap "Sélection multiple"
    is_carousel = len(local_files) > 1
    if is_carousel:
        multi = (
            await drv.tap_element("Sélection multiple", contains=True, refresh=False)
            or await drv.tap_element("Select Multiple", contains=True, refresh=False)
        )
        await asyncio.sleep(0.5)

    # Tap the first gallery thumbnail (usually top-left of grid)
    # The gallery grid starts below the preview area
    await drv.ht._ensure_screen()
    grid_y = drv.ht.screen_h * 0.62  # gallery grid area
    cell_w = drv.ht.screen_w / 4
    for i in range(min(len(local_files), 10)):
        col = i % 4
        row = i // 4
        x = cell_w * col + cell_w / 2
        y = grid_y + row * cell_w + cell_w / 2
        await drv.ht.tap(x, y)
        await asyncio.sleep(0.4)

    # Step 6: Tap "Suivant" / "Next"
    log("   [ig_post] validation sélection...")
    await asyncio.sleep(0.5)
    tapped = (
        await drv.tap_element("Suivant")
        or await drv.tap_element("Next")
    )
    if not tapped:
        # Tap top-right area (where Next usually is)
        await drv.ht.tap(drv.ht.screen_w * 0.92, 50)
    await asyncio.sleep(1.5)

    # Step 7: Skip filter/edit screen → "Suivant" again
    tapped = (
        await drv.tap_element("Suivant")
        or await drv.tap_element("Next")
    )
    if not tapped:
        await drv.ht.tap(drv.ht.screen_w * 0.92, 50)
    await asyncio.sleep(1.5)

    # Step 8: Type caption
    if caption:
        log(f"   [ig_post] saisie légende ({len(caption)} chars)...")
        await drv.refresh_elements()
        caption_field = (
            drv.find_element("légende", contains=True)
            or drv.find_element("caption", contains=True)
            or drv.find_element("Écrire une légende", contains=True)
            or drv.find_element("Write a caption", contains=True)
        )

        if caption_field:
            x = caption_field.get("x", 0)
            y = caption_field.get("y", 0)
            await drv.ht.tap(x, y)
        else:
            # Tap at typical caption position
            await drv.ht.tap_pos(0.5, 0.25)

        await asyncio.sleep(0.5)
        await drv.ht.type_text(caption, interval=random.randint(20, 50))
        await asyncio.sleep(0.5)

    # Step 9: Add location if specified
    if location:
        log(f"   [ig_post] ajout lieu: {location}")
        tapped = (
            await drv.tap_element("Ajouter un lieu", contains=True)
            or await drv.tap_element("Add Location", contains=True)
            or await drv.tap_element("lieu", contains=True)
        )
        if tapped:
            await asyncio.sleep(1.0)
            await drv.ht.type_text(location, interval=random.randint(40, 80))
            await asyncio.sleep(1.5)
            # Tap first search result
            await drv.refresh_elements()
            location_result = drv.find_element(location, contains=True)
            if location_result:
                x = location_result.get("x", 0)
                y = location_result.get("y", 0)
                await drv.ht.tap(x, y)
                await asyncio.sleep(0.5)

    # Step 10: Share!
    log("   [ig_post] publication...")
    tapped = (
        await drv.tap_element("Partager")
        or await drv.tap_element("Share")
        or await drv.tap_element("Publier")
    )
    if not tapped:
        await drv.ht.tap(drv.ht.screen_w * 0.92, 50)

    # Wait for upload
    await asyncio.sleep(5.0)

    # Verify we're back on feed
    screen = await drv.detect_current_screen()
    if screen in ("feed", "own_profile"):
        msg = f"Post publié ({len(local_files)} média(s))"
        if caption:
            msg += f", légende {len(caption)} chars"
        log(f"   [ig_post] ✓ {msg}")
        return True, msg

    # Might still be uploading
    log("   [ig_post] upload en cours, attente...")
    await asyncio.sleep(10.0)
    screen = await drv.detect_current_screen()
    if screen in ("feed", "own_profile", "explore"):
        return True, f"Post publié ({len(local_files)} média(s))"

    return False, f"ig_post: état post-publication incertain (écran: {screen})"


@_handler("ig_story_post")
async def _publish_story(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Publish an IG story.

    values:
        media_url: str     — R2 URL of media (photo or video, max 15s)
        media_path: str    — local VPS path (alternative)
        stickers: list     — sticker config (optional, future)
        text: str          — text overlay (optional)
    """
    media_url = values.get("media_url")
    media_path = values.get("media_path")

    if not media_url and not media_path:
        return False, "ig_story_post: media_url ou media_path requis"

    # Download + transfer
    if media_url and not media_path:
        media_path = await _download_r2_media(media_url, log=log)
        if not media_path:
            return False, f"ig_story_post: échec téléchargement {media_url}"

    remote = await _transfer_media_to_iphone(sess.ssh_port, media_path, log=log)
    if not remote:
        return False, "ig_story_post: échec transfert média vers iPhone"

    # Cleanup temp download
    if media_url:
        try:
            os.unlink(media_path)
        except OSError:
            pass

    await asyncio.sleep(2.0)

    # UI automation: open story creation
    log("   [ig_story] ouverture création de story...")

    # Navigate to feed first
    await drv.go_home()
    await asyncio.sleep(1.0)

    # Tap own story avatar or "Votre story" / camera icon
    tapped = (
        await drv.tap_element("Votre story", contains=True)
        or await drv.tap_element("Your story", contains=True)
    )

    if not tapped:
        # Tap camera icon (top-left) or "+" on story tray
        await drv.ht._ensure_screen()
        await drv.ht.tap(40, 100)  # camera icon position

    await asyncio.sleep(1.5)

    # In story camera: tap gallery button (bottom-left) to select from gallery
    log("   [ig_story] sélection depuis galerie...")
    await drv.ht._ensure_screen()
    await drv.ht.tap(40, drv.ht.screen_h * 0.92)  # gallery thumbnail (bottom-left)
    await asyncio.sleep(1.5)

    # Select the most recent media (first item)
    await drv.ht.tap(drv.ht.screen_w * 0.13, drv.ht.screen_h * 0.22)
    await asyncio.sleep(1.0)

    # Add text overlay if specified
    text = values.get("text")
    if text:
        log(f"   [ig_story] ajout texte: {text[:30]}...")
        # Tap "Aa" text button
        tapped = await drv.tap_element("Aa", contains=True)
        if tapped:
            await asyncio.sleep(0.5)
            await drv.ht.type_text(text, interval=random.randint(30, 60))
            await asyncio.sleep(0.3)
            # Tap "OK" / "Terminé"
            await drv.tap_element("Terminé") or await drv.tap_element("Done")
            await asyncio.sleep(0.5)

    # Share story: tap "Votre story" button or "Partager"
    log("   [ig_story] publication story...")
    tapped = (
        await drv.tap_element("Votre story", contains=True)
        or await drv.tap_element("Your Story", contains=True)
        or await drv.tap_element("Partager", contains=True)
        or await drv.tap_element("Share", contains=True)
    )

    if not tapped:
        # Bottom send button
        await drv.ht.tap(drv.ht.screen_w * 0.5, drv.ht.screen_h * 0.92)

    await asyncio.sleep(4.0)

    screen = await drv.detect_current_screen()
    if screen in ("feed", "own_profile", "story"):
        log("   [ig_story] ✓ Story publiée")
        return True, "Story publiée"

    return False, f"ig_story_post: état post-publication incertain (écran: {screen})"


@_handler("ig_reel_post")
async def _publish_reel(
    drv: IGDriver,
    sess: DeviceSession,
    values: dict,
    log: Callable,
) -> tuple[bool, str]:
    """Publish an IG reel.

    values:
        media_url: str     — R2 URL of video (up to 90s)
        media_path: str    — local VPS path
        caption: str       — reel caption with hashtags
        audio: str | None  — audio name to use (optional)
        cover_time: float  — timestamp for cover photo (optional)
    """
    media_url = values.get("media_url")
    media_path = values.get("media_path")
    caption = values.get("caption", "")

    if not media_url and not media_path:
        return False, "ig_reel_post: media_url ou media_path requis"

    # Download + transfer
    if media_url and not media_path:
        media_path = await _download_r2_media(media_url, log=log)
        if not media_path:
            return False, f"ig_reel_post: échec téléchargement {media_url}"

    remote = await _transfer_media_to_iphone(sess.ssh_port, media_path, log=log)
    if not remote:
        return False, "ig_reel_post: échec transfert vidéo vers iPhone"

    if media_url:
        try:
            os.unlink(media_path)
        except OSError:
            pass

    await asyncio.sleep(2.0)

    # UI automation: create reel
    log("   [ig_reel] ouverture création de reel...")

    # Tap "+" create button
    await drv.refresh_elements()
    tapped = (
        await drv.tap_element("Nouveau post", contains=True, refresh=False)
        or await drv.tap_element("Créer", contains=True, refresh=False)
        or await drv.tap_element("Create", contains=True, refresh=False)
    )

    if not tapped:
        await drv.ht._ensure_screen()
        await drv.ht.tap(drv.ht.screen_w / 2, drv.ht.screen_h * 0.96)

    await asyncio.sleep(1.5)

    # Select "Reel" from the creation menu
    await drv.refresh_elements()
    tapped = (
        await drv.tap_element("Reel", refresh=False)
        or await drv.tap_element("Reels", refresh=False)
    )
    if tapped:
        await asyncio.sleep(1.5)

    # Select video from gallery (bottom-left gallery picker)
    log("   [ig_reel] sélection vidéo depuis galerie...")
    await drv.ht._ensure_screen()
    await drv.ht.tap(40, drv.ht.screen_h * 0.92)
    await asyncio.sleep(1.5)

    # Tap first (most recent) video
    await drv.ht.tap(drv.ht.screen_w * 0.13, drv.ht.screen_h * 0.22)
    await asyncio.sleep(1.5)

    # Tap "Ajouter" / "Add" to confirm video selection
    tapped = (
        await drv.tap_element("Ajouter")
        or await drv.tap_element("Add")
        or await drv.tap_element("Suivant")
        or await drv.tap_element("Next")
    )
    if not tapped:
        await drv.ht.tap(drv.ht.screen_w * 0.92, 50)
    await asyncio.sleep(1.5)

    # Skip edit screen → "Suivant"
    tapped = (
        await drv.tap_element("Suivant")
        or await drv.tap_element("Next")
        or await drv.tap_element("Aperçu")
        or await drv.tap_element("Preview")
    )
    if not tapped:
        await drv.ht.tap(drv.ht.screen_w * 0.92, 50)
    await asyncio.sleep(1.5)

    # Another "Suivant" may appear (audio, effects page)
    tapped = (
        await drv.tap_element("Suivant")
        or await drv.tap_element("Next")
    )
    if tapped:
        await asyncio.sleep(1.5)

    # Type caption
    if caption:
        log(f"   [ig_reel] saisie légende ({len(caption)} chars)...")
        await drv.refresh_elements()
        caption_field = (
            drv.find_element("légende", contains=True)
            or drv.find_element("caption", contains=True)
            or drv.find_element("Écrire une légende", contains=True)
        )

        if caption_field:
            x = caption_field.get("x", 0)
            y = caption_field.get("y", 0)
            await drv.ht.tap(x, y)
        else:
            await drv.ht.tap_pos(0.5, 0.25)

        await asyncio.sleep(0.5)
        await drv.ht.type_text(caption, interval=random.randint(20, 50))
        await asyncio.sleep(0.5)

    # Share
    log("   [ig_reel] publication reel...")
    tapped = (
        await drv.tap_element("Partager")
        or await drv.tap_element("Share")
        or await drv.tap_element("Publier")
    )
    if not tapped:
        await drv.ht.tap(drv.ht.screen_w * 0.92, 50)

    # Wait for upload (reels take longer)
    await asyncio.sleep(8.0)

    screen = await drv.detect_current_screen()
    if screen in ("feed", "own_profile", "reels"):
        log("   [ig_reel] ✓ Reel publié")
        return True, f"Reel publié" + (f", légende {len(caption)} chars" if caption else "")

    # Might still be processing
    log("   [ig_reel] traitement en cours, attente...")
    await asyncio.sleep(15.0)
    screen = await drv.detect_current_screen()
    if screen in ("feed", "own_profile", "reels", "explore"):
        return True, "Reel publié"

    return False, f"ig_reel_post: état post-publication incertain (écran: {screen})"


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
    """Import media from R2/URL to device gallery.

    values:
        media_urls: list[str]   — R2 URLs of media to import
        media_paths: list[str]  — local VPS paths (alternative)
    """
    media_urls = values.get("media_urls", [])
    media_paths = values.get("media_paths", [])

    if not media_urls and not media_paths:
        return False, "ig_media_import: media_urls ou media_paths requis"

    imported = 0
    errors = 0

    # Download from R2 first
    local_files = list(media_paths)
    for url in media_urls:
        local = await _download_r2_media(url, log=log)
        if local:
            local_files.append(local)
        else:
            errors += 1

    # Transfer each to iPhone
    for f in local_files:
        remote = await _transfer_media_to_iphone(sess.ssh_port, f, log=log)
        if remote:
            imported += 1
        else:
            errors += 1

    # Cleanup temp downloads
    for f in local_files[len(media_paths):]:
        try:
            os.unlink(f)
        except OSError:
            pass

    if imported == 0:
        return False, f"ig_media_import: aucun média importé ({errors} erreurs)"

    return True, f"{imported} média(s) importé(s) sur l'iPhone" + (
        f" ({errors} erreurs)" if errors else ""
    )


# ── Story sticker ────────────────────────────────────────────────────────────

@_handler("ig_story_sticker")
async def _story_sticker(drv, sess, values, log):
    return False, "ig_story_sticker pas encore implémenté"


# ── Frontend action-name aliases ─────────────────────────────────────────────
# The Scenarios frontend stores short identifiers (igi_feed, igi_prof, …)
# that differ from the canonical handler names. Register aliases so the
# engine can dispatch them without a mapping layer.

_ALIASES: dict[str, str] = {
    "igi_feed":  "ig_feed",
    "igi_prof":  "ig_profile",
    "igi_reels": "ig_reels",
    "igi_conf":  "ig_config",
    "igi_camp":  "ig_post",      # campaign enrollment → posting handler
}

for _alias, _canonical in _ALIASES.items():
    if _canonical in TASK_HANDLERS:
        TASK_HANDLERS[_alias] = TASK_HANDLERS[_canonical]
