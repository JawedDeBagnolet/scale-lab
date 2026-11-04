"""Anti-detection behavioral patterns.

Each pattern is an async function that takes a driver and a log callable.
They simulate human imperfections: hesitations, re-reads, scroll errors,
typing mistakes, distractions, etc.

Ported from VPS scripts (th_iphone/behavior/patterns.py, ig_iphone/behavior/patterns.py).
"""

import asyncio
import math
import random
from typing import Any, Callable


# ═════════════════════════════════════════════════════════════════════════════
# Common patterns (IG + Threads)
# ═════════════════════════════════════════════════════════════════════════════

async def scroll_back(drv: Any, log: Callable):
    """Scroll back up to re-read a post (~10% of scrolls)."""
    log("   [behavior] scroll back to re-read")
    await drv.ht.scroll_up()
    await asyncio.sleep(random.uniform(2, 5))
    await drv.ht.scroll_down()


async def pause_distraction(drv: Any, log: Callable):
    """Long pause simulating a distraction (phone notification, looking away)."""
    pause = random.uniform(8, 20)
    log(f"   [behavior] distraction pause {pause:.0f}s")
    await asyncio.sleep(pause)


async def hesitate_before_action(drv: Any, log: Callable):
    """Brief hesitation before performing an action (like, comment, follow)."""
    pause = random.uniform(0.5, 2.0)
    await asyncio.sleep(pause)


async def slow_read_caption(drv: Any, log: Callable, caption_length: int = 50):
    """Pause to read a caption at ~250 words per minute."""
    # Assume ~5 chars per word
    word_count = max(caption_length / 5, 3)
    read_time = min(word_count / 250 * 60, 12)  # cap at 12s
    read_time *= random.uniform(0.8, 1.3)  # jitter
    log(f"   [behavior] reading caption ({caption_length} chars, {read_time:.1f}s)")
    await asyncio.sleep(read_time)


async def browse_replies_slow(drv: Any, log: Callable):
    """Open and slowly browse comment replies."""
    log("   [behavior] browsing replies slowly")
    tapped = await drv.tap_element("commentaire", contains=True)
    if not tapped:
        tapped = await drv.tap_element("Voir", contains=True)
    if not tapped:
        return  # no comments visible

    await asyncio.sleep(random.uniform(1.5, 3))
    scroll_count = random.randint(1, 4)
    for _ in range(scroll_count):
        await drv.ht.scroll_down()
        await asyncio.sleep(random.uniform(2, 5))

    # Go back
    await drv.tap_element("Retour", contains=False)
    if not tapped:
        await drv.ht.tap_pos(0.05, 0.06)  # top-left back button area


async def imprecise_scroll(drv: Any, log: Callable):
    """Scroll too far or not enough, then correct (~15% of scrolls)."""
    log("   [behavior] imprecise scroll + correction")
    # Overshoot
    overshoot_cfg = {
        "dist_min": 0.85, "dist_max": 1.1,
        "dur_min": 500, "dur_max": 1200,
        "drift_min": 0.05, "drift_max": 0.20,
        "pts_min": 30, "pts_max": 55,
    }
    await drv.ht.scroll_down(config=overshoot_cfg)
    await asyncio.sleep(random.uniform(0.3, 0.8))
    # Correction: scroll back up a bit
    correction_cfg = {
        "dist_min": 0.10, "dist_max": 0.25,
        "dur_min": 400, "dur_max": 800,
        "drift_min": 0.02, "drift_max": 0.08,
        "pts_min": 20, "pts_max": 35,
    }
    await drv.ht.scroll_up(config=correction_cfg)


async def double_tap_miss(drv: Any, log: Callable, x: float, y: float):
    """Double-tap that misses on the first attempt, then succeeds."""
    log("   [behavior] double-tap miss + retry")
    offset_x = random.uniform(-15, 15)
    offset_y = random.uniform(-15, 15)
    # First tap: slightly off target
    await drv.ht.tap(x + offset_x, y + offset_y)
    await asyncio.sleep(random.uniform(0.08, 0.15))
    # Second tap: on target
    await drv.ht.tap(x, y)


async def random_profile_peek(drv: Any, log: Callable):
    """Quick peek at a random profile (curiosity), then back."""
    elements = await drv.ht.get_elements(clickable_only=True, max_elements=80)
    # Find username-looking elements (short text, high on screen)
    usernames = [
        e for e in elements
        if (e.get("text") or "").startswith("@")
        or (3 < len(e.get("text", "")) < 25 and e.get("y", 0) > 100)
    ]
    if not usernames:
        return

    target = random.choice(usernames[:10])
    name = target.get("text", "?")[:20]
    log(f"   [behavior] quick peek at profile '{name}'")
    await drv.ht.tap(target.get("x", 187), target.get("y", 400))
    await asyncio.sleep(random.uniform(2, 5))

    # Maybe scroll their profile a bit
    if random.random() < 0.3:
        await drv.ht.scroll_down()
        await asyncio.sleep(random.uniform(1, 3))

    # Go back
    await drv.tap_element("Retour", contains=False)
    await asyncio.sleep(random.uniform(0.5, 1.0))


async def typing_corrections(drv: Any, log: Callable, text: str):
    """Type text with realistic mistakes: type some, delete, retype."""
    if len(text) < 5:
        await drv.ht.type_text(text)
        return

    log("   [behavior] typing with corrections")
    # Type a portion
    cut = random.randint(3, min(len(text), 10))
    await drv.ht.type_text(text[:cut], realistic=False)
    await asyncio.sleep(random.uniform(0.3, 0.8))

    # Delete 1-5 characters
    delete_count = random.randint(1, min(5, cut))
    from app.services.dispatch import mcp_call
    mcp_port = drv.ht.mcp_port
    for _ in range(delete_count):
        await mcp_call(mcp_port, "press_key", {"key": "delete"}, timeout=3)
        await asyncio.sleep(random.uniform(0.05, 0.15))

    await asyncio.sleep(random.uniform(0.2, 0.5))
    # Retype correctly from the cut point minus deleted chars
    remaining = text[cut - delete_count:]
    await drv.ht.type_text(remaining, realistic=False)


# ═════════════════════════════════════════════════════════════════════════════
# IG-specific patterns
# ═════════════════════════════════════════════════════════════════════════════

async def watch_video_variable(drv: Any, log: Callable):
    """Watch a video/Reel for a variable duration (log-normal distribution)."""
    # Log-normal: most views 3-8s, occasional long views up to 15s
    duration = min(random.lognormvariate(1.6, 0.5), 15)
    duration = max(duration, 3.0)
    log(f"   [behavior] watching video {duration:.1f}s")
    await asyncio.sleep(duration)


async def change_scroll_speed(drv: Any, log: Callable):
    """Change scroll speed: alternate between light/normal/strong/flick."""
    speed_configs = {
        "light": {"dist_min": 0.20, "dist_max": 0.40, "dur_min": 800, "dur_max": 1500,
                  "drift_min": 0.02, "drift_max": 0.10, "pts_min": 35, "pts_max": 60},
        "normal": {"dist_min": 0.40, "dist_max": 0.70, "dur_min": 600, "dur_max": 1200,
                   "drift_min": 0.05, "drift_max": 0.20, "pts_min": 35, "pts_max": 65},
        "strong": {"dist_min": 0.70, "dist_max": 0.95, "dur_min": 400, "dur_max": 900,
                   "drift_min": 0.08, "drift_max": 0.25, "pts_min": 40, "pts_max": 75},
        "flick": {"dist_min": 0.90, "dist_max": 1.2, "dur_min": 300, "dur_max": 600,
                  "drift_min": 0.05, "drift_max": 0.15, "pts_min": 20, "pts_max": 40},
    }
    # Weighted choice: normal most common
    speed = random.choices(
        ["light", "normal", "strong", "flick"],
        weights=[0.2, 0.45, 0.25, 0.1],
    )[0]
    log(f"   [behavior] scroll speed: {speed}")
    await drv.ht.scroll_down(config=speed_configs[speed])


async def behavior_glance(drv: Any, log: Callable):
    """Quick glance: 1-2 fast scrolls without interaction."""
    log("   [behavior] glance (fast scroll, no interaction)")
    fast_cfg = {"dist_min": 0.6, "dist_max": 0.9, "dur_min": 400, "dur_max": 700,
                "drift_min": 0.03, "drift_max": 0.10, "pts_min": 25, "pts_max": 45}
    count = random.randint(1, 2)
    for _ in range(count):
        await drv.ht.scroll_down(config=fast_cfg)
        await asyncio.sleep(random.uniform(0.3, 0.8))


async def behavior_browse(drv: Any, log: Callable):
    """Browse mode: 2-4 scrolls, then scroll back to top."""
    log("   [behavior] browse (scroll + return to top)")
    count = random.randint(2, 4)
    for _ in range(count):
        await drv.ht.scroll_down()
        await asyncio.sleep(random.uniform(1.0, 2.5))
    # Scroll back up
    for _ in range(count):
        await drv.ht.scroll_up()
        await asyncio.sleep(random.uniform(0.3, 0.6))


async def behavior_deep_read(drv: Any, log: Callable):
    """Deep read: long pause on a post with micro-scrolls."""
    duration = random.uniform(8, 15)
    log(f"   [behavior] deep read {duration:.0f}s")
    elapsed = 0
    while elapsed < duration:
        # Micro-scroll (tiny adjustment)
        if random.random() < 0.4:
            micro_cfg = {"dist_min": 0.03, "dist_max": 0.08, "dur_min": 300, "dur_max": 600,
                         "drift_min": 0.01, "drift_max": 0.03, "pts_min": 15, "pts_max": 25}
            direction = random.choice(["down", "up"])
            if direction == "down":
                await drv.ht.scroll_down(config=micro_cfg)
            else:
                await drv.ht.scroll_up(config=micro_cfg)
        pause = random.uniform(1.5, 4.0)
        await asyncio.sleep(pause)
        elapsed += pause


# ═════════════════════════════════════════════════════════════════════════════
# Registry and helpers
# ═════════════════════════════════════════════════════════════════════════════

# Common patterns (no extra args needed)
PATTERNS = {
    "scroll_back": (scroll_back, 0.10),
    "pause_distraction": (pause_distraction, 0.05),
    "hesitate": (hesitate_before_action, 0.20),
    "imprecise_scroll": (imprecise_scroll, 0.12),
    "profile_peek": (random_profile_peek, 0.05),
}

# IG-specific patterns
IG_PATTERNS = {
    "watch_video": (watch_video_variable, 0.15),
    "change_speed": (change_scroll_speed, 0.20),
    "glance": (behavior_glance, 0.08),
    "browse": (behavior_browse, 0.05),
    "deep_read": (behavior_deep_read, 0.06),
}


async def maybe_pattern(
    drv: Any,
    log: Callable,
    probability: float = 0.15,
    *,
    include_ig: bool = True,
) -> bool:
    """Maybe run a random pattern. Returns True if a pattern ran."""
    if random.random() > probability:
        return False

    pool = dict(PATTERNS)
    if include_ig:
        pool.update(IG_PATTERNS)

    # Weighted random choice based on per-pattern probability
    names = list(pool.keys())
    weights = [pool[n][1] for n in names]
    chosen = random.choices(names, weights=weights, k=1)[0]
    fn, _ = pool[chosen]

    try:
        await fn(drv, log)
    except Exception as e:
        log(f"   [behavior] {chosen} failed: {str(e)[:60]}")

    return True


async def pick_pattern(
    drv: Any,
    log: Callable,
    category: str,
) -> bool:
    """Run a specific pattern by name. Returns True if found and ran."""
    all_patterns = {**PATTERNS, **IG_PATTERNS}
    if category not in all_patterns:
        return False
    fn, _ = all_patterns[category]
    try:
        await fn(drv, log)
        return True
    except Exception as e:
        log(f"   [behavior] {category} failed: {str(e)[:60]}")
        return False
