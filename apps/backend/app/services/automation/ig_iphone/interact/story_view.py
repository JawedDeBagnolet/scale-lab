"""
ig_iphone/interact/story_view.py — Visionnage de stories Instagram (async).

Ouvre les stories depuis le feed, les regarde, parfois like/reply.
Ported from VPS sync version to async.

Usage:
    from app.services.automation.ig_iphone.interact.story_view import watch_stories
    await watch_stories(driver, navigator, config={}, log=print)
"""

import asyncio
import random
import time
from datetime import datetime
from app.services.automation.ig_iphone.selectors import STORY_TAP_NEXT_X, STORY_TAP_PREV_X, STORY_TAP_Y


DEFAULT_CONFIG = {
    "max_stories": 8,           # nombre max de stories a regarder
    "watch_min": 1.5,           # temps min par story (secondes)
    "watch_max": 5.0,           # temps max par story
    "like_pct": 0.05,           # proba de liker une story
    "reply_pct": 0.0,           # proba de repondre (desactive par defaut)
    "skip_pct": 0.15,           # proba de skip rapide (tap vite)
    "go_back_pct": 0.05,        # proba de revenir a la story precedente
    "start_index": 0,           # index de depart dans la barre de stories
}


async def watch_stories(driver, navigator, config=None, log=print):
    """Regarde les stories depuis le feed (async).

    Returns: dict {stories_watched, likes, skipped, duration_s}
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    start = time.time()

    stats = {
        "stories_watched": 0,
        "stories_liked": 0,
        "stories_skipped": 0,
        "users_seen": [],
        "duration_s": 0,
    }

    log("-> Watch stories (max %d)" % cfg["max_stories"])

    # S'assurer qu'on est sur le feed
    screen = await driver.detect_current_screen()
    if screen != 'feed':
        await navigator.go_home()
        await driver.wait('transition')
        await asyncio.sleep(1)

    # Ouvrir la premiere story
    opened = await navigator.open_stories(cfg["start_index"])
    if not opened:
        log("   ! impossible d'ouvrir les stories")
        return stats

    await asyncio.sleep(1.5)

    # Verifier qu'on est dans les stories
    current_user = await _get_story_user(driver)
    if not current_user:
        log("   ! pas dans les stories")
        await navigator.go_back()
        return stats

    log("   story de @%s" % current_user)

    # Boucle de visionnage
    for i in range(cfg["max_stories"]):
        current_user = await _get_story_user(driver)
        if not current_user:
            log("   fin des stories (plus de contenu)")
            break

        if current_user not in stats["users_seen"]:
            stats["users_seen"].append(current_user)

        # Regarder ou skip ?
        if random.random() < cfg["skip_pct"]:
            # Skip rapide
            log("   skip story @%s" % current_user)
            stats["stories_skipped"] += 1
            await _story_next(driver)
            await driver.wait('micro')
            continue

        # Regarder la story
        watch = random.uniform(cfg["watch_min"], cfg["watch_max"])
        log("   watch @%s %.1fs" % (current_user, watch))
        await asyncio.sleep(watch)
        stats["stories_watched"] += 1

        # Maybe like
        if random.random() < cfg["like_pct"]:
            like_el = await driver.find_element(text="J'aime", clickable=True, refresh=True)
            if like_el:
                tap = like_el.get('tap', {})
                log("   like story @%s" % current_user)
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('tap')
                stats["stories_liked"] += 1

        # Maybe go back
        if i > 0 and random.random() < cfg["go_back_pct"]:
            log("   retour story precedente")
            await _story_prev(driver)
            await driver.wait('micro')
            await asyncio.sleep(random.uniform(1.0, 3.0))

        # Avancer a la story suivante
        await _story_next(driver)
        await driver.wait('micro')
        await asyncio.sleep(0.5)

    # Fermer les stories
    log("   ferme stories")
    await _close_stories(driver, navigator)

    stats["duration_s"] = round(time.time() - start)
    log("   stories: %d vues, %d likes, %d skips, %d users" % (
        stats["stories_watched"], stats["stories_liked"],
        stats["stories_skipped"], len(stats["users_seen"])))

    return stats


async def _get_story_user(driver):
    """Extrait le username de la story en cours."""
    els = await driver.find_elements(contains="Story de", refresh=True)
    for e in (els or []):
        text = e.get('text', '') or ''
        if text.startswith('Story de '):
            return text[9:].strip()
    return None


async def _story_next(driver):
    """Avance a la story suivante (tap cote droit)."""
    await driver.ht._ensure_screen()
    x = driver.ht.screen_w * STORY_TAP_NEXT_X
    y = driver.ht.screen_h * STORY_TAP_Y
    await driver.ht.tap(x, y)


async def _story_prev(driver):
    """Revient a la story precedente (tap cote gauche)."""
    await driver.ht._ensure_screen()
    x = driver.ht.screen_w * STORY_TAP_PREV_X
    y = driver.ht.screen_h * STORY_TAP_Y
    await driver.ht.tap(x, y)


async def _close_stories(driver, navigator):
    """Ferme les stories."""
    # Methode 1 : bouton X
    close = await driver.find_element(contains="Fermer les stories", refresh=True)
    if close:
        tap = close.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        return

    # Methode 2 : swipe down
    await driver.ht._ensure_screen()
    await driver.ht.swipe(
        driver.ht.screen_w * 0.5,
        driver.ht.screen_h * 0.3,
        driver.ht.screen_w * 0.5,
        driver.ht.screen_h * 0.85,
        random.randint(250, 400)
    )
    await driver.wait('transition')
