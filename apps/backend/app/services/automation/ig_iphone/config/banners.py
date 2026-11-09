"""
ig_iphone/config/banners.py — Gestion des bannieres de profil IG.

Types : Musique, A remplir, Profil Facebook.

Ported from VPS — adapted to async.
"""

import asyncio
import random
from typing import Callable


async def _open_banners(driver, navigator, log) -> bool:
    """Ouvre l'ecran des bannieres depuis le profil."""
    await navigator.go_profile()
    await asyncio.sleep(1)

    el = await driver.find_element(contains="banni", clickable=True, refresh=True)
    if not el:
        edit = await driver.find_element(contains="Modifier", clickable=True, refresh=True)
        if edit:
            tap = edit.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await asyncio.sleep(1.5)
            await driver.scroll_down('light')
            await asyncio.sleep(1)
            el = await driver.find_element(contains="Banni", clickable=True, refresh=True)

    if not el:
        log("   ! bannieres non trouvees")
        return False

    tap = el.get('tap', {})
    log("   ouvre bannieres")
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(1.5)
    return True


async def add_music_banner(driver, navigator, song=None, log: Callable = print) -> bool:
    """Ajoute une banniere musicale au profil."""
    log("-> Banniere: musique%s" % (" -> '%s'" % song if song else ""))
    if not await _open_banners(driver, navigator, log):
        return False

    el = await driver.find_element(text="Musique", clickable=True, refresh=True)
    if not el:
        log("   ! option Musique non trouvee")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(2)

    if song:
        search = await driver.find_element(contains="Recherche", clickable=True, refresh=True)
        if search:
            tap = search.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.5)
            await driver.type_text(song, method="fast")
            await asyncio.sleep(2)

    # Selectionner le premier morceau
    _skip = ("Enregistrer", "Recherche", "Pour vous", "Populaire",
             "Annuler", "Effacer", "Fermer")
    els = await driver.find_elements(refresh=True, clickable=True)
    for e in els:
        t = (e.get('text', '') or '')
        r = e.get('rect', {})
        if (r.get('width', 0) > 150 and r.get('y', 0) > 180
                and r.get('height', 0) < 25
                and not any(s in t for s in _skip)
                and t and 'reels' not in t.lower()):
            tap = e.get('tap', {})
            log("   selectionne '%s'" % t[:30])
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(2)
            await driver.ht._ensure_screen()
            arrow_x = driver.ht.screen_w - 35
            arrow_y = driver.ht.screen_h * 0.91
            log("   tap fleche confirmation")
            await driver.ht.tap(arrow_x, arrow_y)
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await asyncio.sleep(2)
            break

    done = await driver.find_element(text="Terminé", clickable=True, refresh=True)
    if not done:
        done = await driver.find_element(contains="Termin", clickable=True, refresh=True)
    if done:
        tap = done.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(2)

    log("   banniere musique ajoutee")
    return True


async def add_fill_banner(driver, navigator, text_content, log: Callable = print) -> bool:
    """Ajoute une banniere 'A remplir' au profil."""
    log("-> Banniere: a remplir -> '%s'" % text_content[:20])
    if not await _open_banners(driver, navigator, log):
        return False

    el = await driver.find_element(contains="remplir", clickable=True, refresh=True)
    if not el:
        log("   ! option A remplir non trouvee")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(1.5)

    field = await driver.find_element(contains="Terminez votre", clickable=True, refresh=True)
    if not field:
        field = await driver.find_element(contains="flexion", clickable=True, refresh=True)
    if field:
        tap = field.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(0.5)
        await driver.type_text(text_content[:20], method="natural")
        await asyncio.sleep(0.5)

    save = await driver.find_element(text="Enregistrer", clickable=True, refresh=True)
    if save:
        tap = save.get('tap', {})
        log("   enregistre")
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(3)

    log("   banniere a remplir ajoutee")
    return True


async def _tap_banner_on_profile(driver, navigator, banner_text, log) -> bool:
    """Trouve et tape une banniere sur le profil."""
    await navigator.go_profile()
    await asyncio.sleep(1)

    for attempt in range(3):
        el = await driver.find_element(contains=banner_text, clickable=True, refresh=True)
        if el:
            r = el.get('rect', {})
            if r.get('y', 0) > 650:
                await driver.scroll_down('light')
                await asyncio.sleep(1)
                continue
            tap = el.get('tap', {})
            log("   tap banniere '%s'" % banner_text[:30])
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await asyncio.sleep(1.5)
            return True
        await driver.scroll_down('light')
        await asyncio.sleep(1)

    log("   ! banniere '%s' non trouvee sur le profil" % banner_text)
    return False


async def remove_banner(driver, navigator, banner_text, log: Callable = print) -> bool:
    """Supprime une banniere depuis le profil."""
    log("-> Banniere: supprimer '%s'" % banner_text)
    if not await _tap_banner_on_profile(driver, navigator, banner_text, log):
        return False

    remove = await driver.find_element(contains="Supprimer", clickable=True, refresh=True)
    if remove:
        tap = remove.get('tap', {})
        log("   confirme suppression")
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(1.5)

    log("   banniere supprimee")
    return True


async def modify_banner(driver, navigator, banner_text, new_content=None,
                        log: Callable = print) -> bool:
    """Modifie une banniere depuis le profil."""
    log("-> Banniere: modifier '%s'" % banner_text)
    if not await _tap_banner_on_profile(driver, navigator, banner_text, log):
        return False

    modify = await driver.find_element(contains="Modifier", clickable=True, refresh=True)
    if modify:
        tap = modify.get('tap', {})
        log("   ouvre modification")
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(1.5)

    if new_content:
        is_fill = await driver.find_element(contains="Enregistrer", clickable=True, refresh=True)
        if not is_fill:
            is_fill = await driver.find_element(contains="Obsession", refresh=True)
        if is_fill:
            # Banniere a remplir
            for _ in range(25):
                await driver.ht._call("press_key", {"key": "backspace"})
            await asyncio.sleep(0.3)
            await driver.type_text(new_content[:20], method="natural")
            await asyncio.sleep(0.5)
            save = await driver.find_element(text="Enregistrer", clickable=True, refresh=True)
            if save:
                tap = save.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await asyncio.sleep(1.5)
        else:
            # Banniere musique
            search = await driver.find_element(contains="Recherche", clickable=True, refresh=True)
            if search:
                tap = search.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.5)
                await driver.type_text(new_content, method="fast")
                await asyncio.sleep(2)
            _skip = ("Enregistrer", "Recherche", "Pour vous", "Populaire",
                     "Annuler", "Effacer", "Fermer")
            els = await driver.find_elements(refresh=True, clickable=True)
            for e in els:
                t = (e.get('text', '') or '')
                r = e.get('rect', {})
                if (r.get('width', 0) > 150 and r.get('y', 0) > 180
                        and r.get('height', 0) < 25
                        and not any(s in t for s in _skip)
                        and t and 'reels' not in t.lower()):
                    tap = e.get('tap', {})
                    log("   selectionne '%s'" % t[:30])
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(2)
                    await driver.ht._ensure_screen()
                    await driver.ht.tap(driver.ht.screen_w - 35, driver.ht.screen_h * 0.91)
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    await asyncio.sleep(2)
                    break
            done = await driver.find_element(contains="Termin", clickable=True, refresh=True)
            if done:
                tap = done.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await asyncio.sleep(1.5)

    log("   banniere modifiee")
    return True
