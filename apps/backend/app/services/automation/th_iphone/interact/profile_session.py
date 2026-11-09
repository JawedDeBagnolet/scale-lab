"""
th_iphone/interact/profile_session.py — Session visite de profils Threads (async).

Recherche un utilisateur, visite son profil, scroll ses posts,
like, reply, follow. Simule une decouverte organique.

Usage:
    from ..interact.profile_session import run_profile_session
    await run_profile_session(driver, navigator, targets=["user1"], config={}, log=print)
"""

import asyncio
import random
import time
from datetime import datetime


DEFAULT_CONFIG = {
    "like_pct": 0.20,
    "follow_pct": 0.30,
    "scroll_posts_min": 2,
    "scroll_posts_max": 6,
    "read_bio": True,
    "browse_duration_min": 15,
    "browse_duration_max": 45,
    "pause_between_profiles_min": 5,
    "pause_between_profiles_max": 15,
}


async def visit_single_profile(driver, navigator, username, cfg, log):
    """Visite un profil et interagit."""
    start = time.time()
    stats = {
        "username": username,
        "found": False,
        "followed": False,
        "likes": 0,
        "posts_seen": 0,
        "duration_s": 0,
    }

    log("-> Visite profil @%s" % username)

    # 1. S'assurer d'etre sur le feed
    await driver.ensure_screen("feed")
    await asyncio.sleep(1)

    # 2. Tap bouton Rechercher (top right du feed)
    if not await driver.tap_element(contains="Rechercher", refresh=True):
        log("   ! bouton Rechercher non trouve")
        stats["duration_s"] = round(time.time() - start)
        return stats

    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # 3. Tap la barre de recherche (y > 100)
    els = await driver.get_elements(refresh=True)
    search_bars = [e for e in els if "rechercher" in e.get("text", "").lower() and e.get("tap", {}).get("y", 0) > 100]
    if search_bars:
        await driver.ht.tap(search_bars[0]["tap"]["x"], search_bars[0]["tap"]["y"])
        await driver.wait('tap')
        await asyncio.sleep(0.8)
    else:
        log("   ! barre de recherche non trouvee")
        await navigator.go_back()
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 4. Saisir le username
    log("   recherche @%s" % username)
    await driver.type_text(username, method="slow")
    await asyncio.sleep(2.5)

    # 5. Trouver le resultat (y > 150)
    els = await driver.get_elements(refresh=True)
    result = None
    for e in els:
        text = e.get("text", "").lower()
        y = e.get("tap", {}).get("y", 0)
        if username.lower() in text and y > 150 and e.get("clickable"):
            result = e
            break

    if not result:
        log("   ! @%s non trouve dans les resultats" % username)
        await navigator.go_back()
        await driver.wait('transition')
        await navigator.go_back()
        await driver.ensure_screen("feed")
        stats["duration_s"] = round(time.time() - start)
        return stats

    await driver.ht.tap(result["tap"]["x"], result["tap"]["y"])
    await driver.wait('transition')
    await asyncio.sleep(2)

    stats["found"] = True

    # 6. Verifier qu'on est bien sur son profil
    els = await driver.get_elements(refresh=True)
    all_text = " ".join([e.get("text", "").lower() for e in els])
    on_profile = "passer sur instagram" in all_text or "options de profil" in all_text or "followers" in all_text

    if not on_profile:
        log("   ! pas sur le profil apres tap resultat")
        await navigator.go_back()
        await driver.ensure_screen("feed")
        stats["duration_s"] = round(time.time() - start)
        return stats

    log("   profil @%s ouvert" % username)

    # Lire la bio
    if cfg.get("read_bio", True):
        log("   lecture bio...")
        await asyncio.sleep(random.uniform(2.0, 5.0))

    # Follow ?
    if random.random() < cfg.get("follow_pct", 0.3):
        follow_btn = await driver.find_element(contains="Suivre", clickable=True, refresh=True)
        if follow_btn:
            text = follow_btn.get("text", "")
            if "Suivre" in text and "Abonné" not in text and "plus" not in text:
                await driver.ht.tap(follow_btn["tap"]["x"], follow_btn["tap"]["y"])
                log("   ➕ follow @%s" % username)
                stats["followed"] = True
                await driver.wait('tap')
                await asyncio.sleep(random.uniform(1.0, 2.0))

    # Scroll ses posts et liker
    n_scrolls = random.randint(cfg.get("scroll_posts_min", 2), cfg.get("scroll_posts_max", 6))
    log("   browse %d scrolls" % n_scrolls)

    for i in range(n_scrolls):
        await driver.scroll_down(random.choice(["light", "normal"]))
        await asyncio.sleep(random.uniform(1.5, 4.0))

        if random.random() < cfg.get("like_pct", 0.2):
            likes = await driver.find_elements(contains="personnes ont aimé", clickable=True, refresh=True)
            if not likes:
                likes = await driver.find_elements(contains="personne a aimé", clickable=True, refresh=True)
            if likes:
                like_btn = random.choice(likes)
                if like_btn.get("tap"):
                    await driver.ht.tap(like_btn["tap"]["x"], like_btn["tap"]["y"])
                    log("   ❤️  like post @%s" % username)
                    stats["likes"] += 1
                    await driver.wait('tap')

        stats["posts_seen"] += 1

    # Retour au feed
    await asyncio.sleep(random.uniform(1.0, 3.0))
    await navigator.go_back()
    await driver.wait('transition')
    await asyncio.sleep(0.5)
    await navigator.go_back()
    await driver.wait('transition')
    await asyncio.sleep(0.5)
    await driver.ensure_screen("feed")

    stats["duration_s"] = round(time.time() - start)
    log("   profil @%s termine: follow=%s, likes=%d, %ds" % (
        username, stats["followed"], stats["likes"], stats["duration_s"]))
    return stats


async def run_profile_session(driver, navigator, targets, config=None, log=print):
    """Execute une session de visite de profils."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    stats = {
        "profiles_visited": 0,
        "profiles_found": 0,
        "total_follows": 0,
        "total_likes": 0,
        "duration_s": 0,
        "results": [],
        "started_at": datetime.now().isoformat(),
    }

    start = time.time()
    log("-> Session profils (%d cibles)" % len(targets))

    for i, username in enumerate(targets):
        result = await visit_single_profile(driver, navigator, username, cfg, log)
        stats["results"].append(result)
        stats["profiles_visited"] += 1

        if result.get("found"):
            stats["profiles_found"] += 1
        if result.get("followed"):
            stats["total_follows"] += 1
        stats["total_likes"] += result.get("likes", 0)

        await driver.ensure_screen("feed")

        if i < len(targets) - 1:
            pause = random.uniform(
                cfg.get("pause_between_profiles_min", 5),
                cfg.get("pause_between_profiles_max", 15)
            )
            log("   pause %.1fs avant prochain profil" % pause)
            await asyncio.sleep(pause)

    stats["duration_s"] = round(time.time() - start)
    stats["ended_at"] = datetime.now().isoformat()
    log("-> Session profils terminee: %d visites, %d follows, %d likes, %ds" % (
        stats["profiles_found"], stats["total_follows"], stats["total_likes"], stats["duration_s"]))

    return stats
