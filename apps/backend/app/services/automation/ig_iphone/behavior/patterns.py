"""
ig_iphone/behavior/patterns.py — Anti-patterns IG.

Comportements humains qui rendent la session naturelle :
scroll-back, hesitation, pause distraction, lecture commentaires lente,
double-tap au lieu du bouton, changement de vitesse de scroll.

Ported from VPS — adapted to async.
"""

import asyncio
import math
import random


async def scroll_back(driver, log):
    """Remonte legerement pour revoir un post passe."""
    dist = random.choice(["light", "light", "normal"])
    log("   [anti] scroll back (%s)" % dist)
    await driver.scroll_up(dist)
    await asyncio.sleep(random.uniform(0.5, 1.5))
    # Petit moment de lecture puis retour
    await asyncio.sleep(random.uniform(1.0, 3.0))
    await driver.scroll_down('light')
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def pause_distraction(log, min_s=8.0, max_s=20.0):
    """Longue pause comme si l'utilisateur est distrait (notification, regarde ailleurs)."""
    d = random.uniform(min_s, max_s)
    log("   [anti] distraction %.1fs" % d)
    await asyncio.sleep(d)


async def hesitate_before_action(log, action_name="like"):
    """Pause d'hesitation avant une action (le pouce survole le bouton)."""
    d = random.uniform(0.5, 2.0)
    log("   [anti] hesitation %.1fs avant %s" % (d, action_name))
    await asyncio.sleep(d)


async def slow_read_caption(log):
    """Pause de lecture de la caption/bio comme si on lit attentivement."""
    d = random.uniform(2.0, 6.0)
    log("   [anti] lecture caption %.1fs" % d)
    await asyncio.sleep(d)


async def browse_comments_slow(driver, navigator, log):
    """Ouvre les commentaires et les lit lentement, scroll un peu, puis ferme."""
    log("   [anti] browse commentaires lent")
    await driver.tap_element(contains='commentaire')
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # Lecture avec scrolls lents
    n_scrolls = random.randint(1, 3)
    for i in range(n_scrolls):
        await asyncio.sleep(random.uniform(2.0, 5.0))
        await driver.scroll_down('light')

    await asyncio.sleep(random.uniform(1.0, 3.0))

    # Fermer
    log("   [anti] ferme commentaires")
    await driver.ht._ensure_screen()
    await driver.ht.swipe(
        driver.ht.screen_w * 0.5,
        driver.ht.screen_h * 0.3,
        driver.ht.screen_w * 0.5,
        driver.ht.screen_h * 0.85,
        random.randint(300, 500)
    )
    await asyncio.sleep(1.5)

    # Verifier qu'on est sur le feed
    screen = await driver.detect_current_screen()
    if screen != 'feed':
        log("   [anti] recovery -> Home")
        await driver.go_home()
        await asyncio.sleep(1)


async def watch_video_variable(log, min_s=3.0, max_s=15.0):
    """Regarde une video avec une duree variable (parfois longtemps, parfois court)."""
    # Distribution log-normale : souvent court, parfois tres long
    mu = math.log((min_s + max_s) / 3)
    sigma = 0.5
    d = min(max_s, max(min_s, random.lognormvariate(mu, sigma)))
    log("   [anti] watch video %.1fs" % d)
    await asyncio.sleep(d)


def change_scroll_speed():
    """Retourne une intensite de scroll aleatoire ponderee.
    Simule le changement de rythme naturel."""
    return random.choices(
        ["light", "normal", "normal", "strong", "flick"],
        weights=[15, 40, 25, 15, 5],
    )[0]


# ── Profil behaviors (analogues aux A/B/C de X) ─────────────────────────────

async def behavior_glance(driver, log):
    """Coup d'oeil rapide — 1-2 petits scrolls, pas d'interaction."""
    n = random.randint(1, 2)
    log("   [behavior] glance (%d scrolls)" % n)
    for _ in range(n):
        await driver.scroll_down('light')
        await asyncio.sleep(random.uniform(0.3, 0.8))


async def behavior_browse(driver, log):
    """Browse + remontee — descend 2-4 fois puis remonte en haut."""
    n = random.randint(2, 4)
    log("   [behavior] browse (%d scrolls + remontee)" % n)
    for _ in range(n):
        await driver.scroll_down(change_scroll_speed())
        await asyncio.sleep(random.uniform(0.5, 1.5))
    # Remontee
    await driver.scroll_up('strong')
    await asyncio.sleep(random.uniform(0.3, 0.8))


async def behavior_deep_read(driver, log):
    """Lecture profonde — s'attarde 8-15s sur un post."""
    d = random.uniform(8.0, 15.0)
    log("   [behavior] deep read %.1fs" % d)
    half = d * random.uniform(0.4, 0.6)
    await asyncio.sleep(half)
    # Petit scroll pendant la lecture
    await driver.scroll_down('light')
    await asyncio.sleep(max(0.0, d - half))


def pick_behavior(last=None):
    """Tire un comportement A/B/C avec penalite de repetition."""
    weights = {"glance": 30, "browse": 50, "deep_read": 20}
    if last in weights:
        weights[last] = int(weights[last] * 0.3)
    keys = list(weights.keys())
    return random.choices(keys, weights=[weights[k] for k in keys])[0]


async def run_behavior(driver, log, behavior):
    """Execute un comportement."""
    if behavior == "glance":
        await behavior_glance(driver, log)
    elif behavior == "browse":
        await behavior_browse(driver, log)
    elif behavior == "deep_read":
        await behavior_deep_read(driver, log)
