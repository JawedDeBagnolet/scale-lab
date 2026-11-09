"""
ig_iphone/interact/profile_visit.py — Visite de profil Instagram.

Ouvre un profil, le browse naturellement (bio, posts, stories),
et interagit selon la config (like, follow, DM).

Usage:
    from app.services.automation.ig_iphone.interact.profile_visit import visit_profile
    visit_profile(driver, navigator, username="therock", config={}, log=print)
"""

import random

import asyncio
import time
from datetime import datetime


DEFAULT_CONFIG = {
    "like_pct": 0.15,           # proba de liker un post du profil
    "follow_pct": 0.0,          # proba de follow
    "follow_delay_min": 3.0,    # attente min avant follow (pas instantane)
    "follow_delay_max": 8.0,
    "dm_pct": 0.0,              # proba d'envoyer un DM (desactive par defaut)
    "browse_posts_min": 0,      # nombre min de posts a ouvrir
    "browse_posts_max": 3,      # nombre max de posts a ouvrir
    "read_bio_pct": 0.7,        # proba de lire la bio
    "bio_read_min": 2.0,        # temps de lecture bio min
    "bio_read_max": 6.0,
    "open_stories_pct": 0.0,    # proba d'ouvrir les stories highlights
    "visit_duration_min": 8,    # duree min visite (secondes)
    "visit_duration_max": 40,   # duree max visite (secondes)
    "highlights_pct": 0.25,     # proba d'ouvrir les stories a la une
    "highlights_max": 3,        # max stories a regarder
    "highlight_view_min": 3.0,  # temps min par story
    "highlight_view_max": 8.0,  # temps max par story
    "reels_pct": 0.20,          # proba d'ouvrir l'onglet reels
    "reels_browse_min": 1,      # min reels a regarder
    "reels_browse_max": 4,      # max reels a regarder
    "reel_view_min": 3.0,       # temps min par reel
    "reel_view_max": 12.0,      # temps max par reel
    "reel_like_pct": 0.10,      # proba liker un reel
    "tab_switch_pct": 0.30,     # proba de switch entre grille et reels
}


async def visit_profile(driver, navigator, username, config=None, log=print):
    """Visite le profil d'un utilisateur.

    Args:
        username: le @ du profil a visiter
        config: dict de parametres (merge avec DEFAULT_CONFIG)

    Returns:
        dict {visited, liked, followed, posts_opened, duration_s}
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    start = time.time()
    visit_dur = random.uniform(cfg["visit_duration_min"], cfg["visit_duration_max"])

    stats = {
        "username": username,
        "visited": False,
        "liked": 0,
        "followed": False,
        "posts_opened": 0,
        "reels_watched": 0,
        "highlights_watched": 0,
        "duration_s": 0,
    }

    # Health check avant visite
    health = check_account_health(log=log)
    if not health["ok"]:
        log("   ! compte en %s — visite annulee" % health["status"])
        return stats

    log("-> Visite profil @%s" % username)

    # 1. Ouvrir le profil via Explorer -> recherche
    if not await navigator.search_and_open_profile(username):
        log("   ! profil @%s non trouve" % username)
        return stats
    await asyncio.sleep(2)

    # Verifier qu'on est sur un profil
    screen = await driver.detect_current_screen()
    if screen not in ('profile', 'own_profile'):
        log("   ! ecran=%s, pas un profil" % screen)
        # Peut-etre un popup ou erreur
        await navigator._dismiss_popups()
        await asyncio.sleep(1)
        screen = await driver.detect_current_screen()
        if screen not in ('profile', 'own_profile'):
            log("   ! abandon visite @%s" % username)
            await navigator.go_back()
            return stats

    stats["visited"] = True

    # 2. Lire la bio
    if random.random() < cfg["read_bio_pct"]:
        bio_time = random.uniform(cfg["bio_read_min"], cfg["bio_read_max"])
        log("   lecture bio %.1fs" % bio_time)
        await asyncio.sleep(bio_time)

    # 2b. Stories a la une
    if random.random() < cfg["highlights_pct"]:
        _browse_highlights(driver, cfg, stats, log)

    # 3. Pick behavior : glance / browse / deep_read / reels
    elapsed = time.time() - start
    remaining = visit_dur - elapsed
    if remaining < 5:
        behavior = "glance"
    else:
        # Choisir entre grille, reels, ou les deux
        do_reels = random.random() < cfg["reels_pct"]
        do_switch = random.random() < cfg["tab_switch_pct"]

        if cfg.get("browse_posts_min", 0) > 0:
            behavior = random.choices(
                ["browse", "deep_read"],
                weights=[65, 35],
            )[0]
        else:
            behavior = random.choices(
                ["glance", "browse", "deep_read"],
                weights=[30, 50, 20],
            )[0]

    log("   behavior: %s (%.0fs restants)" % (behavior, remaining))

    if behavior == "glance":
        n = random.randint(1, 2)
        for _ in range(n):
            await driver.scroll_down('light')
            await driver.wait('scroll')

    elif behavior == "browse":
        if do_reels and not do_switch:
            _browse_reels_tab(driver, navigator, cfg, stats, log, remaining)
        elif do_switch:
            # Alterner entre grille et reels
            half = remaining / 2
            _browse_posts(driver, navigator, cfg, stats, log, half, username)
            _browse_reels_tab(driver, navigator, cfg, stats, log, half)
        else:
            _browse_posts(driver, navigator, cfg, stats, log, remaining, username)

    elif behavior == "deep_read":
        extra_read = random.uniform(3.0, 8.0)
        log("   lecture approfondie %.1fs" % extra_read)
        await asyncio.sleep(extra_read)
        remaining2 = remaining - extra_read
        if do_reels:
            _browse_reels_tab(driver, navigator, cfg, stats, log, remaining2)
        else:
            _browse_posts(driver, navigator, cfg, stats, log, remaining2, username)

    # 4. Follow (avec delai)
    if random.random() < cfg["follow_pct"]:
        delay = random.uniform(cfg["follow_delay_min"], cfg["follow_delay_max"])
        log("   attente avant follow %.1fs" % delay)
        await asyncio.sleep(delay)

        follow_btn = await driver.find_element(text="Suivre", clickable=True)
        if follow_btn:
            rect = follow_btn.get('rect', {})
            # Verifier que c'est le GROS bouton follow (pas un petit "Suivre" de suggestion)
            if rect.get('width', 0) >= 60:
                tap = follow_btn.get('tap', {})
                log("   follow @%s" % username)
                await driver.ht.tap(tap['x'], tap['y'], bounds=(rect.get('width', 75), rect.get('height', 34)))
                await driver.wait('tap')
                stats["followed"] = True
            else:
                log("   ! bouton follow trop petit (suggestion?), skip")

    # 5. Attendre la duree restante
    elapsed = time.time() - start
    remaining = visit_dur - elapsed
    if remaining > 1:
        wait = min(remaining, random.uniform(1.0, 3.0))
        await asyncio.sleep(wait)

    # 6. Retour
    log("   retour depuis @%s" % username)
    await navigator.go_back()
    await driver.wait('transition')

    stats["duration_s"] = round(time.time() - start)
    log("   visite @%s: %ds, %d likes, follow=%s" % (
        username, stats["duration_s"], stats["liked"], stats["followed"]))

    return stats


async def _browse_highlights(driver, cfg, stats, log):
    """Ouvre et regarde les stories a la une du profil."""
    n = random.randint(1, cfg.get("highlights_max", 3))
    log("   ouvre stories a la une (%d)" % n)

    # Trouver la barre des contenus a la une
    bar = await driver.find_element(contains="Barre des contenus", refresh=True)
    if not bar:
        log("   pas de stories a la une")
        return

    # Taper sur la premiere story (centre de la barre, un peu a gauche)
    bar_rect = bar.get("rect", {})
    bar_y = bar_rect.get("y", 400) + bar_rect.get("height", 98) // 2
    start_x = 50  # premiere story

    await driver.ht.tap(start_x, bar_y)
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    stories_watched = 0
    for i in range(n):
        # Verifier qu'on est dans le viewer de stories
        close = await driver.find_element(contains="Fermer les stories", refresh=True)
        if not close:
            break

        view_time = random.uniform(cfg["highlight_view_min"], cfg["highlight_view_max"])
        log("   story #%d : %.1fs" % (i + 1, view_time))
        await asyncio.sleep(view_time)
        stories_watched += 1

        # Taper a droite pour passer a la story suivante
        if i < n - 1:
            await driver.ht.tap(340, 400)
            await asyncio.sleep(1)

    # Fermer le viewer
    close = await driver.find_element(contains="Fermer les stories", clickable=True, refresh=True)
    if close:
        tap = close.get("tap", {})
        await driver.ht.tap(tap["x"], tap["y"])
    else:
        await driver.ht.swipe(187, 400, 187, 700, 300)  # swipe down
    await driver.wait('transition')
    await asyncio.sleep(1)

    stats["highlights_watched"] = stories_watched
    log("   %d stories a la une regardees" % stories_watched)


async def _browse_reels_tab(driver, navigator, cfg, stats, log, max_time):
    """Ouvre l'onglet reels du profil et regarde quelques reels."""
    log("   ouvre onglet reels")

    # Taper l'onglet Reels
    reels_tab = await driver.find_element(text="Reels", clickable=True, refresh=True)
    if not reels_tab:
        log("   onglet reels non trouve")
        return
    tap = reels_tab.get("tap", {})
    await driver.ht.tap(tap["x"], tap["y"])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Scroll pour voir les reels
    await driver.scroll_down('light')
    await asyncio.sleep(1)

    # Trouver les miniatures de reels
    els = await driver.refresh_elements(clickable_only=True)
    reel_els = []
    for e in els:
        text = e.get("text", "") or ""
        rect = e.get("rect", {})
        if rect.get("width", 0) < 200 and rect.get("height", 0) > 150:
            reel_els.append(e)
        elif "reel" in text.lower() or "vid" in text.lower():
            reel_els.append(e)

    n_reels = min(
        random.randint(cfg["reels_browse_min"], cfg["reels_browse_max"]),
        len(reel_els) if reel_els else 1
    )

    if not reel_els:
        # Taper sur le premier element visible dans la grille
        await driver.ht.tap(62, 280)
        await asyncio.sleep(2)
        # Regarder ce reel
        view_time = random.uniform(cfg["reel_view_min"], cfg["reel_view_max"])
        log("   reel: %.1fs" % view_time)
        await asyncio.sleep(view_time)
        stats["reels_watched"] = stats.get("reels_watched", 0) + 1

        # Like ?
        if random.random() < cfg["reel_like_pct"]:
            # Double tap pour liker
            await driver.ht.tap(187, 400)
            await asyncio.sleep(0.15)
            await driver.ht.tap(187, 400)
            await asyncio.sleep(1)
            stats["liked"] = stats.get("liked", 0) + 1
            log("   like reel (double tap)")

        await navigator.go_back()
        await driver.wait('transition')
        await asyncio.sleep(1)
    else:
        start = time.time()
        opened = 0
        for i in range(n_reels):
            if time.time() - start > max_time:
                break

            reel = random.choice(reel_els)
            tap = reel.get("tap", {})
            await driver.ht.tap(tap["x"], tap["y"])
            await asyncio.sleep(2)

            view_time = random.uniform(cfg["reel_view_min"], cfg["reel_view_max"])
            log("   reel #%d : %.1fs" % (i + 1, view_time))
            await asyncio.sleep(view_time)
            opened += 1

            # Like ?
            if random.random() < cfg["reel_like_pct"]:
                await driver.ht.tap(187, 400)
                await asyncio.sleep(0.15)
                await driver.ht.tap(187, 400)
                await asyncio.sleep(1)
                stats["liked"] = stats.get("liked", 0) + 1
                log("   like reel (double tap)")

            # Swipe up pour reel suivant ou retour
            if i < n_reels - 1:
                await driver.scroll_down('strong')
                await asyncio.sleep(1.5)
            else:
                await navigator.go_back()
                await driver.wait('transition')
                await asyncio.sleep(1)

            reel_els = [r for r in reel_els if r != reel]

        stats["reels_watched"] = stats.get("reels_watched", 0) + opened

    # Revenir a l'onglet grille
    grille = await driver.find_element(text="Grille", clickable=True, refresh=True)
    if grille:
        tap = grille.get("tap", {})
        await driver.ht.tap(tap["x"], tap["y"])
        await asyncio.sleep(1)

    log("   %d reels regardes" % stats.get("reels_watched", 0))


async def _detect_post_type(driver):
    """Detecte le type du post ouvert : photo, video, carousel."""
    els = await driver.find_elements(refresh=True, clickable=None)
    has_video = False
    has_photo = False
    has_commande = False
    for e in els:
        text = (e.get("text", "") or "").lower()
        if "vid" in text and "de " in text:
            has_video = True
        if "photo de " in text:
            has_photo = True
        if "commande reglable" in text or "commande r" in text:
            has_commande = True
        if "reel de " in text:
            has_video = True
    # Carousel = commande reglable sans video ni photo identifiee
    if has_commande and not has_video and not has_photo:
        return "carousel"
    if has_video:
        return "video"
    return "photo"


def _view_time_for_type(post_type):
    """Temps de visionnage adapte au type de post."""
    if post_type == 'video':
        return random.uniform(5.0, 15.0)
    elif post_type == 'carousel':
        return random.uniform(4.0, 8.0)  # par slide, on ajoutera les swipes
    else:
        return random.uniform(2.0, 5.0)


async def _handle_carousel(driver, log):
    """Swipe horizontal pour voir les slides d un carousel."""
    n_slides = random.randint(1, 3)
    for i in range(n_slides):
        await asyncio.sleep(random.uniform(1.5, 3.5))
        log("   swipe carousel (%d)" % (i + 1))
        sw = driver.ht.screen_w
        sh = driver.ht.screen_h
        # Swipe gauche dans la zone media
        await driver.ht.swipe(
            sw * 0.75, sh * 0.40,
            sw * 0.25, sh * 0.40,
            random.randint(300, 500)
        )
        await asyncio.sleep(random.uniform(1.0, 2.5))


async def _interact_post(driver, navigator, cfg, stats, log):
    """Regarde le post ouvert, interagit selon le type et la config."""
    post_type = _detect_post_type(driver)
    view_time = _view_time_for_type(post_type)
    log("   %s — lecture %.1fs" % (post_type, view_time))
    await asyncio.sleep(view_time)
    stats["posts_opened"] += 1

    # Carousel : swipe horizontal
    if post_type == 'carousel':
        _handle_carousel(driver, log)

    # Lire les commentaires
    if random.random() < cfg.get("read_comments_pct", 0.15):
        comment_els = await driver.find_elements(contains='commentaire', clickable=True, refresh=True)
        comment_btn = None
        for ce in comment_els:
            ct = (ce.get('text', '') or '')
            cr = ce.get('rect', {})
            # Le bouton commentaire fait ~40px, pas le compteur
            if cr.get('width', 0) >= 30 and cr.get('height', 0) >= 30 and 'commentaire' in ct.lower():
                comment_btn = ce
                break
        if comment_btn:
            tap_c = comment_btn.get('tap', {})
            log("   ouvre commentaires")
            await driver.ht.tap(tap_c['x'], tap_c['y'])
            await asyncio.sleep(2)
            # Lire un peu
            read_t = random.uniform(2.0, 5.0)
            await asyncio.sleep(read_t)
            # Fermer les commentaires via bouton Fermer
            log("   ferme commentaires")
            if not await driver.tap_element(text="Fermer"):
                # Fallback : swipe down
                sw = driver.ht.screen_w
                sh = driver.ht.screen_h
                await driver.ht.swipe(sw * 0.5, sh * 0.3, sw * 0.5, sh * 0.85, random.randint(300, 500))
            await asyncio.sleep(1.5)
            # Verifier
            screen = await driver.detect_current_screen()
            if screen not in ('post_view', 'profile'):
                log("   ! bloque apres commentaires, recovery")
                _ensure_on_profile(driver, navigator, username, log)

    # Like
    if random.random() < cfg["like_pct"]:
        # Double-tap sur le media (plus naturel en vue post)
        sh = driver.ht.screen_h
        sw = driver.ht.screen_w
        await driver.ht.double_tap(
            sw * 0.5 + random.gauss(0, 20),
            sh * 0.40 + random.gauss(0, 20)
        )
        log("   like (double-tap)")
        stats["liked"] += 1
        await driver.wait('tap')


async def _find_grid_posts(driver, username=""):
    """Trouve les posts dans la grille du profil."""
    els = await driver.refresh_elements(clickable_only=True)
    post_els = []
    for e in els:
        text = e.get('text', '') or ''
        if any(text.startswith(p) for p in ('Video de ', 'Vid\u00e9o de ', 'Photo de ', 'photos ou')):
            rect = e.get('rect', {})
            if rect.get('width', 0) < 200:
                if username and username.lower() not in text.lower():
                    continue
                post_els.append(e)
    return post_els


async def _ensure_on_profile(driver, navigator, username, log):
    """Verifie qu on est sur le profil ou la vue post. Corrige sinon."""
    screen = await driver.detect_current_screen()
    if screen in ('profile', 'post_view'):
        return screen
    log("   ! ecran=%s, retour au profil" % screen)
    # Essayer retour arriere
    for _ in range(3):
        await navigator.go_back()
        await driver.wait('transition')
        await asyncio.sleep(1)
        screen = await driver.detect_current_screen()
        if screen in ('profile', 'post_view'):
            return screen
    # Dernier recours : rouvrir le profil
    log("   ! perdu, reouverture profil @%s" % username)
    await navigator.search_and_open_profile(username)
    await asyncio.sleep(2)
    return await driver.detect_current_screen()


async def _ensure_post_view(driver, navigator, username, log):
    """Verifie qu on est en vue post. Retourne True si oui."""
    screen = await driver.detect_current_screen()
    if screen == 'post_view':
        return True
    if screen == 'profile':
        return False  # on est sur la grille, pas un post
    # Perdu ailleurs
    log("   ! ecran=%s apres navigation" % screen)
    _ensure_on_profile(driver, navigator, username, log)
    return False


async def _browse_posts(driver, navigator, cfg, stats, log, max_time, username=""):
    """Browse les posts du profil avec 3 patterns de navigation.

    feed_scroll (40%) : scroll au post suivant/precedent dans la vue post
    grid_browse (35%) : retour grille, scroll, tap nouveau post
    quick_pick  (25%) : retour grille, tap direct sur un post visible
    """
    start = time.time()
    n_posts = random.randint(cfg["browse_posts_min"], cfg["browse_posts_max"])

    # Scroll pour voir la grille
    await driver.scroll_down('normal')
    await driver.wait('read_short')

    if n_posts == 0:
        return

    # Verifier qu on est bien sur le profil
    screen = _ensure_on_profile(driver, navigator, username, log)
    if screen not in ('profile', 'post_view'):
        log("   ! pas sur le profil, abandon browse")
        return

    post_els = _find_grid_posts(driver, username)
    if not post_els:
        log("   pas de posts dans la grille")
        return

    # Ouvrir le premier post
    first = random.choice(post_els)
    first_text = (first.get('text', '') or '')[:40]
    log("   ouvre post '%s'" % first_text)
    await driver.ht.tap(first['tap']['x'], first['tap']['y'])
    await driver.wait('transition')
    await asyncio.sleep(1)

    # Verifier qu on est en vue post
    if not _ensure_post_view(driver, navigator, username, log):
        log("   ! vue post non atteinte")
        return

    opened = 0
    seen_in_grid = {id(first)}
    in_post_view = True

    for cycle in range(n_posts):
        if time.time() - start > max_time:
            break

        if not in_post_view:
            # Verifier qu on est sur la grille
            screen = await driver.detect_current_screen()
            if screen != 'profile':
                screen = _ensure_on_profile(driver, navigator, username, log)
                if screen != 'profile':
                    break

            post_els = _find_grid_posts(driver, username)
            unseen = [p for p in post_els if id(p) not in seen_in_grid]
            if not unseen:
                unseen = post_els
            if not unseen:
                break
            pick = random.choice(unseen)
            pick_text = (pick.get('text', '') or '')[:40]
            log("   ouvre post '%s'" % pick_text)
            await driver.ht.tap(pick['tap']['x'], pick['tap']['y'])
            await driver.wait('transition')
            await asyncio.sleep(1)

            if not _ensure_post_view(driver, navigator, username, log):
                in_post_view = False
                continue

            seen_in_grid.add(id(pick))
            in_post_view = True

        # Regarder et interagir avec le post
        _interact_post(driver, navigator, cfg, stats, log)
        opened += 1

        if time.time() - start > max_time:
            break

        if cycle >= n_posts - 1:
            break

        # Choisir le pattern pour le post suivant
        pattern = random.choices(
            ["feed_scroll", "grid_browse", "quick_pick"],
            weights=[40, 35, 25],
        )[0]

        if pattern == "feed_scroll":
            direction = random.choices(["down", "up"], weights=[75, 25])[0]
            if direction == "down":
                log("   [nav] scroll au post suivant")
                await driver.scroll_down("normal")
            else:
                log("   [nav] scroll au post precedent")
                await driver.scroll_up("light")
            await driver.wait("scroll")
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # Verifier qu on est toujours en vue post
            screen = await driver.detect_current_screen()
            if screen == "post_view":
                # Centrer le media du nouveau post
                posts = driver.detect_visible_posts()
                if posts:
                    new_post = posts[0]
                    mp = new_post.get(media_pos)
                    if mp:
                        my = mp.get(y, 400)
                        target = driver.ht.screen_h * 0.45
                        if abs(my - target) > driver.ht.screen_h * 0.12:
                            driver.scroll_to_y(new_post[username], target_y=target, tol=driver.ht.screen_h*0.12, max_moves=2)
                            log("   [nav] centrage media")
                in_post_view = True
            elif screen == "profile":
                in_post_view = False
                continue
            else:
                _ensure_on_profile(driver, navigator, username, log)
                in_post_view = False
                continue

        elif pattern == "grid_browse":
            log("   [nav] retour grille + scroll")
            await navigator.go_back()
            await driver.wait('transition')
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Verifier qu on est sur la grille
            screen = await driver.detect_current_screen()
            if screen == 'profile':
                n_scrolls = random.randint(1, 2)
                for _ in range(n_scrolls):
                    await driver.scroll_down('light')
                    await asyncio.sleep(random.uniform(0.8, 2.0))
                in_post_view = False
            elif screen == 'post_view':
                # go_back n a pas marche, on est encore dans le post
                in_post_view = True
            else:
                _ensure_on_profile(driver, navigator, username, log)
                in_post_view = False

        elif pattern == "quick_pick":
            log("   [nav] retour grille")
            await navigator.go_back()
            await driver.wait('transition')
            await asyncio.sleep(random.uniform(0.3, 1.0))

            screen = await driver.detect_current_screen()
            if screen == 'profile':
                in_post_view = False
            elif screen == 'post_view':
                in_post_view = True
            else:
                _ensure_on_profile(driver, navigator, username, log)
                in_post_view = False

    # S assurer qu on revient a la grille du profil
    for _ in range(3):
        screen = await driver.detect_current_screen()
        if screen == 'profile':
            break
        if screen == 'post_view':
            await navigator.go_back()
            await driver.wait('transition')
            await asyncio.sleep(0.5)
        else:
            _ensure_on_profile(driver, navigator, username, log)
            break
