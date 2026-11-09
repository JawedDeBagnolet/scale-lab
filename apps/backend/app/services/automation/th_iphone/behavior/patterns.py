"""
th_iphone/behavior/patterns.py — Anti-patterns Threads (async).

Comportements humains qui rendent la session naturelle :
scroll-back, hesitation, pause distraction, lecture reponses lente,
changement de vitesse de scroll.
"""

import asyncio
import random


async def scroll_back(driver, log):
    """Remonte legerement pour revoir un post passe."""
    dist = random.choice(["light", "light", "normal"])
    log("   [anti] scroll back (%s)" % dist)
    await driver.scroll_up(dist)
    await driver.wait('read_short')
    await asyncio.sleep(random.uniform(1.0, 3.0))
    await driver.scroll_down('light')
    await driver.wait('scroll')


async def pause_distraction(log, min_s=8.0, max_s=20.0):
    """Longue pause comme si l'utilisateur est distrait."""
    d = random.uniform(min_s, max_s)
    log("   [anti] distraction %.1fs" % d)
    await asyncio.sleep(d)


async def hesitate_before_action(log, action_name="like"):
    """Pause d'hesitation avant une action."""
    d = random.uniform(0.5, 2.0)
    log("   [anti] hesitation %.1fs avant %s" % (d, action_name))
    await asyncio.sleep(d)


async def slow_read_caption(log, caption_len=0):
    """Pause de lecture de la caption."""
    base = 2.0 + (caption_len / 100) * 1.5
    d = random.uniform(base, base * 1.8)
    d = min(d, 12.0)
    log("   [anti] lecture caption %.1fs (%d chars)" % (d, caption_len))
    await asyncio.sleep(d)


async def browse_replies_slow(driver, log):
    """Ouvre les reponses et les lit lentement, scroll un peu, puis ferme."""
    log("   [anti] browse reponses lent")
    n_scrolls = random.randint(1, 4)
    for i in range(n_scrolls):
        await asyncio.sleep(random.uniform(2.0, 5.0))
        await driver.scroll_down('light')
    await asyncio.sleep(random.uniform(1.0, 3.0))


async def imprecise_scroll(driver, log):
    """Scroll pas parfait — un peu trop ou pas assez, puis correction."""
    if random.random() < 0.5:
        log("   [anti] scroll trop fort + correction")
        await driver.scroll_down('strong')
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await driver.scroll_up('light')
    else:
        log("   [anti] scroll trop faible + correction")
        await driver.scroll_down('light')
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await driver.scroll_down('light')
    await driver.wait('scroll')


async def double_tap_miss(driver, log, x, y):
    """Simule un double-tap rate — le premier tap est legerement decale."""
    offset_x = random.uniform(-15, 15)
    offset_y = random.uniform(-10, 10)
    log("   [anti] double-tap imprecis (offset %.0f,%.0f)" % (offset_x, offset_y))
    await driver.ht.tap(x + offset_x, y + offset_y)
    await asyncio.sleep(random.uniform(0.08, 0.15))
    await driver.ht.tap(x, y)


async def random_profile_peek(driver, navigator, post, log):
    """Visite rapide du profil depuis un post, comme par curiosite."""
    username = post.get("username", "?")
    log("   [anti] peek profil @%s" % username)

    if await navigator.visit_profile_from_post(post):
        await asyncio.sleep(random.uniform(2.0, 5.0))
        if random.random() < 0.3:
            await driver.scroll_down('light')
            await asyncio.sleep(random.uniform(1.5, 3.0))
        await navigator.go_back()
        await driver.wait('transition')


async def typing_corrections(driver, log, text):
    """Simule des corrections de frappe — ecrit, efface, re-ecrit."""
    split = random.randint(len(text) // 3, len(text) * 2 // 3)
    first_part = text[:split]

    await driver.type_text(first_part, method="slow")
    await asyncio.sleep(random.uniform(0.3, 1.0))

    n_delete = random.randint(1, min(5, len(first_part)))
    log("   [anti] correction: efface %d chars" % n_delete)
    for _ in range(n_delete):
        await driver.ht._call("press_key", {"key": "delete"})
        await asyncio.sleep(random.uniform(0.05, 0.12))

    await asyncio.sleep(random.uniform(0.3, 0.8))

    corrected = text[split - n_delete:]
    await driver.type_text(corrected, method="slow")
