"""Story executor — connects the planner to the automation engine.

Takes a LoopSlot from story_planner and executes it end-to-end:
  1. Load template from DB
  2. Push media to iPhone gallery
  3. Apply template (open editor → stickers → position)
  4. Publish story
  5. Optionally add to highlight

Usage:
    from app.services.story_executor import execute_slot, execute_next

    # Execute a specific slot
    await execute_slot(db, driver, slot, iphone_config, log=print)

    # Execute the next pending slot for an account
    await execute_next(db, account_id, iphone_config)
"""

import asyncio
import logging
import random
from datetime import datetime, UTC
from typing import Any, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.posting import StoryTemplate, StoryCollection
from app.services.story_planner import LoopSlot, Variant
from app.services.media_pipeline import push_media
from app.services.automation.ig_driver import IGDriver
from app.services.automation.ig_iphone.interact.apply_template import apply_template
from app.services.automation.ig_iphone.interact.story_stickers import (
    publish_story,
    add_to_highlight,
    open_story_editor,
)

logger = logging.getLogger("story_executor")


async def _load_template(db: AsyncSession, template_id: str) -> dict | None:
    """Load a StoryTemplate from DB and return as dict."""
    try:
        uid = UUID(template_id)
    except ValueError:
        logger.error("Invalid template_id: %s", template_id)
        return None

    result = await db.execute(
        select(StoryTemplate).where(StoryTemplate.id == uid)
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        logger.error("Template not found: %s", template_id)
        return None

    return {
        "id": str(tpl.id),
        "name": tpl.name,
        "story_type": tpl.story_type,
        "username": tpl.username,
        "color": tpl.color,
        "media_ids": tpl.media_ids or [],
        "bg_idx": tpl.bg_idx,
        "stickers": [
            {**s, "type": s.get("type", s.get("kind", "unknown"))}
            for s in (tpl.elements or [])
        ],
        "moments": tpl.moments or [],
        "context": "planner",
    }


async def _load_collection(db: AsyncSession, collection_id: str) -> dict | None:
    """Load a StoryCollection to get highlight info."""
    try:
        uid = UUID(collection_id)
    except ValueError:
        return None

    result = await db.execute(
        select(StoryCollection).where(StoryCollection.id == uid)
    )
    col = result.scalar_one_or_none()
    if not col:
        return None

    return {
        "id": str(col.id),
        "name": col.name,
        "kind": col.kind,
        "story_type": col.story_type,
    }


async def _resolve_media_url(db: AsyncSession, media_id: str) -> str | None:
    """Resolve a media_id to a downloadable URL.

    Media can be in the medias table (uploaded) or from a source URL.
    """
    from app.models.posting import Media
    try:
        uid = UUID(media_id)
    except ValueError:
        return None

    result = await db.execute(
        select(Media).where(Media.id == uid)
    )
    media = result.scalar_one_or_none()
    if not media:
        return None

    return media.url or media.cdn_url or media.source_url


async def execute_slot(
    db: AsyncSession,
    driver: IGDriver,
    slot: LoopSlot,
    iphone_config: dict,
    *,
    log: Callable = logger.info,
) -> dict:
    """Execute a single LoopSlot — full story publication pipeline.

    Args:
        db: async database session
        driver: IGDriver connected to the iPhone
        slot: planner slot with day, moment, variant
        iphone_config: {ssh_port, mcp_port, host, market, device_model, phone_id}
        log: logging function

    Returns:
        dict with execution result:
            ok: bool
            steps: list of step results
            error: str | None
    """
    variant = slot.variant
    steps = []

    log("=" * 50)
    log("execute_slot: day=%d, moment=%s, type=%s" % (
        slot.day, slot.moment, variant.story_type))
    log("  template=%s, media=%s" % (variant.template_id, variant.media_id))
    log("=" * 50)

    # 1. Load template
    log("[1/5] Loading template...")
    template = await _load_template(db, variant.template_id)
    if not template:
        return {"ok": False, "steps": steps, "error": "template_not_found"}
    steps.append({"step": "load_template", "ok": True, "name": template["name"]})
    log("  ✓ template: %s (%d stickers)" % (template["name"], len(template["stickers"])))

    # 2. Push media to iPhone gallery
    log("[2/5] Pushing media to iPhone...")
    media_url = await _resolve_media_url(db, variant.media_id)
    if not media_url:
        log("  ! media URL not found, using template bg_idx=%d" % template["bg_idx"])
        steps.append({"step": "push_media", "ok": False, "reason": "url_not_found"})
        # Continue anyway — template might use bg color
    else:
        try:
            iphone_path = await push_media(
                media_url,
                ssh_port=iphone_config.get("ssh_port", 2223),
                mcp_port=iphone_config.get("mcp_port", 18090),
                market=iphone_config.get("market", "FR"),
                device_model=iphone_config.get("device_model", "iPhone X"),
                phone_id=iphone_config.get("phone_id", "default"),
                host=iphone_config.get("host", "127.0.0.1"),
            )
            steps.append({"step": "push_media", "ok": True, "path": iphone_path})
            log("  ✓ media on iPhone: %s" % iphone_path)
        except Exception as e:
            log("  ! push_media failed: %s" % e)
            steps.append({"step": "push_media", "ok": False, "error": str(e)})
            # Continue — the latest gallery photo will be used

    # Human pause before opening Instagram
    await asyncio.sleep(random.uniform(1.0, 3.0))

    # 3. Open story editor and select photo
    log("[3/5] Opening story editor...")
    try:
        ok = await open_story_editor(driver, media_index=0, log=log)
        steps.append({"step": "open_editor", "ok": ok})
        if not ok:
            return {"ok": False, "steps": steps, "error": "editor_open_failed"}
        log("  ✓ story editor open")
    except Exception as e:
        log("  ! open_editor failed: %s" % e)
        steps.append({"step": "open_editor", "ok": False, "error": str(e)})
        return {"ok": False, "steps": steps, "error": str(e)}

    await asyncio.sleep(random.uniform(0.5, 1.5))

    # 4. Apply template (add stickers + position)
    log("[4/5] Applying template stickers...")
    try:
        stickers = template.get("stickers", [])
        real_stickers = [s for s in stickers
                         if s.get("type") not in ("media_placeholder", "repost_media")]

        for i, sticker in enumerate(real_stickers):
            stype = sticker.get("type", "?")
            log("  sticker %d/%d: %s" % (i + 1, len(real_stickers), stype))

            from app.services.automation.ig_iphone.interact.apply_template import (
                _add_and_position,
            )
            await _add_and_position(driver, sticker, log=log)
            await asyncio.sleep(random.uniform(0.5, 1.5))

        steps.append({"step": "apply_stickers", "ok": True,
                       "count": len(real_stickers)})
        log("  ✓ %d stickers applied" % len(real_stickers))
    except Exception as e:
        log("  ! apply_stickers failed: %s" % e)
        steps.append({"step": "apply_stickers", "ok": False, "error": str(e)})
        # Continue to try publishing even if stickers failed

    await asyncio.sleep(random.uniform(0.5, 2.0))

    # 5. Publish
    log("[5/5] Publishing story...")
    try:
        ok = await publish_story(driver, log=log)
        steps.append({"step": "publish", "ok": ok})
        if ok:
            log("  ✓ story published!")
        else:
            log("  ! publish failed")
            return {"ok": False, "steps": steps, "error": "publish_failed"}
    except Exception as e:
        log("  ! publish failed: %s" % e)
        steps.append({"step": "publish", "ok": False, "error": str(e)})
        return {"ok": False, "steps": steps, "error": str(e)}

    # 6. Optional: add to highlight (if collection is a highlight)
    collection = await _load_collection(db, variant.collection_id)
    if collection and collection.get("kind") == "hl":
        hl_name = collection.get("name", "")
        log("[bonus] Adding to highlight: %s" % hl_name)
        await asyncio.sleep(random.uniform(2.0, 4.0))
        try:
            # Open the story we just published
            await driver.ht.tap(60, 158)  # profile pic (story ring)
            await asyncio.sleep(3)

            ok = await add_to_highlight(
                driver, highlight_name=hl_name, create_new=False, log=log)
            steps.append({"step": "highlight", "ok": ok, "name": hl_name})
            if ok:
                log("  ✓ added to highlight '%s'" % hl_name)
        except Exception as e:
            log("  ! highlight failed: %s" % e)
            steps.append({"step": "highlight", "ok": False, "error": str(e)})

    log("=" * 50)
    log("execute_slot DONE")
    log("=" * 50)

    return {"ok": True, "steps": steps, "error": None}


async def execute_next(
    db: AsyncSession,
    account_id: str,
    iphone_config: dict,
    *,
    slots: list[LoopSlot] | None = None,
    current_day: int = 0,
    current_moment: str = "matin",
    log: Callable = logger.info,
) -> dict | None:
    """Find and execute the next pending slot for an account.

    If slots is provided, finds the first slot matching current_day + moment.
    Returns the execution result or None if no slot matches.
    """
    if not slots:
        log("No slots provided")
        return None

    # Find matching slot
    matching = [s for s in slots
                if s.day == current_day and s.moment == current_moment]
    if not matching:
        log("No slot for day=%d moment=%s" % (current_day, current_moment))
        return None

    slot = matching[0]

    # Create driver
    driver = IGDriver(
        mcp_port=iphone_config.get("mcp_port", 18090),
        host=iphone_config.get("host", "127.0.0.1"),
        log=log,
    )

    return await execute_slot(db, driver, slot, iphone_config, log=log)
