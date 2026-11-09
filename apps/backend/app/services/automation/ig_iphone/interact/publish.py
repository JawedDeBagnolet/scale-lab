"""
ig_iphone/interact/publish.py — Publication sur Instagram.

Flows : post feed, story, reel.
Le contenu (photo/video) doit etre dans la galerie de l'iPhone.

Usage:
    from app.services.automation.ig_iphone.interact.publish import publish_feed_post, publish_story, publish_reel
    publish_feed_post(driver, navigator, caption="Hello!", log=print)
"""

import random
import asyncio
import time


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _open_create_menu(driver, navigator, log):
    """Ouvre le menu de creation depuis le profil (bouton '+')."""
    await navigator.go_profile()
    await asyncio.sleep(1)
    # Le bouton "+" s'appelle "Appuyez pour ouvrir le menu de création"
    plus_el = await driver.find_element(contains="menu de cr", clickable=True, refresh=True)
    if not plus_el:
        log("   ! bouton creation non trouve")
        return False
    tap = plus_el.get('tap', {})
    log("   tap menu creation")
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1)
    return True


async def _select_photo(driver, log, index=0):
    """Selectionne une photo dans la galerie (par index, 0 = premiere)."""
    els = await driver.find_elements(contains="Miniature photo", clickable=True, refresh=True)
    if not els:
        log("   ! aucune photo dans la galerie")
        return False
    idx = min(index, len(els) - 1)
    tap = els[idx].get('tap', {})
    log("   selectionne photo #%d" % idx)
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('tap')
    await asyncio.sleep(1)
    return True


async def _select_video(driver, log, index=0):
    """Selectionne une video dans la galerie."""
    els = await driver.find_elements(contains="Miniature vidéo", clickable=True, refresh=True)
    if not els:
        # Fallback : les videos peuvent avoir "Miniature photo" aussi
        els = await driver.find_elements(contains="Miniature", clickable=True, refresh=True)
    if not els:
        log("   ! aucune video dans la galerie")
        return False
    idx = min(index, len(els) - 1)
    tap = els[idx].get('tap', {})
    log("   selectionne video #%d" % idx)
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('tap')
    await asyncio.sleep(1)
    return True


async def _tap_suivant(driver, log):
    """Tape sur le bouton 'Suivant' (haut ou bas de l ecran)."""
    els = await driver.find_elements(text="Suivant", clickable=True, refresh=True)
    if els:
        # Prendre le dernier visible (souvent en bas dans l editeur)
        best = els[-1]
        tap = best.get('tap', {})
        log("   -> Suivant (y=%d)" % tap.get('y', 0))
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(2)
        return True
    log("   ! bouton Suivant non trouve")
    return False


async def _dismiss_privacy_popup(driver, log):
    """Ferme le popup de partage de publications (s'il apparait)."""
    ok_el = await driver.find_element(text="OK", clickable=True, refresh=True)
    if ok_el:
        rect = ok_el.get('rect', {})
        if rect.get('width', 0) >= 200:  # Le gros bouton OK, pas un petit
            tap = ok_el.get('tap', {})
            log("   dismiss popup vie privee")
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('transition')
            await asyncio.sleep(1)
            return True
    return False


async def _write_caption(driver, log, caption):
    """Ecrit la legende du post naturellement, puis ferme le clavier."""
    if not caption:
        return True
    el = await driver.find_element(contains="Ajouter une l", clickable=True, refresh=True)
    if not el:
        log("   ! champ legende non trouve")
        return False
    tap = el.get('tap', {})
    log("   tap champ legende")
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('tap')
    await asyncio.sleep(0.5)
    # Ecriture naturelle (caractere par caractere avec delai)
    log("   ecriture legende (%d chars)" % len(caption))
    await driver.type_text(caption, method="slow")
    await asyncio.sleep(1)
    # Valider la legende : tap "OK" (en haut a droite)
    ok_el = await driver.find_element(text="OK", clickable=True, refresh=True)
    if ok_el:
        tap2 = ok_el.get('tap', {})
        log("   valide legende (OK)")
        await driver.ht.tap(tap2['x'], tap2['y'])
    else:
        ok_el = await driver.find_element(contains="Termin", clickable=True, refresh=True)
        if ok_el:
            tap2 = ok_el.get('tap', {})
            log("   valide legende (Termine)")
            await driver.ht.tap(tap2['x'], tap2['y'])
        else:
            log("   ferme clavier (tap haut)")
            await driver.ht.tap(driver.ht.screen_w * 0.5, 50)
    await driver.wait('tap')
    await asyncio.sleep(2)
    return True


async def _tap_partager(driver, log):
    """Tape sur le bouton 'Partager' pour publier."""
    el = await driver.find_element(text="Partager", clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        log("   -> Partager")
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        # Attendre l upload (25-30s pour images, plus pour video)
        log("   attente upload...")
        await asyncio.sleep(25)
        return True
    log("   ! bouton Partager non trouve")
    return False


# ── Publication Feed ──────────────────────────────────────────────────────────

async def publish_feed_post(driver, navigator, caption="", photo_index=0, location=None, log=print):
    """Publie un post dans le feed.

    Args:
        caption: texte de la legende
        photo_index: index de la photo dans la galerie (0 = premiere)
        location: nom du lieu (optionnel, pas encore implemente)

    Returns:
        dict {published, duration_s}
    """
    start = time.time()
    stats = {"published": False, "type": "feed_post", "duration_s": 0}

    log("-> Publication feed post")

    # 1. Menu creation → Publication
    if not _open_create_menu(driver, navigator, log):
        return stats
    pub_el = await driver.find_element(text="Publication", clickable=True, refresh=True)
    if not pub_el:
        log("   ! option Publication non trouvee")
        return stats
    tap = pub_el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # 2. Selectionner une photo
    if not _select_photo(driver, log, photo_index):
        return stats

    # 3. Suivant (galerie → editeur)
    if not _tap_suivant(driver, log):
        return stats

    # 4. Suivant (editeur → caption)
    if not _tap_suivant(driver, log):
        return stats

    # 5. Popup vie privee
    _dismiss_privacy_popup(driver, log)

    # 6. Ecrire la legende
    _write_caption(driver, log, caption)

    # 7. Partager
    if _tap_partager(driver, log):
        stats["published"] = True
        log("   post publie!")

    stats["duration_s"] = round(time.time() - start)
    return stats


# ── Story ─────────────────────────────────────────────────────────────────────

async def publish_story(driver, navigator, photo_index=0, caption=None, stickers=None, log=print):
    """Publie une story avec stickers optionnels.

    Args:
        photo_index: index de la photo dans la galerie
        caption: legende optionnelle
        stickers: dict de stickers a ajouter, ex:
            {
                "link": {"url": "https://...", "text": "Mon lien"},
                "poll": {"question": "Tu preferes?", "options": ["A", "B"]},
                "question": "Posez-moi une question",
                "location": "Paris",
                "music": "Espresso",
            }
    """
    start = time.time()
    stats = {"published": False, "type": "story", "duration_s": 0}

    log("-> Publication story")

    # 1. Menu creation → Story
    if not _open_create_menu(driver, navigator, log):
        return stats
    story_el = await driver.find_element(text="Story", clickable=True, refresh=True)
    if not story_el:
        log("   ! option Story non trouvee")
        return stats
    tap = story_el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # 2. Selectionner une photo
    if not _select_photo(driver, log, photo_index):
        return stats
    await asyncio.sleep(2)

    # 2b. Dismiss popup (partage de story, etc.)
    await navigator._dismiss_popups()
    await asyncio.sleep(1)

    # 3. Editeur story : ajouter legende si demandee
    if caption:
        caption_el = await driver.find_element(contains="Ajoutez une l", clickable=True, refresh=True)
        if caption_el:
            tap = caption_el.get('tap', {})
            log("   tap champ legende story")
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
            await asyncio.sleep(0.5)
            log("   ecriture legende (%d chars)" % len(caption))
            await driver.type_text(caption, method="natural")
            await asyncio.sleep(1)
            await driver.ht.tap(driver.ht.screen_w * 0.5, 100)
            await driver.wait('tap')
            await asyncio.sleep(0.5)

    # 3b. Ajouter les stickers
    if stickers:
        from app.services.automation.ig_iphone.interact.story_stickers import (
            add_link_sticker, add_poll_sticker, add_question_sticker,
            add_location_sticker, add_music_sticker,
        )
        if "link" in stickers:
            link = stickers["link"]
            if isinstance(link, dict):
                add_link_sticker(driver, link.get("url", ""), text=link.get("text"), log=log)
            else:
                add_link_sticker(driver, str(link), log=log)

        if "poll" in stickers:
            poll = stickers["poll"]
            if isinstance(poll, dict):
                add_poll_sticker(driver, poll.get("question", ""), options=poll.get("options"), log=log)
            else:
                add_poll_sticker(driver, str(poll), log=log)

        if "question" in stickers:
            q = stickers["question"]
            add_question_sticker(driver, question=q if q else None, log=log)

        if "location" in stickers:
            add_location_sticker(driver, stickers["location"], log=log)

        if "music" in stickers:
            add_music_sticker(driver, song=stickers["music"] if stickers["music"] else None, log=log)


    # 4. Partager dans votre story
    share_el = await driver.find_element(contains="Partager dans votre story", clickable=True, refresh=True)
    if share_el:
        tap = share_el.get('tap', {})
        log("   -> Partager dans votre story")
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(3)
        stats["published"] = True
        log("   story publiee!")
    else:
        # Fallback : bouton "Partager" generique ou options de partage
        share_opt = await driver.find_element(contains="options de partage", clickable=True, refresh=True)
        if share_opt:
            tap = share_opt.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('transition')
            await asyncio.sleep(1)
            # Tap le gros bouton Partager
            if _tap_partager(driver, log):
                stats["published"] = True
                log("   story publiee!")

    stats["duration_s"] = round(time.time() - start)
    return stats


# ── Reel ──────────────────────────────────────────────────────────────────────

async def publish_reel(driver, navigator, caption="", video_index=0, log=print):
    """Publie un reel.

    Args:
        caption: texte de la legende
        video_index: index de la video dans la galerie

    Returns:
        dict {published, duration_s}
    """
    start = time.time()
    stats = {"published": False, "type": "reel", "duration_s": 0}

    log("-> Publication reel")

    # 1. Menu creation → Reel
    if not _open_create_menu(driver, navigator, log):
        return stats
    reel_el = await driver.find_element(text="Reel", clickable=True, refresh=True)
    if not reel_el:
        log("   ! option Reel non trouvee")
        return stats
    tap = reel_el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # 2. Selectionner une video
    if not _select_video(driver, log, video_index):
        return stats

    # 3. Suivant (galerie → editeur)
    if not _tap_suivant(driver, log):
        return stats

    # 4. Editeur reel (audio, texte, etc.) → Suivant
    await asyncio.sleep(1)
    if not _tap_suivant(driver, log):
        return stats

    # 5. Popup vie privee
    _dismiss_privacy_popup(driver, log)

    # 6. Ecrire la legende
    _write_caption(driver, log, caption)

    # 7. Partager
    if _tap_partager(driver, log):
        stats["published"] = True
        log("   reel publie!")

    stats["duration_s"] = round(time.time() - start)
    return stats


# ── Carousel ──────────────────────────────────────────────────────────────────

async def publish_carousel(driver, navigator, caption="", photo_count=2, log=print):
    """Publie un carousel (multi-photo).

    Args:
        caption: texte de la legende
        photo_count: nombre de photos a selectionner (les plus recentes)

    Returns:
        dict {published, duration_s}
    """
    start = time.time()
    stats = {"published": False, "type": "carousel", "duration_s": 0}

    log("-> Publication carousel (%d photos)" % photo_count)

    # 1. Menu creation -> Publication
    if not _open_create_menu(driver, navigator, log):
        return stats
    pub_el = await driver.find_element(text="Publication", clickable=True, refresh=True)
    if not pub_el:
        log("   ! option Publication non trouvee")
        return stats
    tap = pub_el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # 2. Activer multi-select
    sel_el = await driver.find_element(contains="lectionner", clickable=True, refresh=True)
    if not sel_el:
        log("   ! bouton Selectionner non trouve")
        return stats
    tap = sel_el.get('tap', {})
    log("   mode multi-select")
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(1.5)

    # 2b. Dismiss popup "Partager plus"
    await navigator._dismiss_popups()
    await asyncio.sleep(1)

    # 3. Selectionner les photos (la 1ere est deja selectionnee)
    photos = await driver.find_elements(contains="Miniature photo", clickable=True, refresh=True)
    # Filtrer camera et elements trop hauts
    photos = [p for p in photos if p.get('rect', {}).get('y', 0) > 500]
    log("   %d photos disponibles" % len(photos))

    # Selectionner photos 2 a N (la 1ere est deja cochee)
    selected = 1
    for i in range(1, min(photo_count, len(photos))):
        tap = photos[i].get('tap', {})
        log("   selectionne photo #%d" % (i + 1))
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(0.8)
        selected += 1

    log("   %d photos selectionnees" % selected)

    # 4. Suivant (galerie -> editeur)
    if not _tap_suivant(driver, log):
        return stats

    # 5. Editeur -> Suivant
    if not _tap_suivant(driver, log):
        return stats

    # 5b. Dismiss privacy popup
    _dismiss_privacy_popup(driver, log)
    await navigator._dismiss_popups()
    await asyncio.sleep(1)

    # 6. Ecrire la legende
    _write_caption(driver, log, caption)

    # 7. Partager
    if _tap_partager(driver, log):
        stats["published"] = True
        log("   carousel publie!")

    stats["duration_s"] = round(time.time() - start)
    return stats
