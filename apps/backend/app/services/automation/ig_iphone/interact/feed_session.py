"""
ig_iphone/interact/feed_session.py — Session feed Instagram.

Scroll naturel, like, pause lecture, skip sponsorise.
Parametrable via un dict de config (comme les presets X).

Usage:
    from app.services.automation.ig_iphone.interact.feed_session import run_feed_session
    run_feed_session(driver, navigator, config={}, log=print)
"""

import random

import asyncio
import time
from datetime import datetime




# ── Detection langue caption ──────────────────────────────────────────────
_LANG_WORDS = {
    "FR": {"de","le","la","les","et","est","un","une","en","du","des","que","je","tu","il","elle","nous","avec","pour","pas","sur","mon","ma","mes","ton","cette","qui","dans","ce","au"},
    "US": {"the","is","and","for","with","this","that","are","was","you","have","has","not","but","from","they","been","will","your","all","can","had","her","one","our","out","just"},
    "ES": {"el","los","las","una","del","por","con","para","como","pero","sus","mas","este","esta","todo","han","muy","tiene","fue","ser","hay","cuando","desde","entre"},
    "DE": {"der","die","das","und","ist","ein","eine","den","dem","mit","auf","fur","von","sich","nicht","auch","noch","nach","wird","bei","aus","wie","nur","aber","hat"},
    "IT": {"il","lo","la","gli","le","di","del","che","non","con","per","una","sono","suo","sua","anche","come","piu","questo","questa","tutti","dal","nel","alla"},
    "PT": {"que","nao","uma","para","com","por","mais","dos","das","foi","tem","como","seu","sua","nos","ele","ela","mas","isso","este","esta","muito","bem","aqui"},
    "UK": {"the","is","and","for","with","this","that","are","was","you","have","has","not","but","from","they","been","will","your","all","can","had","her","one","our","out","just"},
}
_MARKET_LANG = {"FR":"FR","US":"US","UK":"UK","GB":"UK","ES":"ES","DE":"DE","IT":"IT","PT":"PT","BR":"PT","CA":"FR","BE":"FR","CH":"FR","NL":"DE","IE":"UK","AU":"UK","MX":"ES"}

def _detect_lang(text):
    """Detecte la langue d un texte court. Retourne le code marche ou None."""
    if not text or len(text) < 10:
        return None
    words = set(text.lower().split())
    best, best_score = None, 0
    for lang, kw in _LANG_WORDS.items():
        score = len(words & kw)
        if score > best_score:
            best, best_score = lang, score
    return best if best_score >= 2 else None

async def _market_matches(detected_lang, account_market):
    """Verifie si la langue detectee correspond au marche du compte."""
    if not detected_lang:
        return True  # pas assez de texte pour juger -> on interagit
    expected = _MARKET_LANG.get(account_market.upper(), account_market.upper())
    return detected_lang == expected

DEFAULT_CONFIG = {
    "duration_min": 5,
    "duration_max": 10,
    "like_pct": 0.15,
    "double_tap_like_pct": 0.4,
    "comment_read_pct": 0.08,
    "comment_write_pct": 0.03,
    "comment_emoji_pct": 0.6,
    "save_pct": 0.02,
    "follow_pct": 0.0,
    "visit_profile_pct": 0.03,   # proba de visiter le profil depuis le feed
    "skip_sponsored": True,
    "market": "FR",
    "market_filter": True,
    "market_skip_pct": 0.7,  # proba de skip si mauvais marche
    "scroll_intensity": "normal",
    "read_pause_min": 1.5,
    "read_pause_max": 5.0,
    "video_watch_pct": 0.6,
    "video_watch_min": 3.0,
    "video_watch_max": 12.0,
    "scroll_back_pct": 0.05,
    "hesitate_like_pct": 0.3,
    "pause_long_pct": 0.08,
    "pause_long_min": 8.0,
    "pause_long_max": 20.0,
}


# Distances de scroll, en fraction de la hauteur d'ecran. Une seule
# primitive de geste : c'est la DISTANCE qui varie, continument, pas un
# profil choisi parmi trois. Le moteur ajoute sa propre variabilite sur la
# duree, la derive et la forme du geste.
SCROLL_RANGES = {
    "open":      (0.45, 0.75),   # premier scroll de la session
    "advance":   (0.60, 0.90),   # secours : aucun post exploitable a l'ecran
    "back_up":   (0.15, 0.35),   # relecture : on remonte un peu
    "back_down": (0.18, 0.38),   # ... et on redescend, jamais du meme montant
    "read":      (0.20, 0.40),   # lecture dans un panneau (commentaires)
}


async def _scroll(driver, kind, up=False):
    """Scroll d'une distance tiree dans la plage de `kind`."""
    lo, hi = SCROLL_RANGES[kind]
    d = driver.ht.screen_h * random.uniform(lo, hi)
    return await driver.scroller.scroll_by(-d if up else d)


def _pick_intensity():
    return random.choices(
        ["light", "normal", "normal", "strong", "flick"],
        weights=[15, 40, 25, 15, 5],
    )[0]


async def run_feed_session(driver, navigator, config=None, task=None, log=print,
                           abort_check=None):
    """Execute une session feed IG complete.

    Args:
        config: dict de parametres manuels
        task: dict de la task (pour resolution preset)
    Returns: dict de stats {posts_seen, likes, comments_read, duration_s, ...}
    """
    from app.services.automation.ig_iphone.behavior.presets import resolve_behavior, apply_behavior

    cfg = {**DEFAULT_CONFIG, **(config or {})}
    task = task or {}

    # Resoudre et appliquer un preset comportement
    behavior = resolve_behavior(task, cfg, log)
    if behavior:
        cfg = apply_behavior(cfg, behavior, log)

    duration_s = random.uniform(cfg["duration_min"] * 60, cfg["duration_max"] * 60)

    stats = {
        "posts_seen": 0,
        "likes": 0,
        "double_tap_likes": 0,
        "button_likes": 0,
        "comments_read": 0,
        "comments_written": 0,
        "saves": 0,
        "_recovery_fails": 0,
        "_lost_count": 0,
        "aborted": None,
        "follows": 0,
        "sponsored_skipped": 0,
        "market_skipped": 0,
        "scroll_backs": 0,
        "behavior": behavior.get("name", "default") if behavior else "default",
        "behavior_id": behavior.get("id", "") if behavior else "",
        "started_at": datetime.now().isoformat(),
        "duration_s": 0,
    }
    seen = set()
    start = time.time()

    bname = stats["behavior"]
    log("=" * 50)
    log("SESSION FEED IG [%s] (%d-%dmin, like=%.0f%%)" % (
        bname, cfg["duration_min"], cfg["duration_max"], cfg["like_pct"] * 100))
    log("=" * 50)

    # Health check avant session
    health = check_account_health(log=log)
    if not health["ok"]:
        log("   ! compte en %s — session annulee" % health["status"])
        stats["aborted"] = health["status"]
        return stats

    await navigator.open_instagram()
    screen = await navigator.where_am_i()
    if screen != 'feed':
        await navigator.go_home()

    _scroll(driver, 'open')
    await driver.wait('read_short')

    while True:
        elapsed = time.time() - start
        if elapsed >= duration_s:
            break

        # Check abort
        if abort_check:
            abort_check()

        log("\n[%s] %d/%ds — %d posts, %d likes" % (
            datetime.now().strftime("%H:%M:%S"),
            int(elapsed), int(duration_s),
            stats["posts_seen"], stats["likes"]))

        # Anti-pattern : longue pause
        if random.random() < cfg["pause_long_pct"]:
            pause = random.uniform(cfg["pause_long_min"], cfg["pause_long_max"])
            log("   [anti] longue pause %.1fs" % pause)
            await asyncio.sleep(pause)
            continue

        # Anti-pattern : scroll back
        if stats["posts_seen"] > 2 and random.random() < cfg["scroll_back_pct"]:
            log("   [anti] scroll back")
            _scroll(driver, 'back_up', up=True)
            await driver.wait('read_short')
            stats["scroll_backs"] += 1
            _scroll(driver, 'back_down')
            await driver.wait('scroll')
            continue

        # Avancer au post suivant
        intensity = _pick_intensity()
        post = driver.cycle_next_post(seen=seen, intensity=intensity)
        if not post:
            log("   pas de post -> avance")
            _scroll(driver, 'advance')
            await driver.wait('scroll')
            # Recovery : verifier qu'on est toujours sur le feed
            post2 = driver.cycle_next_post(seen=seen, intensity='strong')
            if not post2:
                screen = await navigator.where_am_i()
                stats["_recovery_fails"] += 1
                log("   ! toujours pas de post (ecran=%s) -> recovery %d/3"
                    % (screen, stats["_recovery_fails"]))
                if screen != 'feed':
                    stats["_lost_count"] += 1
                    if not await navigator.ensure_feed(log=log):
                        log("   !! retour au feed impossible -> fin de session")
                        stats["aborted"] = "lost_off_feed"
                        break
                if stats["_lost_count"] >= 3:
                    log("   !! perdu hors feed 3 fois -> fin de session")
                    stats["aborted"] = "lost_repeatedly"
                    break
                if stats["_recovery_fails"] >= 3:
                    log("   !! 3 recoveries sans post -> fin de session anticipee")
                    stats["aborted"] = "recovery_failed"
                    break
                continue
            post = post2
        stats["_recovery_fails"] = 0   # post trouve : compteur remis a zero

        stats["posts_seen"] += 1
        username = post.get('username', '?')
        is_video = post.get('is_video', False)
        is_sponsored = post.get('is_sponsored', False)

        log("   @%s %s%s likes=%d comments=%d" % (
            username,
            "video" if is_video else "photo",
            " [SPONSO]" if is_sponsored else "",
            post.get('likes', 0),
            post.get('comments', 0)))

        if is_sponsored and cfg["skip_sponsored"]:
            log("   -> skip sponsorise")
            stats["sponsored_skipped"] += 1
            await driver.wait('micro')
            continue

        # Un post nul signifie qu'aucun post n'est lisible : ecran recouvert
        # (consentement, popup, story) ou parsing en echec. Ce n'est pas une
        # erreur fatale — on passe au suivant plutot que de lever.
        # Ciblage marche : detecter la langue de la caption
        if cfg.get("market_filter"):
            caption_els = await driver.find_elements(refresh=False)
            caption_text = ""
            # media_pos peut exister avec la valeur None (media non localise) :
            # le defaut {} de .get() ne s'applique QUE si la cle est absente.
            post_y = (post.get('media_pos') or {}).get('y', 400)
            for ce in caption_els:
                ct = (ce.get('text') or '')
                cr = ce.get('rect', {})
                cy = cr.get('y', 0)
                # Caption = texte en dessous du media, pas trop loin
                if cy > post_y + 50 and cy < post_y + 300 and len(ct) > 15:
                    if not ct.startswith('J') and 'aime' not in ct[:15]:
                        caption_text = ct
                        break
            if caption_text:
                lang = _detect_lang(caption_text)
                if lang and not _market_matches(lang, cfg.get("market", "FR")):
                    if random.random() < cfg.get("market_skip_pct", 0.7):
                        log("   -> skip marche (%s != %s)" % (lang, cfg.get("market", "FR")))
                        stats["market_skipped"] += 1
                        await driver.wait('micro')
                        continue

        # Pause lecture
        if is_video and random.random() < cfg["video_watch_pct"]:
            watch = random.uniform(cfg["video_watch_min"], cfg["video_watch_max"])
            log("   regarder video %.1fs" % watch)
            await asyncio.sleep(watch)
        else:
            pause = random.uniform(cfg["read_pause_min"], cfg["read_pause_max"])
            await asyncio.sleep(pause)

        # Like
        safe_y_min = driver.ht.screen_h * 0.12
        safe_y_max = driver.ht.screen_h * 0.88

        if random.random() < cfg["like_pct"]:
            if random.random() < cfg["hesitate_like_pct"]:
                hesitate = random.uniform(0.5, 2.0)
                log("   [anti] hesitation %.1fs" % hesitate)
                await asyncio.sleep(hesitate)

            if random.random() < cfg["double_tap_like_pct"] and post.get('media_pos'):
                mx = post['media_pos']['x']
                my = post['media_pos']['y']
                if safe_y_min < my < safe_y_max:
                    log("   double-tap like @%s" % username)
                    await driver.ht.double_tap(
                        mx + random.gauss(0, 20),
                        my + random.gauss(0, 20)
                    )
                    stats["double_tap_likes"] += 1
                    stats["likes"] += 1
                    await driver.wait('tap')
                else:
                    log("   ! double-tap skip (media hors zone y=%d)" % my)
            else:
                # Trouver le bouton J'aime le plus proche du media
                media_y = (post.get('media_pos') or {}).get('y', 400)
                like_els = await driver.find_elements(text="J'aime", clickable=True, refresh=True)
                best_like = None
                best_dist = float('inf')
                for el in like_els:
                    el_y = el.get('tap', {}).get('y', 0)
                    el_w = el.get('rect', {}).get('width', 0)
                    # Le bouton like fait ~40px de large, pas le compteur
                    if el_w < 30 or el_w > 100:
                        continue
                    # Doit etre SOUS le media et dans la zone safe
                    if el_y > media_y and safe_y_min < el_y < safe_y_max:
                        d = abs(el_y - media_y)
                        if d < best_dist:
                            best_dist = d
                            best_like = el

                if best_like:
                    tap = best_like.get('tap', {})
                    rect = best_like.get('rect', {})
                    log("   like @%s (bouton y=%d)" % (username, tap.get('y', 0)))
                    await driver.ht.tap(tap['x'], tap['y'],
                                  bounds=(rect.get('width', 40), rect.get('height', 48)))
                    stats["button_likes"] += 1
                    stats["likes"] += 1
                    await driver.wait('tap')
                else:
                    log("   ! pas de bouton like valide")

        # Lire commentaires
        if random.random() < cfg["comment_read_pct"] and post.get('comments', 0) > 0:
            log("   ouvre commentaires @%s" % username)
            await driver.tap_element(contains='commentaire')
            await driver.wait('transition')
            read_time = random.uniform(3.0, 8.0)
            await asyncio.sleep(read_time / 2)
            _scroll(driver, 'read')
            await asyncio.sleep(read_time / 2)
            # Ecrire un commentaire IA ?
            if random.random() < cfg.get("comment_write_pct", 0.03):
                try:
                    from app.services.automation.ig_iphone.interact.comments import generate_comment, post_comment as _pc
                    _cap = ""
                    for _ce in await driver.find_elements(refresh=False):
                        _ct = (_ce.get("text") or "")
                        if username.lower() in _ct.lower()[:30] and len(_ct) > 30:
                            _cap = _ct
                            break
                    _ai = generate_comment(caption=_cap, persona=cfg.get("persona"), market=cfg.get("market", "FR"), log=log)
                    if _ai:
                        _pc(driver, _ai, log=log)
                        stats["comments_written"] = stats.get("comments_written", 0) + 1
                except Exception as _e:
                    log("   comment AI skip: %s" % str(_e)[:40])
            # Fermer les commentaires (swipe down sur IG iOS)
            log("   ferme commentaires")
            await driver.ht.swipe(
                driver.ht.screen_w * 0.5,
                driver.ht.screen_h * 0.3,
                driver.ht.screen_w * 0.5,
                driver.ht.screen_h * 0.85,
                random.randint(300, 500)
            )
            await asyncio.sleep(1.5)  # attendre la fin de l'animation
            # Verifier qu'on est bien sur le feed
            if await navigator.where_am_i() != 'feed':
                stats["_lost_count"] += 1
                if not await navigator.ensure_feed(log=log):
                    log("   !! retour au feed impossible -> fin de session")
                    stats["aborted"] = "lost_off_feed"
                    break
            stats["comments_read"] += 1

        # Enregistrer
        if random.random() < cfg["save_pct"]:
            log("   save @%s" % username)
            _tapped = await driver.tap_element(contains='Enregistrer')
            await driver.wait('tap')
            # Le libelle "Enregistrer" existe aussi hors du post (lien vers la
            # collection) : un mauvais match ouvre la bibliotheque et sort du
            # feed. On verifie, et on revient si besoin.
            _scr = await driver.detect_current_screen(refresh=True)
            if _tapped and _scr != 'feed':
                log("   ! save: derive hors feed (ecran=%s) -> retour" % _scr)
                stats["_lost_count"] += 1
                if not await navigator.ensure_feed(log=log):
                    log("   !! retour au feed impossible -> fin de session")
                    stats["aborted"] = "lost_off_feed"
                    break
            else:
                stats["saves"] += 1

        # Visiter le profil depuis le feed (tap sur username)
        if random.random() < cfg.get("visit_profile_pct", 0):
            log("   visite profil @%s depuis feed" % username)
            visited = await navigator.visit_from_post(username, post_y=(post.get('media_pos') or {}).get('y'))
            if visited:
                await asyncio.sleep(random.uniform(3.0, 8.0))
                # Maybe follow
                if random.random() < cfg["follow_pct"]:
                    follow_el = await driver.find_element(text="Suivre", clickable=True, refresh=True)
                    if follow_el:
                        rect = follow_el.get('rect', {})
                        if rect.get('width', 0) >= 60:
                            tap = follow_el.get('tap', {})
                            log("   follow @%s" % username)
                            await driver.ht.tap(tap['x'], tap['y'])
                            await driver.wait('tap')
                            stats["follows"] += 1
                await navigator.go_back()
                await driver.wait('transition')
                await asyncio.sleep(1)

    elapsed = time.time() - start
    stats["duration_s"] = round(elapsed)
    stats["ended_at"] = datetime.now().isoformat()

    log("\n" + "=" * 50)
    log("FIN SESSION FEED")
    log("  Duree: %ds (%dmin)" % (stats["duration_s"], stats["duration_s"] // 60))
    log("  Posts vus: %d" % stats["posts_seen"])
    log("  Likes: %d (double-tap: %d, bouton: %d)" % (
        stats["likes"], stats["double_tap_likes"], stats["button_likes"]))
    log("  Commentaires lus: %d" % stats["comments_read"])
    log("  Sponsorises passes: %d" % stats["sponsored_skipped"])
    log("  Marche passes: %d" % stats.get("market_skipped", 0))
    log("  Commentaires ecrits: %d" % stats.get("comments_written", 0))
    log("  Scroll-backs: %d" % stats["scroll_backs"])
    log("=" * 50)

    return stats
