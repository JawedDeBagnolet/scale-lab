"""
ig_iphone/interact/publish.py — Publication sur Instagram.

Flows : post feed, story, reel, carousel.
Le contenu (photo/video) doit etre dans la galerie de l'iPhone
(pousse via push_media_to_gallery avec spoof EXIF).

Usage:
    from app.services.automation.ig_iphone.interact.publish import (
        publish_feed_post, publish_story, publish_reel, publish_carousel,
    )
    await publish_feed_post(driver, navigator, caption="Hello!", log=print)
"""

import asyncio
import random
import time
from typing import Callable

from app.services.automation.ig_iphone.config.profile_config import (
    _detect_screen, _dump_screen,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _open_create_menu(driver, navigator, log) -> bool:
    """Ouvre le menu de creation depuis n'importe quel ecran."""
    screen = await _detect_screen(driver, log)
    log("   ecran actuel: '%s'" % screen)

    # Si on est deja dans le menu creation
    if screen == "creation_menu":
        log("   deja dans le menu creation")
        return True

    # Toujours aller au profil d'abord (le bouton "+" du feed est different)
    if screen != "own_profile":
        for nav_try in range(3):
            await navigator.go_profile()
            await asyncio.sleep(2)
            screen = await _detect_screen(driver, log)
            if screen in ("own_profile", "creation_menu"):
                break
            log("   ⚠ navigation profil tentative %d: ecran '%s'" % (nav_try + 1, screen))
            if nav_try < 2:
                await asyncio.sleep(1)
        if screen not in ("own_profile", "creation_menu"):
            log("   ! impossible d'atteindre le profil apres 3 tentatives")
            await _dump_screen(driver, log, "no_profile")
            return False
        if screen == "creation_menu":
            log("   ✓ menu creation ouvert (via nav)")
            return True

    # Chercher le bouton "+" (menu de creation)
    plus_el = await driver.find_element(contains="menu de cr", clickable=True, refresh=True)
    if not plus_el:
        plus_el = await driver.find_element(contains="Cr", clickable=True, refresh=True)
    if not plus_el:
        log("   ! bouton creation non trouve")
        await _dump_screen(driver, log, "no_create_btn")
        return False

    tap = plus_el.get('tap', {})
    log("   tap menu creation (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(2.5, 3.5))

    # Verifier que le menu est apparu (retry 3 fois avec delai)
    for attempt in range(3):
        screen = await _detect_screen(driver, log)
        if screen == "creation_menu":
            break
        # Verifier par presence directe de "Reel" et "Fermer"
        reel_check = await driver.find_element(text="Reel", clickable=True, refresh=True)
        fermer_check = await driver.find_element(text="Fermer", clickable=True)
        if reel_check and fermer_check:
            log("   ✓ menu creation detecte via Reel+Fermer")
            break
        log("   ⚠ tentative %d: ecran '%s'" % (attempt + 1, screen))
        if attempt < 2:
            await asyncio.sleep(1.5)
    else:
        log("   ! menu creation pas ouvert apres 3 tentatives")
        return False

    log("   ✓ menu creation ouvert")
    return True


async def _select_photo(driver, log, index=0) -> bool:
    """Selectionne une photo dans la galerie (par index, 0 = premiere/plus recente)."""
    for attempt in range(3):
        els = await driver.find_elements(contains="Miniature", clickable=True, refresh=True)
        # Filtrer : garder les elements dans la grille (tap.y > 220, exclut header)
        photos = [e for e in els if e.get('tap', {}).get('y', 0) > 220]
        photos.sort(key=lambda e: (e.get('tap', {}).get('y', 0), e.get('tap', {}).get('x', 0)))
        if photos:
            break
        log("   [retry %d] galerie pas encore chargee" % (attempt + 1))
        await asyncio.sleep(1.5)

    if not photos:
        log("   ! aucune photo dans la galerie")
        await _dump_screen(driver, log, "galerie_vide")
        return False

    idx = min(index, len(photos) - 1)
    tap = photos[idx].get('tap', {})
    log("   selectionne photo #%d (y=%d, %d dispo)" % (idx, tap.get('y', 0), len(photos)))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(0.8, 1.5))
    return True


async def _select_video(driver, log, index=0) -> bool:
    """Selectionne une video dans la galerie.

    La grille commence vers y=250-300 (sous le header 'Nouveau reel' et
    les boutons Brouillons/Modeles). On filtre y > 220 pour exclure le
    header et l'element Camera, puis on trie par y puis x pour obtenir
    l'ordre galerie (haut-gauche = plus recent).
    """
    for attempt in range(3):
        els = await driver.find_elements(contains="Miniature", clickable=True, refresh=True)
        # Exclure Camera et garder uniquement les miniatures de la grille
        videos = []
        for e in els:
            txt = (e.get('text', '') or '').lower()
            ty = e.get('tap', {}).get('y', 0)
            if ty < 220:
                continue
            if 'cam' in txt or 'caméra' in txt:
                continue
            videos.append(e)
        # Trier par position tap : haut→bas, gauche→droite (ordre galerie)
        videos.sort(key=lambda e: (e.get('tap', {}).get('y', 0), e.get('tap', {}).get('x', 0)))
        if videos:
            break
        log("   [retry %d] galerie pas encore chargee" % (attempt + 1))
        await asyncio.sleep(1.5)

    if not videos:
        log("   ! aucune video dans la galerie")
        return False

    idx = min(index, len(videos) - 1)
    tap = videos[idx].get('tap', {})
    log("   selectionne video #%d (y=%d, x=%d, %d dispo)" % (idx, tap.get('y', 0), tap.get('x', 0), len(videos)))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(0.8, 1.5))
    return True


async def _tap_suivant(driver, log) -> bool:
    """Tape sur le bouton 'Suivant'."""
    for attempt in range(3):
        els = await driver.find_elements(text="Suivant", clickable=True, refresh=True)
        if els:
            best = els[-1]
            tap = best.get('tap', {})
            log("   -> Suivant (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(2.0, 3.0))
            return True
        log("   [retry %d] bouton Suivant non trouve" % (attempt + 1))
        await asyncio.sleep(1)
    log("   ! bouton Suivant non trouve apres 3 essais")
    await _dump_screen(driver, log, "no_suivant")
    return False


async def _add_audio(driver, log, song_query: str) -> bool:
    """Ajoute un son au reel/carousel depuis l'editeur.

    Flow (d'apres dumps UI IG) :
    1. Tap "Audio" sur l'editeur
    2. Tap champ de recherche
    3. Taper le nom du son
    4. Tap sur le premier resultat
    5. Confirmer la selection (bouton sans label, y > 700)
    6. Tap "C'est fait" sur la page de config audio
    """
    if not song_query:
        return True

    log("   [audio] recherche: '%s'" % song_query[:40])

    # 1. Tap "Audio" sur l'editeur
    audio_el = await driver.find_element(text="Audio", clickable=True, refresh=True)
    if not audio_el:
        log("   [audio] ! bouton Audio non trouve sur l'editeur")
        await _dump_screen(driver, log, "editor_no_audio")
        return False
    tap = audio_el.get('tap', {})
    log("   [audio] tap Audio (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(2.0, 3.0))

    # 2. Tap champ de recherche
    search_tapped = await driver.ht.tap_by_text("Recherche", match="contains")
    if not search_tapped:
        # Fallback: chercher l'element dans l'arbre
        search_el = await driver.find_element(contains="Recherche", clickable=True, refresh=True)
        if search_el:
            tap = search_el.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
        else:
            log("   [audio] ! champ recherche non trouve")
            await _dump_screen(driver, log, "audio_no_search")
            # Fermer et continuer sans audio
            await driver.ht.tap_by_text("Fermer")
            await asyncio.sleep(1)
            return False
    await asyncio.sleep(1)

    # 3. Taper le nom du son
    log("   [audio] ecriture recherche: '%s'" % song_query[:30])
    await driver.ht.type_text(song_query)
    await asyncio.sleep(random.uniform(2.0, 3.0))

    # 4. Tap sur le premier resultat (titre du son, y > 150)
    #    Les resultats ont le format: "TITRE, Explicite" ou juste "TITRE"
    #    Sous chaque titre: "artiste · X K reels · durée"
    for attempt in range(3):
        els = await driver.find_elements(clickable=True, refresh=True)
        # Chercher les elements de resultat (y > 150, pas les filtres/boutons)
        candidates = []
        for e in els:
            txt = (e.get('text', '') or '')
            ty = e.get('tap', {}).get('y', 0)
            # Exclure: filtres (Artiste/Titre/Paroles), boutons (Fermer/Annuler/Effacer/Enregistrer/Recherche)
            if ty < 170 or ty > 790:
                continue
            skip_words = ['fermer', 'annuler', 'effacer', 'enregistrer', 'recherche',
                         'artiste', 'titre', 'paroles', 'vibe', 'type',
                         'pour vous', 'populaire', 'audio d', 'importer']
            if any(w in txt.lower() for w in skip_words):
                continue
            # Garder les elements qui ressemblent a un titre de chanson
            if len(txt) > 2 and '·' not in txt:
                candidates.append(e)

        if candidates:
            # Prendre le premier resultat (le plus haut)
            candidates.sort(key=lambda e: e.get('tap', {}).get('y', 0))
            best = candidates[0]
            tap = best.get('tap', {})
            log("   [audio] tap resultat '%s' (y=%d)" % ((best.get('text', '') or '')[:30], tap.get('y', 0)))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.5, 2.5))
            break
        log("   [audio] [retry %d] aucun resultat" % (attempt + 1))
        await asyncio.sleep(1.5)
    else:
        log("   [audio] ! aucun resultat pour '%s'" % song_query[:30])
        await driver.ht.tap_by_text("Fermer")
        await asyncio.sleep(1)
        return False

    # 5. Confirmer la selection (bouton sans label "Bouton" a y > 700, le plus a droite)
    #    Ce bouton n'a pas de libelle descriptif, on le cherche par position
    await asyncio.sleep(1.5)
    for attempt in range(3):
        els = await driver.find_elements(clickable=True, refresh=True)
        buttons = [e for e in els
                   if (e.get('text', '') or '').lower() in ('bouton', '')
                   and e.get('tap', {}).get('y', 0) > 700
                   and e.get('tap', {}).get('x', 0) > 250]
        if buttons:
            # Prendre le plus a droite (x le plus grand)
            buttons.sort(key=lambda e: e.get('tap', {}).get('x', 0), reverse=True)
            best = buttons[0]
            tap = best.get('tap', {})
            log("   [audio] tap confirmer (y=%d, x=%d)" % (tap.get('y', 0), tap.get('x', 0)))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.5, 2.5))
            break
        # Peut-etre que le son a ete selectionne automatiquement
        fait_el = await driver.find_element(contains="est fait", clickable=True)
        if fait_el:
            log("   [audio] son deja confirme, page config detectee")
            break
        log("   [audio] [retry %d] bouton confirmation non trouve" % (attempt + 1))
        await _dump_screen(driver, log, "audio_no_confirm_%d" % attempt)
        await asyncio.sleep(1)

    # 6. Page config audio → tap "C'est fait"
    for attempt in range(3):
        fait_el = await driver.find_element(contains="est fait", clickable=True, refresh=True)
        if fait_el:
            tap = fait_el.get('tap', {})
            log("   [audio] tap 'C'est fait' (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.5, 2.5))
            log("   [audio] ✓ son ajoute")
            return True
        # Peut-etre pas encore sur la page config
        await asyncio.sleep(1)

    log("   [audio] ⚠ bouton 'C'est fait' non trouve, on continue")
    return True


async def _dismiss_ig_popups(driver, log) -> bool:
    """Ferme les popups connus d'IG (Partager plus, À votre image, Partage de publications)."""
    dismissed = False
    for _ in range(3):
        ok_el = await driver.find_element(text="OK", clickable=True, refresh=True)
        fermer_el = await driver.find_element(text="Fermer", clickable=True)
        partager_plus = await driver.find_element(contains="Partager plus", clickable=False)
        votre_image = await driver.find_element(contains="votre image", clickable=False)
        partage_pub = await driver.find_element(contains="Partage de publications", clickable=False)
        if partager_plus and ok_el:
            tap = ok_el.get('tap', {})
            log("   dismiss popup 'Partager plus' (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1)
            dismissed = True
            continue
        if votre_image and ok_el:
            tap = ok_el.get('tap', {})
            log("   dismiss popup 'À votre image' (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1)
            dismissed = True
            continue
        if partage_pub:
            target = ok_el or fermer_el
            if target:
                tap = target.get('tap', {})
                log("   dismiss popup 'Partage de publications' (y=%d)" % tap.get('y', 0))
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(1)
                dismissed = True
                continue
        break
    return dismissed


async def _dismiss_privacy_popup(driver, log) -> bool:
    """Ferme le popup de partage de publications (ancien + nouveau)."""
    if await _dismiss_ig_popups(driver, log):
        return True
    ok_el = await driver.find_element(text="OK", clickable=True, refresh=True)
    if ok_el:
        rect = ok_el.get('rect', {})
        if rect.get('width', 0) >= 200:
            tap = ok_el.get('tap', {})
            log("   dismiss popup vie privee (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.0, 1.5))
            return True
    return False


async def _write_caption(driver, log, caption) -> bool:
    """Ecrit la legende du post.

    Utilise tap_by_text (MCP tap_element natif) pour ouvrir le champ
    legende — les coordonnees tap_screen ne fonctionnent pas sur ce
    champ texte sur Instagram.
    """
    if not caption:
        return True

    # Taper sur le champ legende via MCP tap_element natif (par texte)
    for attempt in range(3):
        # Verifier que le champ est visible dans l'arbre
        els = await driver.find_elements(contains="Ajouter une l", clickable=True, refresh=True)
        candidates = [e for e in els if e.get('tap', {}).get('y', 0) > 300]
        if not candidates:
            log("   ! champ legende non trouve a y>300 (tentative %d)" % (attempt + 1))
            await _dump_screen(driver, log, "no_caption_%d" % attempt)
            await asyncio.sleep(1.5)
            continue

        log("   tap champ legende via tap_element natif (tentative %d)" % (attempt + 1))
        tapped = await driver.ht.tap_by_text("Ajouter une l", match="contains")
        if not tapped:
            log("   ⚠ tap_element natif echoue, retry")
            await asyncio.sleep(1.5)
            continue
        await asyncio.sleep(1.5)

        # Verifier que le clavier s'est ouvert (header "Legende" ou "OK" visible)
        ok_el = await driver.find_element(text="OK", clickable=True, refresh=True)
        leg_el = await driver.find_element(contains="gende", refresh=True)
        if ok_el or (leg_el and leg_el.get('tap', {}).get('y', 0) < 100):
            log("   ✓ clavier ouvert")
            break
        log("   ⚠ clavier pas ouvert, retry")
    else:
        log("   ! impossible d'ouvrir le champ legende")
        return False

    log("   ecriture legende (%d chars)" % len(caption))
    await driver.ht.type_text(caption)
    await asyncio.sleep(1)
    # Fermer le clavier : tap OK via tap_element natif
    log("   tap OK via tap_element natif")
    ok_tapped = await driver.ht.tap_by_text("OK")
    if not ok_tapped:
        # Fallback coordonnees connues
        log("   ⚠ OK natif echoue, fallback coordonnees (348,66)")
        await driver.ht.tap(348, 66)
    await asyncio.sleep(random.uniform(1.5, 2.5))
    return True


async def _tap_partager(driver, log) -> bool:
    """Tape sur le bouton 'Partager' et attend l'upload."""
    for attempt in range(3):
        el = await driver.find_element(text="Partager", clickable=True, refresh=True)
        if el:
            tap = el.get('tap', {})
            log("   -> Partager (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            # Attendre l'upload (15-30s selon le media)
            log("   attente upload...")
            for wait_i in range(20):
                await asyncio.sleep(2)
                screen = await _detect_screen(driver, log)
                if screen in ("feed", "own_profile"):
                    log("   ✓ upload termine, retour '%s'" % screen)
                    return True
            log("   ⚠ timeout upload (40s)")
            return True  # On considere que c'est OK meme si timeout
        log("   [retry %d] bouton Partager non trouve" % (attempt + 1))
        await asyncio.sleep(1)
    log("   ! bouton Partager non trouve")
    await _dump_screen(driver, log, "no_partager")
    return False


# ── Publication Feed ──────────────────────────────────────────────────────────

async def publish_feed_post(driver, navigator, caption="", photo_index=0,
                            first_comment=None, location=None,
                            log: Callable = print) -> dict:
    """Publie un post dans le feed.

    Args:
        caption: texte de la legende
        photo_index: index de la photo dans la galerie (0 = premiere/plus recente)
        first_comment: premier commentaire a poster apres publication (optionnel)
        location: nom du lieu (optionnel, pas encore implemente)

    Returns:
        dict {published, duration_s, type}
    """
    start = time.time()
    stats = {"published": False, "type": "feed_post", "duration_s": 0}

    log("-> Publication feed post")

    # 1. Menu creation → Publication
    if not await _open_create_menu(driver, navigator, log):
        stats["duration_s"] = round(time.time() - start)
        return stats
    pub_el = await driver.find_element(text="Publication", clickable=True, refresh=True)
    if not pub_el:
        log("   ! option Publication non trouvee")
        await _dump_screen(driver, log, "creation_menu_no_pub")
        stats["duration_s"] = round(time.time() - start)
        return stats
    tap = pub_el.get('tap', {})
    log("   tap Publication (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(2.0, 3.0))

    # 2. Selectionner une photo
    if not await _select_photo(driver, log, photo_index):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 3. Suivant (galerie → editeur)
    if not await _tap_suivant(driver, log):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 4. Suivant (editeur → caption)
    if not await _tap_suivant(driver, log):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 5. Popup vie privee
    await _dismiss_privacy_popup(driver, log)

    # 6. Ecrire la legende
    await _write_caption(driver, log, caption)

    # 7. Partager
    if await _tap_partager(driver, log):
        stats["published"] = True
        log("   ✓ post publie!")
    else:
        log("   ! echec publication")

    stats["duration_s"] = round(time.time() - start)
    return stats


# ── Story ─────────────────────────────────────────────────────────────────────

async def publish_story(driver, navigator, photo_index=0, caption=None,
                        stickers=None, log: Callable = print) -> dict:
    """Publie une story avec stickers optionnels.

    Args:
        photo_index: index de la photo dans la galerie
        caption: legende optionnelle
        stickers: dict de stickers, ex:
            {"link": {"url": "...", "text": "..."}, "poll": {...}, ...}
    """
    start = time.time()
    stats = {"published": False, "type": "story", "duration_s": 0}

    log("-> Publication story")

    # 1. Menu creation → Story
    if not await _open_create_menu(driver, navigator, log):
        stats["duration_s"] = round(time.time() - start)
        return stats
    story_el = await driver.find_element(text="Story", clickable=True, refresh=True)
    if not story_el:
        log("   ! option Story non trouvee")
        stats["duration_s"] = round(time.time() - start)
        return stats
    tap = story_el.get('tap', {})
    log("   tap Story (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(2.0, 3.0))

    # 2. Selectionner une photo
    if not await _select_photo(driver, log, photo_index):
        stats["duration_s"] = round(time.time() - start)
        return stats
    await asyncio.sleep(2)

    # 3. Legende (optionnelle)
    if caption:
        caption_el = await driver.find_element(contains="Ajoutez une l", clickable=True, refresh=True)
        if caption_el:
            tap = caption_el.get('tap', {})
            log("   tap champ legende story (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.5)
            log("   ecriture legende (%d chars)" % len(caption))
            await driver.ht.type_text(caption)
            await asyncio.sleep(1)
            await driver.ht.tap(187, 100)
            await asyncio.sleep(0.5)

    # 4. Stickers
    if stickers:
        try:
            from app.services.automation.ig_iphone.interact.story_stickers import (
                add_link_sticker, add_poll_sticker, add_question_sticker,
                add_location_sticker, add_music_sticker,
            )
            if "link" in stickers:
                link = stickers["link"]
                if isinstance(link, dict):
                    await add_link_sticker(driver, link.get("url", ""), text=link.get("text"), log=log)
                else:
                    await add_link_sticker(driver, str(link), log=log)
            if "poll" in stickers:
                poll = stickers["poll"]
                if isinstance(poll, dict):
                    await add_poll_sticker(driver, poll.get("question", ""), options=poll.get("options"), log=log)
                else:
                    await add_poll_sticker(driver, str(poll), log=log)
            if "question" in stickers:
                await add_question_sticker(driver, question=stickers["question"] or None, log=log)
            if "location" in stickers:
                await add_location_sticker(driver, stickers["location"], log=log)
            if "music" in stickers:
                await add_music_sticker(driver, song=stickers["music"] or None, log=log)
        except Exception as e:
            log("   ⚠ erreur stickers: %s (non bloquant)" % str(e)[:100])

    # 5. Partager dans votre story
    share_el = await driver.find_element(contains="Partager dans votre story", clickable=True, refresh=True)
    if not share_el:
        share_el = await driver.find_element(contains="Votre story", clickable=True, refresh=True)
    if share_el:
        tap = share_el.get('tap', {})
        log("   -> Partager dans votre story (y=%d)" % tap.get('y', 0))
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(3.0, 5.0))
        stats["published"] = True
        log("   ✓ story publiee!")
    else:
        # Fallback : bouton Partager generique
        if await _tap_partager(driver, log):
            stats["published"] = True
            log("   ✓ story publiee!")

    stats["duration_s"] = round(time.time() - start)
    return stats


# ── Reel ──────────────────────────────────────────────────────────────────────

async def publish_reel(driver, navigator, caption="", video_index=0,
                       audio_query: str | None = None,
                       log: Callable = print) -> dict:
    """Publie un reel. Flow complet basé sur le dump de l'arbre UI."""
    start = time.time()
    stats = {"published": False, "type": "reel", "duration_s": 0}

    log("-> Publication reel")

    # 1. Menu creation → Reel
    if not await _open_create_menu(driver, navigator, log):
        stats["duration_s"] = round(time.time() - start)
        return stats
    reel_el = await driver.find_element(text="Reel", clickable=True, refresh=True)
    if not reel_el:
        log("   ! option Reel non trouvee")
        stats["duration_s"] = round(time.time() - start)
        return stats
    tap = reel_el.get('tap', {})
    log("   tap Reel (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(2.0, 3.0))

    # 2. Galerie: selectionner une video
    if not await _select_video(driver, log, video_index):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 3. Suivant (galerie → editeur video)
    if not await _tap_suivant(driver, log):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 4. Editeur video (Audio/Texte/Voix/Sous-titres)
    await asyncio.sleep(1.5)

    # 4a. Ajouter un son si demande
    if audio_query:
        await _add_audio(driver, log, audio_query)
        await asyncio.sleep(1)

    # 4b. Suivant (editeur → page caption ou audio suggestion)
    if not await _tap_suivant(driver, log):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 4b. Attendre la page caption ou skipper la page audio
    await asyncio.sleep(2.5)
    for _try in range(3):
        els = await driver.find_elements(contains="Ajouter une l", clickable=True, refresh=True)
        cap = [e for e in els if e.get('tap', {}).get('y', 0) > 300]
        if cap:
            break  # page caption trouvee
        # Pas sur la page caption → chercher page audio
        ignore_el = await driver.find_element(contains="Ignorer la synchro", clickable=True)
        if ignore_el and ignore_el.get('tap', {}).get('y', 0) > 600:
            t = ignore_el.get('tap', {})
            log("   skip audio (Ignorer y=%d)" % t.get('y', 0))
            await driver.ht.tap(t['x'], t['y'])
            await asyncio.sleep(2.5)
            continue
        suivant_el = await driver.find_element(text="Suivant", clickable=True)
        if suivant_el:
            t = suivant_el.get('tap', {})
            log("   skip audio (Suivant y=%d)" % t.get('y', 0))
            await driver.ht.tap(t['x'], t['y'])
            await asyncio.sleep(2.5)
            continue
        await asyncio.sleep(1.5)

    # 5. Page caption — taper sur le champ et ecrire
    await _write_caption(driver, log, caption)

    # 6. Suivant (page caption → popup "A propos de Reels")
    if not await _tap_suivant(driver, log):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 7. Popup "A propos de Reels" → tap "Partager"
    await asyncio.sleep(1.5)
    if await _tap_partager(driver, log):
        # 8. Possible popup Meta One → fermer
        await asyncio.sleep(2)
        meta_el = await driver.find_element(contains="Meta", clickable=True, refresh=True)
        fermer_el = await driver.find_element(text="Fermer", clickable=True)
        if not fermer_el:
            fermer_el = await driver.find_element(contains="Non merci", clickable=True, refresh=True)
        if fermer_el and meta_el:
            ftap = fermer_el.get('tap', {})
            log("   dismiss popup Meta One (y=%d)" % ftap.get('y', 0))
            await driver.ht.tap(ftap['x'], ftap['y'])
            await asyncio.sleep(1)
        stats["published"] = True
        log("   ✓ reel publie!")

    stats["duration_s"] = round(time.time() - start)
    return stats


# ── Carousel ──────────────────────────────────────────────────────────────────

async def publish_carousel(driver, navigator, caption="", photo_count=2,
                           audio_query: str | None = None,
                           log: Callable = print) -> dict:
    """Publie un carousel (multi-photo)."""
    start = time.time()
    stats = {"published": False, "type": "carousel", "duration_s": 0}

    log("-> Publication carousel (%d photos)" % photo_count)

    # 1. Menu creation → Publication
    if not await _open_create_menu(driver, navigator, log):
        stats["duration_s"] = round(time.time() - start)
        return stats
    pub_el = await driver.find_element(text="Publication", clickable=True, refresh=True)
    if not pub_el:
        log("   ! option Publication non trouvee")
        stats["duration_s"] = round(time.time() - start)
        return stats
    tap = pub_el.get('tap', {})
    log("   tap Publication (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(2.0, 3.0))

    # 2. Activer multi-select
    # Chercher "Sélectionner" exact d'abord, puis par contains avec filtre y > 300
    # (eviter de matcher la barre du haut a y=66 qui contient "Sélection de galerie")
    sel_el = await driver.find_element(text="Sélectionner", clickable=True, refresh=True)
    if not sel_el:
        candidates = await driver.find_elements(contains="lectionner", clickable=True, refresh=True)
        candidates = [c for c in candidates if c.get('tap', {}).get('y', 0) > 300]
        sel_el = candidates[0] if candidates else None
    if not sel_el:
        sel_el = await driver.find_element(contains="Multi", clickable=True, refresh=True)
    if not sel_el:
        log("   ! bouton Selectionner non trouve")
        await _dump_screen(driver, log, "no_multiselect")
        stats["duration_s"] = round(time.time() - start)
        return stats
    tap = sel_el.get('tap', {})
    log("   mode multi-select (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(1.5)

    # 2b. Popup possible apres multi-select ("Partager plus")
    await _dismiss_ig_popups(driver, log)

    # 3. Selectionner les photos (meme logique que _select_video)
    photos = await driver.find_elements(contains="Miniature", clickable=True, refresh=True)
    photos = [p for p in photos
              if p.get('tap', {}).get('y', 0) > 220
              and 'cam' not in (p.get('text', '') or '').lower()]
    photos.sort(key=lambda e: (e.get('tap', {}).get('y', 0), e.get('tap', {}).get('x', 0)))
    log("   %d photos disponibles" % len(photos))

    # La 1ere est deja selectionnee, selectionner les suivantes
    selected = 1
    for i in range(1, min(photo_count, len(photos))):
        tap = photos[i].get('tap', {})
        log("   selectionne photo #%d (y=%d, x=%d)" % (i + 1, tap.get('y', 0), tap.get('x', 0)))
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(0.5, 1.0))
        selected += 1

    log("   %d photos selectionnees" % selected)

    # 4. Suivant (galerie → editeur)
    if not await _tap_suivant(driver, log):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 4b. Popups possibles ("À votre image", etc.)
    await _dismiss_ig_popups(driver, log)

    # 5. Editeur: ajouter un son si demande
    if audio_query:
        await asyncio.sleep(1)
        await _add_audio(driver, log, audio_query)
        await asyncio.sleep(1)

    # 6. Editeur → Suivant
    if not await _tap_suivant(driver, log):
        stats["duration_s"] = round(time.time() - start)
        return stats

    # 7. Popup vie privee
    await _dismiss_privacy_popup(driver, log)

    # 8. Legende
    await _write_caption(driver, log, caption)

    # 9. Partager
    if await _tap_partager(driver, log):
        stats["published"] = True
        log("   ✓ carousel publie!")

    stats["duration_s"] = round(time.time() - start)
    return stats
