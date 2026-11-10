"""
th_iphone/interact/feed_session.py — Session feed Threads (async).

Scroll naturel, likes, pause lecture, skip sponsorise.
Parametrable via un dict de config.

Usage:
    from ..interact.feed_session import run_feed_session
    await run_feed_session(driver, navigator, config={}, log=print)
"""

import asyncio
import random
import time
from datetime import datetime


DEFAULT_CONFIG = {
    "duration_min": 5,
    "duration_max": 10,
    "like_pct": 0.12,
    "double_tap_like_pct": 0.35,
    "reply_read_pct": 0.06,
    "repost_pct": 0.01,
    "follow_pct": 0.0,
    "visit_profile_pct": 0.04,
    "scroll_intensity": "normal",
    "read_pause_min": 1.0,
    "read_pause_max": 4.0,
    "scroll_back_pct": 0.05,
    "hesitate_like_pct": 0.3,
    "pause_long_pct": 0.08,
    "pause_long_min": 8.0,
    "pause_long_max": 20.0,
}


def _pick_intensity():
    return random.choices(
        ["light", "normal", "normal", "strong", "flick"],
        weights=[15, 40, 25, 15, 5],
    )[0]


async def run_feed_session(driver, navigator, config=None, task=None, log=print):
    """Execute une session feed Threads complete (async)."""

    # Presets are resolved and applied by th_runner before calling this function.
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    duration_s = random.uniform(cfg["duration_min"] * 60, cfg["duration_max"] * 60)

    stats = {
        "posts_seen": 0,
        "likes": 0,
        "reply_reads": 0,
        "reposts": 0,
        "follows": 0,
        "profile_visits": 0,
        "scroll_backs": 0,
        "behavior": behavior.get("name", "default") if behavior else "default",
        "started_at": datetime.now().isoformat(),
    }

    # Import anti-patterns
    from ..behavior.patterns import (
        scroll_back, pause_distraction, hesitate_before_action,
        slow_read_caption, browse_replies_slow, imprecise_scroll,
        random_profile_peek,
    )

    # Ensure on feed via helper
    if not await driver.ensure_screen("feed"):
        log("!! ABORT: impossible de trouver le feed")
        stats["aborted"] = True
        stats["abort_reason"] = "feed_not_found"
        return stats
    await asyncio.sleep(1)

    seen_users = set()
    start = time.time()
    log("-> Feed session Threads (%d-%d min)" % (cfg["duration_min"], cfg["duration_max"]))

    while (time.time() - start) < duration_s:
        # Parse visible posts
        posts = await driver.parse_visible_posts(refresh=True)

        for post in posts:
            if (time.time() - start) >= duration_s:
                break

            username = post.get("username", "?")

            # Skip deja vu
            if username in seen_users:
                continue
            seen_users.add(username)

            # Skip sponsorise
            if "sponsoris" in post.get("time_text", "").lower():
                log("   -> skip sponsorise @%s" % username)
                continue

            stats["posts_seen"] += 1

            # ── Lecture du post ────────────────────────────────────────
            read_time = random.uniform(cfg["read_pause_min"], cfg["read_pause_max"])
            if len(post.get("caption", "")) > 100:
                read_time *= random.uniform(1.2, 1.8)

            log("   [%d] @%s — %d likes, pause %.1fs" % (
                stats["posts_seen"], username, post.get("likes", 0), read_time))
            await asyncio.sleep(read_time)

            # ── Anti-patterns ──────────────────────────────────────────

            if random.random() < cfg["scroll_back_pct"]:
                await scroll_back(driver, log)
                stats["scroll_backs"] += 1

            if random.random() < 0.06:
                await imprecise_scroll(driver, log)

            if random.random() < cfg["pause_long_pct"]:
                await pause_distraction(log, cfg["pause_long_min"], cfg["pause_long_max"])

            # ── Actions ────────────────────────────────────────────────

            if len(post.get("caption", "")) > 50 and random.random() < 0.4:
                await slow_read_caption(log, len(post.get("caption", "")))

            # Like
            if random.random() < cfg["like_pct"]:
                if random.random() < cfg["hesitate_like_pct"]:
                    await hesitate_before_action(log, "like")

                like_tap = (post.get("actions") or {}).get("like")
                if like_tap and 80 < like_tap.get("y", 0) < 700:
                    await driver.ht.tap(like_tap["x"], like_tap["y"])
                    log("   ❤️  like @%s" % username)
                elif like_tap:
                    log("   ! like skip (y=%d hors zone)" % like_tap.get("y", 0))

                await driver.wait('tap')
                stats["likes"] += 1

            # Lire les reponses
            if random.random() < cfg["reply_read_pct"]:
                reply_tap = post.get("actions", {}).get("reply")
                if reply_tap and 80 < reply_tap.get("y", 0) < 700:
                    log("   💬 lecture reponses @%s" % username)
                    await driver.ht.tap(reply_tap["x"], reply_tap["y"])
                elif reply_tap:
                    log("   ! reply skip (y=%d hors zone)" % reply_tap.get("y", 0))
                    reply_tap = None
                if reply_tap:
                    await driver.wait('transition')
                    await browse_replies_slow(driver, log)
                    await navigator.go_back()
                    await driver.wait('transition')
                    await driver.ensure_screen("feed")
                    stats["reply_reads"] += 1

            # Visite profil
            if random.random() < cfg["visit_profile_pct"]:
                if random.random() < 0.6:
                    await random_profile_peek(driver, navigator, post, log)
                else:
                    log("   👤 visite profil @%s" % username)
                    await navigator.visit_profile_from_post(post)
                    await asyncio.sleep(random.uniform(3.0, 8.0))

                    if random.random() < 0.5:
                        await driver.scroll_down("normal")
                        await asyncio.sleep(random.uniform(2.0, 5.0))

                    if random.random() < cfg["follow_pct"]:
                        if await driver.tap_element(contains="Suivre"):
                            log("   ➕ follow @%s" % username)
                            stats["follows"] += 1
                            await driver.wait('tap')

                    await navigator.go_back()
                    await driver.wait('transition')

                await driver.ensure_screen("feed")
                stats["profile_visits"] += 1

            # Verify still on feed
            if stats["posts_seen"] % 5 == 0:
                if not await driver.ensure_screen("feed"):
                    log("!! ABORT: perdu apres interaction")
                    stats["aborted"] = True
                    stats["abort_reason"] = "lost_after_interaction"
                    stats["duration_s"] = round(time.time() - start)
                    return stats

            # Repost
            if random.random() < cfg["repost_pct"]:
                repost_tap = post.get("actions", {}).get("repost")
                if repost_tap:
                    log("   🔁 repost @%s" % username)
                    await driver.ht.tap(repost_tap["x"], repost_tap["y"])
                    await driver.wait('transition')
                    await asyncio.sleep(0.5)
                    await driver.tap_element(contains="Republier")
                    await driver.wait('tap')
                    stats["reposts"] += 1

        # ── Scroll vers les posts suivants ─────────────────────────────
        intensity = _pick_intensity()
        await driver.scroll_down(intensity)
        await driver.wait('scroll')
        await asyncio.sleep(random.uniform(1.5, 3.5))

    stats["duration_s"] = round(time.time() - start)
    stats["ended_at"] = datetime.now().isoformat()
    log("-> Feed session terminee: %d posts, %d likes, %ds" % (
        stats["posts_seen"], stats["likes"], stats["duration_s"]))

    return stats
