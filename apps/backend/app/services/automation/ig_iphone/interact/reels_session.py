"""
ig_iphone/interact/reels_session.py — Session Reels Instagram (async).

Navigue dans l'onglet Reels, regarde les videos, like, skip les pubs.
Ported from VPS sync version to async.

Usage:
    from app.services.automation.ig_iphone.interact.reels_session import run_reels_session
    await run_reels_session(driver, navigator, config={}, log=print)
"""

import asyncio
import random
import time
from datetime import datetime


DEFAULT_CONFIG = {
    "duration_min": 3,           # minutes
    "duration_max": 8,
    "watch_min": 3.0,            # temps min par reel (secondes)
    "watch_max": 15.0,           # temps max par reel
    "watch_full_pct": 0.3,       # proba de regarder jusqu'au bout (long)
    "watch_full_max": 30.0,
    "like_pct": 0.10,
    "follow_pct": 0.0,
    "comment_read_pct": 0.03,
    "save_pct": 0.02,              # proba d'enregistrer le reel (via menu)
    "repost_pct": 0.01,            # proba de republier
    "not_interested_pct": 0.03,    # proba "ca ne m'interesse pas" (via menu)
    "interested_pct": 0.02,        # proba "ce reel m'interesse" (via menu)
    "visit_profile_pct": 0.03,     # proba de visiter le profil depuis le reel
    "skip_sponsored": True,
    "skip_fast_pct": 0.15,       # proba de skip tres rapide (<1s)
    "go_back_pct": 0.03,         # proba de revoir le reel precedent
    "pause_long_pct": 0.05,
    "pause_long_min": 5.0,
    "pause_long_max": 15.0,
}


async def run_reels_session(driver, navigator, config=None, task=None, log=print,
                            abort_check=None, compte_id=None):
    """Execute une session Reels IG complete (async).

    Args:
        config: dict de parametres manuels
        task: dict de la task (pour resolution preset)
        abort_check: callable that raises if run is aborted
        compte_id: UUID du compte (pour health check)
    Returns: dict de stats
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    duration_s = random.uniform(cfg["duration_min"] * 60, cfg["duration_max"] * 60)

    stats = {
        "reels_watched": 0,
        "likes": 0,
        "follows": 0,
        "comments_read": 0,
        "saves": 0,
        "reposts": 0,
        "not_interested": 0,
        "interested": 0,
        "sponsored_skipped": 0,
        "fast_skipped": 0,
        "started_at": datetime.now().isoformat(),
        "duration_s": 0,
    }
    seen = set()
    start = time.time()

    log("=" * 50)
    log("SESSION REELS IG (%d-%dmin, like=%.0f%%)" % (
        cfg["duration_min"], cfg["duration_max"], cfg["like_pct"] * 100))
    log("=" * 50)

    # Health check avant session
    if compte_id:
        from app.services.automation.ig_iphone.health import check_account_health
        health = await check_account_health(compte_id, log=log)
        if not health["ok"]:
            log("   ! compte en %s — session annulee" % health["status"])
            return stats

    # Naviguer vers Reels
    await navigator.open_instagram()
    await navigator.go_reels()
    await asyncio.sleep(2)

    while True:
        elapsed = time.time() - start
        if elapsed >= duration_s:
            break

        if abort_check:
            abort_check()

        log("\n[%s] %d/%ds — %d reels, %d likes" % (
            datetime.now().strftime("%H:%M:%S"),
            int(elapsed), int(duration_s),
            stats["reels_watched"], stats["likes"]))

        # Pause longue (distraction)
        if random.random() < cfg["pause_long_pct"]:
            pause = random.uniform(cfg["pause_long_min"], cfg["pause_long_max"])
            log("   [anti] pause %.1fs" % pause)
            await asyncio.sleep(pause)
            continue

        # Detecter le reel en cours
        reel = await _detect_current_reel(driver)
        if not reel:
            # Peut-être un popup bloque l'écran
            dismissed = await _dismiss_popup(driver)
            if dismissed:
                log("   popup dismiss -> retry")
                continue
            log("   pas de reel detecte -> swipe")
            await _swipe_next_reel(driver)
            await asyncio.sleep(1)
            continue

        username = reel["username"]
        is_sponsored = reel["is_sponsored"]

        # Skip si deja vu
        if username in seen:
            await _swipe_next_reel(driver)
            await asyncio.sleep(0.5)
            continue
        seen.add(username)

        log("   reel @%s%s" % (username, " [SPONSO]" if is_sponsored else ""))

        # Skip sponsorise
        if is_sponsored and cfg["skip_sponsored"]:
            log("   -> skip sponsorise")
            stats["sponsored_skipped"] += 1
            await _swipe_next_reel(driver)
            await driver.wait('micro')
            continue

        # Skip rapide
        if random.random() < cfg["skip_fast_pct"]:
            log("   -> skip rapide")
            stats["fast_skipped"] += 1
            await asyncio.sleep(random.uniform(0.3, 0.8))
            await _swipe_next_reel(driver)
            await driver.wait('micro')
            continue

        # Regarder le reel
        if random.random() < cfg["watch_full_pct"]:
            watch = random.uniform(cfg["watch_max"], cfg["watch_full_max"])
        else:
            watch = random.uniform(cfg["watch_min"], cfg["watch_max"])
        log("   watch %.1fs" % watch)
        await asyncio.sleep(watch)
        stats["reels_watched"] += 1

        # Like
        if random.random() < cfg["like_pct"]:
            like_els = await driver.find_elements(text="J'aime", clickable=True, refresh=True)
            for el in (like_els or []):
                w = el.get('rect', {}).get('width', 0)
                if 30 <= w <= 50:
                    tap = el.get('tap', {})
                    log("   like reel @%s" % username)
                    await driver.ht.tap(tap['x'], tap['y'])
                    await driver.wait('tap')
                    stats["likes"] += 1
                    break

        # Lire commentaires
        if random.random() < cfg["comment_read_pct"]:
            comment_el = await driver.find_element(text="Commenter", clickable=True, refresh=True)
            if comment_el:
                tap = comment_el.get('tap', {})
                log("   ouvre commentaires reel @%s" % username)
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('transition')
                await asyncio.sleep(1)
                # Lire quelques commentaires
                read_time = random.uniform(3.0, 7.0)
                await asyncio.sleep(read_time / 2)
                await driver.scroll_down('light')
                await asyncio.sleep(read_time / 2)
                # Fermer (bouton ou swipe down)
                log("   ferme commentaires")
                closed = await driver.tap_element(text="Fermer")
                if not closed:
                    await driver.ht.swipe(
                        driver.ht.screen_w * 0.5, driver.ht.screen_h * 0.3,
                        driver.ht.screen_w * 0.5, driver.ht.screen_h * 0.85,
                        random.randint(300, 500))
                await asyncio.sleep(1.5)
                # Verifier qu on est bien dans les reels
                screen = await driver.detect_current_screen()
                if screen != "reels":
                    log("   ! bloque apres commentaires (ecran=%s)" % screen)
                    closed2 = await driver.tap_element(text="Fermer")
                    if closed2:
                        await asyncio.sleep(1)
                stats["comments_read"] += 1

        # Follow
        if random.random() < cfg["follow_pct"]:
            follow_el = await driver.find_element(contains="Suivre " + username, refresh=True)
            if follow_el:
                tap = follow_el.get('tap', {})
                log("   follow @%s" % username)
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('tap')
                stats["follows"] += 1

        # Repost (bouton Republier sur l'ecran du reel)
        if random.random() < cfg["repost_pct"]:
            repost_el = await driver.find_element(text="Republier", clickable=True, refresh=True)
            if repost_el:
                tap = repost_el.get('tap', {})
                log("   repost reel @%s" % username)
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('transition')
                await asyncio.sleep(1)
                # Confirmer le repost si dialogue
                confirm = await driver.find_element(contains="Republier", clickable=True, refresh=True)
                if confirm:
                    tap2 = confirm.get('tap', {})
                    await driver.ht.tap(tap2['x'], tap2['y'])
                    await driver.wait('transition')
                # Dismiss le popup "Vous avez republié ce reel"
                await asyncio.sleep(1)
                await _dismiss_popup(driver)
                stats["reposts"] += 1

        # Actions menu (3 points) : save, interested, not interested
        _menu_action = None
        if random.random() < cfg["save_pct"]:
            _menu_action = "save"
        elif random.random() < cfg["not_interested_pct"]:
            _menu_action = "not_interested"
        elif random.random() < cfg["interested_pct"]:
            _menu_action = "interested"

        if _menu_action:
            menu_el = await driver.find_element(text="Plus d'actions", clickable=True, refresh=True)
            if menu_el:
                tap = menu_el.get('tap', {})
                log("   ouvre menu reel @%s" % username)
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('transition')
                await asyncio.sleep(0.8)

                if _menu_action == "save":
                    target = await driver.find_element(contains="Enregistrer", clickable=True, refresh=True)
                    if target:
                        tap2 = target.get('tap', {})
                        log("   enregistrer reel @%s" % username)
                        await driver.ht.tap(tap2['x'], tap2['y'])
                        stats["saves"] += 1
                elif _menu_action == "not_interested":
                    target = await driver.find_element(contains="ne m'int", clickable=True, refresh=True)
                    if target:
                        tap2 = target.get('tap', {})
                        log("   pas interesse @%s" % username)
                        await driver.ht.tap(tap2['x'], tap2['y'])
                        stats["not_interested"] += 1
                elif _menu_action == "interested":
                    target = await driver.find_element(contains="m'int", clickable=True, refresh=True)
                    if not target or "ne m" in (target.get('text', '') or '').lower():
                        target = await driver.find_element(contains="Ce reel m", clickable=True, refresh=False)
                    if target:
                        tap2 = target.get('tap', {})
                        log("   interesse @%s" % username)
                        await driver.ht.tap(tap2['x'], tap2['y'])
                        stats["interested"] += 1

                await driver.wait('tap')
                await asyncio.sleep(0.5)

        # Visiter le profil depuis le reel
        if random.random() < cfg.get("visit_profile_pct", 0):
            log("   visite profil @%s depuis reel" % username)
            visited = await navigator.visit_from_reel(username)
            if visited:
                await asyncio.sleep(random.uniform(3.0, 8.0))
                # Maybe follow sur le profil
                if random.random() < cfg["follow_pct"]:
                    follow_el = await driver.find_element(text="Suivre", clickable=True, refresh=True)
                    if follow_el:
                        rect = follow_el.get('rect', {})
                        if rect.get('width', 0) >= 60:
                            tap = follow_el.get('tap', {})
                            log("   follow @%s depuis profil" % username)
                            await driver.ht.tap(tap['x'], tap['y'])
                            await driver.wait('tap')
                            stats["follows"] += 1
                await navigator.go_back()
                await driver.wait('transition')
                await asyncio.sleep(1)

        # Retour (revoir le precedent)
        if stats["reels_watched"] > 1 and random.random() < cfg["go_back_pct"]:
            log("   [anti] revoir precedent")
            await _swipe_prev_reel(driver)
            await asyncio.sleep(random.uniform(2.0, 5.0))
            await _swipe_next_reel(driver)
            await asyncio.sleep(0.5)

        if abort_check:
            abort_check()

        # Avancer au reel suivant
        await _swipe_next_reel(driver)
        await driver.wait('micro')

    # Retour au feed
    await navigator.go_home()

    stats["duration_s"] = round(time.time() - start)
    stats["ended_at"] = datetime.now().isoformat()

    log("\n" + "=" * 50)
    log("FIN SESSION REELS")
    log("  Duree: %ds (%dmin)" % (stats["duration_s"], stats["duration_s"] // 60))
    log("  Reels vus: %d" % stats["reels_watched"])
    log("  Likes: %d" % stats["likes"])
    log("  Commentaires lus: %d" % stats["comments_read"])
    log("  Sponsorises passes: %d" % stats["sponsored_skipped"])
    log("  Skips rapides: %d" % stats["fast_skipped"])
    log("=" * 50)

    return stats


async def _detect_current_reel(driver):
    """Detecte le reel en cours — username et sponsored."""
    els = await driver.find_elements(refresh=True, clickable=None)
    username = None
    is_sponsored = False

    for e in (els or []):
        text = (e.get('text', '') or '')
        # "Reel de <user>" ou "Reel sponsorisé de <user>"
        if text.startswith('Reel de '):
            username = text[8:].rstrip('.')
        elif text.startswith('Reel sponsoris'):
            # "Reel sponsorisé de <user>."
            parts = text.split(' de ', 1)
            if len(parts) > 1:
                username = parts[1].rstrip('.')
            is_sponsored = True
        # "Publicité" label
        if text == 'Publicité' or text == 'Publicite':
            is_sponsored = True
        # CTA full-width (ads)
        r = e.get('rect', {})
        if r.get('width', 0) >= 250 and r.get('height', 0) >= 40:
            _ctas = ('obtenir', 'acheter', 'installer', 'en savoir', "s'inscrire", 'telecharger')
            if any(c in text.lower() for c in _ctas):
                is_sponsored = True

    if username:
        return {"username": username, "is_sponsored": is_sponsored}
    return None


async def _swipe_next_reel(driver):
    """Swipe up pour passer au reel suivant."""
    await driver.ht._ensure_screen()
    w, h = driver.ht.screen_w, driver.ht.screen_h
    # Fast vertical swipe — simulates a flick to advance to next reel
    x = w * random.uniform(0.35, 0.65)
    start_y = h * random.uniform(0.70, 0.80)
    end_y = h * random.uniform(0.15, 0.25)
    dur = random.randint(250, 450)
    await driver.ht.swipe(x, start_y, x + random.gauss(0, 5), end_y, duration=dur, steps=random.randint(15, 25))


async def _dismiss_popup(driver):
    """Try to dismiss common IG popups (repost confirm, notifications, etc.).

    Returns True if a popup was dismissed.
    """
    await driver.refresh_elements()
    dismiss_texts = ["OK", "Annuler", "Pas maintenant", "Not Now", "Ignorer", "Continuer"]
    for text in dismiss_texts:
        el = await driver.find_element(text, clickable=True)
        if el:
            tap = el.get('tap', {})
            await driver.ht.tap(tap.get('x', 0), tap.get('y', 0))
            await asyncio.sleep(0.8)
            return True
    return False


async def _swipe_prev_reel(driver):
    """Swipe down pour revenir au reel precedent."""
    await driver.ht._ensure_screen()
    w, h = driver.ht.screen_w, driver.ht.screen_h
    x = w * random.uniform(0.35, 0.65)
    start_y = h * random.uniform(0.20, 0.30)
    end_y = h * random.uniform(0.75, 0.85)
    dur = random.randint(250, 450)
    await driver.ht.swipe(x, start_y, x + random.gauss(0, 5), end_y, duration=dur, steps=random.randint(15, 25))
