"""
screen_atlas.py — Atlas des écrans Instagram pour la navigation iPhone.

Dump l'arbre d'accessibilité de chaque écran clé de l'app pour identifier
les marqueurs uniques. Utilisé pour construire le système de détection d'écran.

Usage depuis le runner:
    from ig_iphone.config.screen_atlas import dump_all_screens
    result = await dump_all_screens(driver, navigator, log=print)
"""

import asyncio
from typing import Callable


async def _dump(driver, log, label):
    """Dump complet de l'arbre d'accessibilité."""
    els = await driver.find_elements(refresh=True)
    log("=" * 60)
    log("DUMP: %s (%d elements)" % (label, len(els)))
    log("=" * 60)
    for e in els:
        t = (e.get('text', '') or '')
        r = e.get('rect', {})
        c = e.get('clickable', False)
        typ = e.get('type', '')
        if t or c:
            log("  %s%s y=%d x=%d w=%d h=%d %s" % (
                '→ ' if c else '  ',
                repr(t[:60]),
                r.get('y', 0), r.get('x', 0),
                r.get('width', 0), r.get('height', 0),
                typ,
            ))
    log("")
    return els


async def dump_current_screen(driver, navigator, log: Callable = print) -> dict:
    """Dump l'écran actuel — utile pour debug ponctuel."""
    return await _dump(driver, log, "ECRAN ACTUEL")


async def dump_all_screens(driver, navigator, log: Callable = print) -> dict:
    """Navigue dans l'app et dumpe chaque écran clé.

    Screens dumpés:
    1. Feed principal
    2. Profil du compte
    3. Modifier le profil
    4. Sous-écran nom
    5. Sous-écran bio
    6. Sous-écran liens (liste)
    7. Sous-écran ajouter un lien
    8. Menu photo de profil (action sheet)
    9. Galerie photos
    10. Paramètres et activité
    11. Type de compte et outils
    12. Autre (sous type de compte)
    13. Âge minimum
    """
    results = {}

    # 1. Feed
    log("\n>>> Navigation: Feed")
    await navigator.go_home()
    await asyncio.sleep(2)
    results['feed'] = await _dump(driver, log, "1. FEED")

    # 2. Profil
    log("\n>>> Navigation: Profil")
    profile_tab = await driver.find_element(text="Profil", clickable=True, refresh=True)
    if profile_tab and profile_tab.get('rect', {}).get('y', 0) > 650:
        tap = profile_tab.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    else:
        await navigator.go_profile()
        await asyncio.sleep(2)
    results['own_profile'] = await _dump(driver, log, "2. PROFIL DU COMPTE")

    # 3. Modifier le profil
    log("\n>>> Navigation: Modifier le profil")
    el = await driver.find_element(text="Modifier le profil", clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2.5)
    results['edit_profile'] = await _dump(driver, log, "3. MODIFIER LE PROFIL")

    # 4. Sous-écran nom
    log("\n>>> Navigation: Champ nom")
    el = await driver.find_element("rénom", contains=True, refresh=True)
    if not el:
        el = await driver.find_element("nom", contains=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['edit_name'] = await _dump(driver, log, "4. SOUS-ECRAN NOM")

    # Retour
    back = await driver.find_element("Retour", clickable=True, refresh=True)
    if back:
        tap = back.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1.5)

    # 5. Sous-écran bio
    log("\n>>> Navigation: Champ bio")
    bio_els = await driver.find_elements(text="Bio", clickable=True, refresh=True)
    best = None
    for e in bio_els:
        w = e.get('rect', {}).get('width', 0)
        if not best or w > best.get('rect', {}).get('width', 0):
            best = e
    if best:
        tap = best.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['edit_bio'] = await _dump(driver, log, "5. SOUS-ECRAN BIO")

    # Retour
    back = await driver.find_element("Retour", clickable=True, refresh=True)
    if not back:
        done = await driver.find_element("fait", contains=True, clickable=True, refresh=True)
        if done:
            tap = done.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1.5)
    else:
        tap = back.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1.5)

    # 6. Sous-écran liens
    log("\n>>> Navigation: Liens")
    el = await driver.find_element("Ajouter des liens", contains=True, refresh=True)
    if not el:
        el = await driver.find_element("liens", contains=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['links_list'] = await _dump(driver, log, "6. LISTE LIENS")

    # Retour à edit profile
    back = await driver.find_element("Modifier le profil", contains=True, clickable=True, refresh=True)
    if back and back.get('rect', {}).get('y', 0) < 80:
        tap = back.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1.5)
    else:
        await navigator.go_back()
        await asyncio.sleep(1.5)

    # 8. Menu photo de profil
    log("\n>>> Navigation: Menu photo")
    el = await driver.find_element("Modifier la photo", contains=True, clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['photo_menu'] = await _dump(driver, log, "8. MENU PHOTO DE PROFIL")

    # Fermer le menu photo (tap outside)
    await driver.ht.tap(187, 300)
    await asyncio.sleep(1.5)

    # Retour au profil
    back = await driver.find_element("Retour", clickable=True, refresh=True)
    if back and back.get('rect', {}).get('y', 0) < 80:
        tap = back.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1.5)

    # 10. Paramètres
    log("\n>>> Navigation: Paramètres")
    el = await driver.find_element("param", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element("activit", contains=True, clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['settings'] = await _dump(driver, log, "10. PARAMETRES")

    # 11. Type de compte et outils
    log("\n>>> Navigation: Type de compte et outils")
    for _ in range(3):
        el = await driver.find_element("Type de compte", contains=True, clickable=True, refresh=True)
        if el:
            break
        await driver.ht.swipe(187, 600, 187, 300, 300)
        await asyncio.sleep(1)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['account_type'] = await _dump(driver, log, "11. TYPE DE COMPTE ET OUTILS")

    # 12. Autre
    log("\n>>> Navigation: Autre")
    el = await driver.find_element("Autre", clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['other'] = await _dump(driver, log, "12. AUTRE")

    # 13. Âge minimum
    log("\n>>> Navigation: Âge minimum")
    el = await driver.find_element("ge minimum", contains=True, clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    results['age_limit'] = await _dump(driver, log, "13. AGE MINIMUM")

    # Retour home
    log("\n>>> Retour au feed")
    for _ in range(5):
        await navigator.go_back()
        await asyncio.sleep(1)

    log("\n" + "=" * 60)
    log("ATLAS COMPLET: %d écrans dumpés" % len(results))
    log("=" * 60)

    return results
