"""Campaign scheduler — background loop that dispatches posts for active campaigns.

Runs every 60s, checks active campaigns, and creates + dispatches publications
when it's time based on the campaign's planning config.

Planning config (JSONB):
    mode: "rotation" | "proba"      — content selection mode
    type: "post" | "reel" | ...     — post type
    freq: int                       — posts per day per account
    from: int                       — earliest hour (0-23)
    to: int                         — latest hour (0-23)
    fromM: int                      — earliest minute of day
    toM: int                        — latest minute of day
    days: [bool] * 7                — active days (Mon=0..Sun=6)
    delay: int                      — min delay between accounts (minutes)

Usage:
    from app.services.campaign_scheduler import start_campaign_scheduler
    # Called once at app startup
    start_campaign_scheduler()
"""

import asyncio
import logging
import random
from datetime import datetime, UTC, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models.posting import Campagne, Collection, Publication, Media

logger = logging.getLogger("campaign_scheduler")

TICK_INTERVAL = 60  # seconds


# ── Content picker ───────────────────────────────────────────────────────────

def pick_content(collection: Collection, campaign: Campagne, mode: str = "rotation"):
    """Pick next media + caption from collection.

    Args:
        collection: Collection with media_ids and captions
        campaign: Campagne (for rotation_index tracking)
        mode: "rotation" (round-robin) or "proba" (weighted random)

    Returns:
        (media_ids: list[str], caption: str, new_rotation_index: int)
    """
    media_ids = collection.media_ids or []
    captions = collection.captions or []

    if not media_ids and not captions:
        return [], "", campaign.rotation_index

    post_type = campaign.post_type or collection.post_type or "post"

    if mode == "proba" or mode == "intelligent":
        # Weighted random — pick random media + random caption
        if media_ids:
            if post_type in ("carousel", "car"):
                # Carousel: pick 3-10 random media
                n = min(len(media_ids), random.randint(3, 10))
                selected_media = random.sample(media_ids, n)
            else:
                selected_media = [random.choice(media_ids)]
        else:
            selected_media = []
        caption = random.choice(captions) if captions else ""
        return selected_media, caption, campaign.rotation_index
    else:
        # Rotation — round-robin through media, cycle captions
        idx = campaign.rotation_index or 0

        if post_type in ("carousel", "car"):
            # Carousel: pick consecutive chunk of media
            chunk = min(len(media_ids), random.randint(3, 8))
            selected_media = []
            for i in range(chunk):
                selected_media.append(media_ids[(idx + i) % len(media_ids)])
            new_idx = (idx + chunk) % max(len(media_ids), 1)
        elif media_ids:
            selected_media = [media_ids[idx % len(media_ids)]]
            new_idx = (idx + 1) % len(media_ids)
        else:
            selected_media = []
            new_idx = idx

        caption = captions[idx % len(captions)] if captions else ""
        return selected_media, caption, new_idx


# ── Scheduling logic ─────────────────────────────────────────────────────────

def should_post_now(campaign: Campagne, now: datetime) -> bool:
    """Check if a campaign should post right now based on its planning."""
    planning = campaign.planning or {}

    # Check active days (Mon=0..Sun=6)
    days = planning.get("days")
    if days and isinstance(days, list) and len(days) >= 7:
        weekday = now.weekday()
        if not days[weekday]:
            return False

    # Check time window
    from_h = planning.get("from", 8)
    to_h = planning.get("to", 22)
    hour = now.hour
    if hour < from_h or hour >= to_h:
        return False

    # Check frequency — how many posts today vs target
    freq = planning.get("freq", 1)
    if freq <= 0:
        return False

    # Calculate posts already done today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # This is checked per-tick, we approximate by checking last_posted_at
    if campaign.last_posted_at:
        last = campaign.last_posted_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)

        # Same day? Check if we've hit the daily limit
        if last.date() == now.date():
            # Approximate: space posts evenly across the window
            window_hours = max(to_h - from_h, 1)
            interval_minutes = (window_hours * 60) / freq
            elapsed = (now - last).total_seconds() / 60
            if elapsed < interval_minutes:
                return False

    # Check delay between accounts
    delay = planning.get("delay", 0)
    if delay > 0 and campaign.last_posted_at:
        last = campaign.last_posted_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if (now - last).total_seconds() < delay * 60:
            return False

    return True


def pick_account(campaign: Campagne) -> str | None:
    """Pick the next account to post from."""
    accounts = campaign.accounts or []
    if not accounts:
        return None

    # Simple rotation through accounts
    idx = (campaign.post_count or 0) % len(accounts)
    return accounts[idx]


# ── Main scheduler loop ──────────────────────────────────────────────────────

async def _tick():
    """One scheduler tick — check all active campaigns."""
    async with AsyncSessionLocal() as db:
        # Fetch active campaigns with their collections
        result = await db.execute(
            select(Campagne).where(Campagne.status == "active")
        )
        campaigns = result.scalars().all()

        if not campaigns:
            return

        now = datetime.now(UTC)

        for camp in campaigns:
            try:
                if not should_post_now(camp, now):
                    continue

                # Load collection
                if not camp.collection_id:
                    logger.warning("campaign %s has no collection", camp.id)
                    continue

                coll = await db.get(Collection, camp.collection_id)
                if not coll:
                    logger.warning("campaign %s: collection %s not found",
                                   camp.id, camp.collection_id)
                    continue

                # Pick account
                account_id = pick_account(camp)
                if not account_id:
                    logger.warning("campaign %s has no accounts", camp.id)
                    continue

                # Pick content
                mode = (camp.planning or {}).get("mode", "rotation")
                media_ids, caption, new_idx = pick_content(coll, camp, mode)

                if not media_ids:
                    logger.warning("campaign %s: no media in collection", camp.id)
                    continue

                # Resolve media URLs
                media_urls = []
                for mid in media_ids:
                    try:
                        media = await db.get(Media, UUID(mid) if isinstance(mid, str) else mid)
                        if media and media.url:
                            media_urls.append(media.url)
                    except Exception:
                        pass

                if not media_urls:
                    logger.warning("campaign %s: no valid media URLs", camp.id)
                    continue

                # Determine post type
                post_type = camp.post_type or coll.post_type or "post"
                if post_type in ("car", "carousel") and len(media_urls) > 1:
                    post_type = "carousel"
                elif post_type in ("car", "carousel") and len(media_urls) == 1:
                    post_type = "post"

                # Create publication
                pub = Publication(
                    compte_id=UUID(account_id),
                    campagne_id=camp.id,
                    caption=caption,
                    post_type=post_type,
                    media_urls=media_urls,
                    status="planned",
                )
                db.add(pub)

                # Update campaign tracking
                camp.last_posted_at = now
                camp.post_count = (camp.post_count or 0) + 1
                camp.rotation_index = new_idx

                await db.commit()
                await db.refresh(pub)

                logger.info(
                    "campaign %s: created publication %s for @%s (%s, %d media)",
                    camp.name, pub.id, account_id, post_type, len(media_urls)
                )

                # Dispatch publication via the same path as the API
                from app.models.compte import Compte
                compte = await db.get(Compte, UUID(account_id))
                if not compte:
                    logger.error("campaign %s: compte %s not found", camp.id, account_id)
                    continue

                action_map = {"post": "ig_post", "story": "ig_story_post",
                              "reel": "ig_reel_post", "carousel": "ig_post"}
                action = action_map.get(post_type, "ig_post")

                values = {
                    "media_urls": media_urls if action == "ig_post" else None,
                    "media_url": media_urls[0] if action != "ig_post" else None,
                    "caption": caption,
                    "market": "FR",
                    "phone_id": str(compte.id),
                    "username": compte.handle,
                }
                values = {k: v for k, v in values.items() if v is not None}

                pub.status = "publishing"
                await db.commit()

                from app.api.posting import _run_publication
                asyncio.create_task(
                    _run_publication(pub.id, compte.id, compte.plateforme, action, values, compte.handle),
                    name=f"camp_{camp.name}_{pub.id}",
                )

            except Exception as e:
                logger.error("campaign %s tick error: %s", camp.id, e)


async def _scheduler_loop():
    """Background loop — ticks every TICK_INTERVAL seconds."""
    logger.info("campaign scheduler started (interval=%ds)", TICK_INTERVAL)
    while True:
        try:
            await _tick()
        except Exception as e:
            logger.error("campaign scheduler tick error: %s", e)
        await asyncio.sleep(TICK_INTERVAL)


def start_campaign_scheduler():
    """Start the campaign scheduler as a background task."""
    asyncio.ensure_future(_scheduler_loop())
    logger.info("campaign scheduler background task created")
