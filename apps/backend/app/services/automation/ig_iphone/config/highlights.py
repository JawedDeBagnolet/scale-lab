"""
ig_iphone/config/highlights.py — Gestion des stories a la une.

Creer, modifier, supprimer, archiver les highlights.

Ported from VPS (516 lines) — adapted to async.
"""

import asyncio
from typing import Callable


async def _long_press_highlight(driver, navigator, log, highlight_index=0) -> bool:
    """Long press sur un highlight pour ouvrir le menu contextuel."""
    await navigator.go_profile()
    await asyncio.sleep(1)

    bar = None
    for attempt in range(3):
        els = await driver.find_elements(refresh=True, clickable=True)
        for e in els:
            t = (e.get('text', '') or '')
            if 'Barre des contenus' in t:
                bar = e
                break
        if bar:
            break
        log("   scroll pour trouver highlights (%d)" % (attempt + 1))
        await driver.scroll_down('light')
        await asyncio.sleep(2)

    if not bar:
        log("   ! barre des highlights non trouvee")
        return False

    r = bar.get('rect', {})
    bar_y = r.get('y', 555)
    bar_h = r.get('height', 98)
    bar_center_y = bar_y + bar_h / 2

    if bar_center_y > 500:
        log("   barre trop basse (y=%d), scroll" % bar_center_y)
        await driver.scroll_down('normal')
        await asyncio.sleep(2)
        els = await driver.find_elements(refresh=True, clickable=True)
        for e in els:
            if 'Barre des contenus' in (e.get('text', '') or ''):
                bar = e
                r = bar.get('rect', {})
                bar_y = r.get('y', 400)
                bar_h = r.get('height', 98)
                bar_center_y = bar_y + bar_h / 2
                break

    hl_x = 100 + highlight_index * 80
    hl_y = bar_center_y

    log("   long press highlight #%d (x=%d, y=%d)" % (highlight_index, hl_x, hl_y))
    await driver.ht.long_press(hl_x, hl_y, duration_ms=1000)
    await asyncio.sleep(1.5)

    menu = await driver.find_element(contains="Modifier la story", refresh=True)
    if not menu:
        menu = await driver.find_element(contains="Supprimer la story", refresh=True)
    if not menu:
        log("   ! menu contextuel non apparu")
        return False

    return True


async def delete_highlight(driver, navigator, highlight_index=0, log: Callable = print) -> bool:
    """Supprime un highlight."""
    log("-> Highlight: supprimer #%d" % highlight_index)
    if not await _long_press_highlight(driver, navigator, log, highlight_index):
        return False

    el = await driver.find_element(contains="Supprimer la story", clickable=True, refresh=True)
    if not el:
        log("   ! option supprimer non trouvee")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(1.5)

    confirm = await driver.find_element(text="Supprimer", clickable=True, refresh=True)
    if confirm:
        r = confirm.get('rect', {})
        if r.get('width', 0) >= 200:
            tap = confirm.get('tap', {})
            log("   confirme suppression")
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(2)

    log("   highlight supprime")
    return True


async def archive_highlight(driver, navigator, highlight_index=0, log: Callable = print) -> bool:
    """Archive un highlight."""
    log("-> Highlight: archiver #%d" % highlight_index)
    if not await _long_press_highlight(driver, navigator, log, highlight_index):
        return False

    el = await driver.find_element(contains="Archiver la story", clickable=True, refresh=True)
    if not el:
        log("   ! option archiver non trouvee")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(2)

    log("   highlight archive")
    return True


async def modify_highlight(driver, navigator, highlight_index=0, new_name=None,
                           add_stories=None, remove_stories=None, cover_index=None,
                           cover_photo_index=None, log: Callable = print) -> bool:
    """Modifie un highlight — renomme, ajoute/retire stories, change couverture."""
    log("-> Highlight: modifier #%d%s%s%s%s%s" % (
        highlight_index,
        " nom='%s'" % new_name if new_name else "",
        " +%d stories" % len(add_stories) if add_stories else "",
        " -%d stories" % len(remove_stories) if remove_stories else "",
        " cover=#%d" % cover_index if cover_index is not None else "",
        " cover_photo=#%d" % cover_photo_index if cover_photo_index is not None else ""))

    if not await _long_press_highlight(driver, navigator, log, highlight_index):
        return False

    el = await driver.find_element(contains="Modifier la story", clickable=True, refresh=True)
    if not el:
        log("   ! option modifier non trouvee")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(1.5)

    # Renommer
    if new_name:
        name_field = await driver.find_element(contains="Nom", clickable=True, refresh=True)
        if name_field:
            tap = name_field.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.5)
            clear = await driver.find_element(contains="Effacer", clickable=True, refresh=True)
            if clear:
                tap = clear.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.3)
            else:
                for _ in range(30):
                    await driver.ht._call("press_key", {"key": "backspace"})
                await asyncio.sleep(0.3)
            await driver.type_text(new_name, method="natural")
            await asyncio.sleep(0.5)
            await driver.ht.tap(driver.ht.screen_w / 2, 57)
            await asyncio.sleep(0.5)
            log("   nom -> '%s'" % new_name)

    # Retirer des stories
    if remove_stories:
        stories = []
        all_els = await driver.find_elements(refresh=True, clickable=True)
        for e in all_els:
            t = (e.get('text', '') or '')
            r = e.get('rect', {})
            if 'Photo de' in t and r.get('height', 0) > 100:
                stories.append(e)
        for idx in remove_stories:
            if idx < len(stories):
                tap = stories[idx].get('tap', {})
                log("   retire story #%d" % idx)
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.5)

    # Ajouter des stories
    if add_stories:
        stories_tab = await driver.find_element(text="Stories", clickable=True, refresh=True)
        if stories_tab:
            tap = stories_tab.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1)
        stories = []
        all_els = await driver.find_elements(refresh=True, clickable=True)
        for e in all_els:
            t = (e.get('text', '') or '')
            r = e.get('rect', {})
            if 'Photo de' in t and r.get('height', 0) > 100:
                stories.append(e)
        for idx in add_stories:
            if idx < len(stories):
                tap = stories[idx].get('tap', {})
                log("   ajoute story #%d" % idx)
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.5)

    # Changer la couverture
    if cover_index is not None:
        cover_btn = await driver.find_element(contains="Modifier la couverture", clickable=True, refresh=True)
        if cover_btn:
            tap = cover_btn.get('tap', {})
            log("   ouvre modification couverture")
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1.5)

            if cover_index == -1:
                perso = await driver.find_element(contains="photo de couverture", clickable=True, refresh=True)
                if perso:
                    tap = perso.get('tap', {})
                    log("   photo personnalisee")
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(2)
                    photos = await driver.find_elements(contains="Miniature", clickable=True, refresh=True)
                    for p in photos:
                        r = p.get('rect', {})
                        if 500 < r.get('y', 0) < 700:
                            tap = p.get('tap', {})
                            log("   selectionne photo")
                            await driver.ht.tap(tap['x'], tap['y'])
                            await asyncio.sleep(1)
                            break
                    done = await driver.find_element(text="Terminé", clickable=True, refresh=True)
                    if done:
                        tap = done.get('tap', {})
                        log("   -> Termine (galerie)")
                        await driver.ht.tap(tap['x'], tap['y'])
                        await asyncio.sleep(1.5)
            else:
                thumbs = []
                all_els = await driver.find_elements(refresh=True, clickable=True)
                for e in all_els:
                    r = e.get('rect', {})
                    if r.get('y', 0) > 680 and r.get('height', 0) < 60 and r.get('width', 0) < 60:
                        thumbs.append(e)
                thumbs.sort(key=lambda e: e.get('rect', {}).get('x', 0))
                if cover_index < len(thumbs):
                    tap = thumbs[cover_index].get('tap', {})
                    log("   selectionne couverture #%d" % cover_index)
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(1)

            done_cover = await driver.find_element(text="Terminé", clickable=True, refresh=True)
            if done_cover:
                tap = done_cover.get('tap', {})
                log("   -> Termine (couverture)")
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(1.5)

    # Terminer
    done = await driver.find_element(text="Terminé", clickable=True, refresh=True)
    if not done:
        done = await driver.find_element(contains="Termin", clickable=True, refresh=True)
    if done:
        tap = done.get('tap', {})
        log("   -> Termine")
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(5)

    log("   highlight modifie")
    return True


async def rename_highlight(driver, navigator, new_name, highlight_index=0,
                           log: Callable = print) -> bool:
    """Renomme un highlight existant."""
    return await modify_highlight(driver, navigator, highlight_index,
                                  new_name=new_name, log=log)


async def add_story_to_highlight(driver, navigator, highlight_index=0,
                                 story_indices=None, log: Callable = print) -> bool:
    """Ajoute des stories a un highlight existant."""
    return await modify_highlight(driver, navigator, highlight_index,
                                  add_stories=story_indices or [0], log=log)


async def create_highlight(driver, navigator, name, story_indices=None,
                           log: Callable = print) -> bool:
    """Cree un nouveau highlight."""
    log("-> Highlight: creer '%s'" % name)
    if story_indices is None:
        story_indices = [0]

    await navigator.go_profile()
    await asyncio.sleep(1)

    new_btn = None
    for attempt in range(3):
        els = await driver.find_elements(refresh=True, clickable=True)
        for e in els:
            t = (e.get('text', '') or '')
            if 'Nouveau' in t and 'banni' not in t.lower():
                new_btn = e
                break
        if new_btn:
            break

        bar = None
        for e in els:
            if 'Barre des contenus' in (e.get('text', '') or ''):
                bar = e
                break
        if bar:
            r = bar.get('rect', {})
            bar_center_y = r.get('y', 555) + r.get('height', 98) / 2
            if bar_center_y > 500:
                log("   barre trop basse (y=%d), scroll" % bar_center_y)
                await driver.scroll_down('normal')
                await asyncio.sleep(2)
                els2 = await driver.find_elements(refresh=True, clickable=True)
                for e2 in els2:
                    if 'Barre des contenus' in (e2.get('text', '') or ''):
                        bar = e2
                        r = bar.get('rect', {})
                        break

            plus_x = r.get('x', 0) + 35
            plus_y = r.get('y', 400) + r.get('height', 98) / 2
            log("   tap '+' dans la barre (x=%d, y=%d)" % (plus_x, plus_y))
            await driver.ht.tap(plus_x, plus_y)
            await asyncio.sleep(2)
            check = await driver.find_element(contains="Ajouter au contenu", refresh=True)
            if check:
                log("   ecran creation OK")
                new_btn = True
                break

        if not new_btn:
            log("   scroll pour trouver highlights (%d)" % (attempt + 1))
            await driver.scroll_down('light')
            await asyncio.sleep(2)

    if not new_btn:
        log("   ! bouton nouveau highlight non trouve")
        return False

    if new_btn is not True:
        tap = new_btn.get('tap', {})
        log("   tap nouveau highlight")
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)

    # Selectionner les stories
    stories = []
    all_els = await driver.find_elements(refresh=True, clickable=True)
    for e in all_els:
        t = (e.get('text', '') or '')
        r = e.get('rect', {})
        if 'Photo de' in t and r.get('height', 0) > 100:
            stories.append(e)

    for idx in story_indices:
        if idx < len(stories):
            tap = stories[idx].get('tap', {})
            log("   selectionne story #%d" % idx)
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.5)

    # Suivant
    next_btn = await driver.find_element(text="Suivant", clickable=True, refresh=True)
    if next_btn:
        tap = next_btn.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1.5)

    # Nom
    name_field = await driver.find_element(contains="Nom", clickable=True, refresh=True)
    if not name_field:
        name_field = await driver.find_element(contains="nom du contenu", clickable=True, refresh=True)
    if name_field:
        tap = name_field.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(0.3)
        await driver.type_text(name, method="natural")
        await asyncio.sleep(0.5)

    # Ajouter
    add_btn = await driver.find_element(text="Ajouter", clickable=True, refresh=True)
    if not add_btn:
        add_btn = await driver.find_element(contains="Termin", clickable=True, refresh=True)
    if add_btn:
        r = add_btn.get('rect', {})
        if r.get('width', 0) >= 40:
            tap = add_btn.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(2)

    log("   highlight '%s' cree" % name)
    return True
