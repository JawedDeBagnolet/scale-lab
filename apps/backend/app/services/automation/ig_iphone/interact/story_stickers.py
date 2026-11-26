"""
ig_iphone/interact/story_stickers.py — Stickers avances pour stories IG.

Chaque fonction suppose qu'on est sur l'editeur story (apres selection photo).
Le dump de reference est dans Flow_stories_dump.rtf.

Conventions:
  - "C'est fait" (328, 69) est le bouton de validation principal.
    Il est souvent INVISIBLE dans l'arbre d'accessibilite → fallback coords.
  - Apres ajout d'un sticker lieu, l'ecran freeze → swipe up + fermer menu.
  - Les variantes visuelles d'un sticker se changent en tappant dessus.

Usage:
    from app.services.automation.ig_iphone.interact.story_stickers import (
        add_link_sticker, add_poll_sticker, add_question_sticker,
        add_location_sticker, add_mention_sticker, add_music_sticker,
        add_text_sticker, add_to_highlight, publish_story, open_story_editor,
    )
"""

import asyncio
import random


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

async def _open_stickers(driver, log):
    """Ouvre le panneau de stickers (bouton a droite de l'editeur)."""
    el = await driver.find_element(text="Stickers, bouton", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(text="Stickers", contains=True, clickable=True, refresh=True)
    if not el:
        log("   ! bouton Stickers non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)
    return True


async def _close_stickers(driver, log):
    """Ferme le panneau de stickers."""
    el = await driver.find_element(text="Fermer l'espace stickers", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(text="Fermer", contains=True, clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(0.8)
        return True
    return False


async def _tap_done(driver, log):
    """Tape sur 'C'est fait' — souvent invisible dans l'arbre.

    Cherche d'abord dans l'arbre ("C'est fait", "Terminé"),
    sinon fallback aux coordonnees (328, 69).
    """
    # Chercher dans l'arbre
    el = await driver.find_element(text="C’est fait", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(text="Termin", contains=True, clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        log("   -> C'est fait (%d, %d)" % (tap['x'], tap['y']))
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(1)
        return True

    # Fallback: coordonnees fixes (en haut a droite)
    log("   -> C'est fait (fallback 328, 69)")
    await driver.ht.tap(328, 69)
    await driver.wait('transition')
    await asyncio.sleep(1)
    return True


async def _unfreeze_after_sticker(driver, log):
    """Workaround pour le bug freeze apres ajout d'un sticker lieu.

    Swipe up pour ouvrir le menu stickers, puis le fermer.
    """
    log("   [unfreeze] swipe up + fermer menu")
    await driver.ht.swipe(188, 600, 188, 200, 300)
    await asyncio.sleep(1.5)
    await _close_stickers(driver, log)
    await asyncio.sleep(0.5)


async def _find_sticker_in_menu(driver, name, log):
    """Trouve un sticker par nom dans le panneau ouvert."""
    el = await driver.find_element(text=name, contains=True, clickable=True, refresh=True)
    if not el:
        log("   ! sticker '%s' non trouve dans le menu" % name)
        return None
    return el


async def _human_pause(lo=0.3, hi=0.8):
    """Pause humaine aleatoire."""
    await asyncio.sleep(random.uniform(lo, hi))


# ═══════════════════════════════════════════════════════════════════════════
# Sticker Lieu
# ═══════════════════════════════════════════════════════════════════════════

async def add_location_sticker(driver, location, variant_taps=0, log=print):
    """Ajoute un sticker de lieu a la story.

    Flow: Stickers → Sticker de lieu → (popup OK) → Recherche → Choisir →
          Ajouter → BUG FREEZE → swipe up → fermer menu → retour story.

    Args:
        location: nom du lieu a rechercher (ex: "Lyon", "Tour Eiffel")
        variant_taps: nombre de taps sur le sticker pour changer la variante
    """
    log("   [sticker] lieu -> '%s'" % location)
    if not await _open_stickers(driver, log):
        return False

    el = await _find_sticker_in_menu(driver, "Sticker de lieu", log)
    if not el:
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # Popup localisation (premiere fois) → taper OK
    ok_btn = await driver.find_element(text="OK", clickable=True, refresh=True)
    if ok_btn:
        tap = ok_btn.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(1)

    # Rechercher le lieu
    search = await driver.find_element(text="Rechercher des lieux", contains=True, clickable=True, refresh=True)
    if search:
        tap = search.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await _human_pause()
        await driver.type_text(location, method="fast")
        await asyncio.sleep(2.5)  # attendre les resultats

    # Selectionner le premier resultat de recherche
    # Les resultats sont des lignes comme "Paris, France" entre y=250 et y=550
    # (au-dessus = barre de recherche, en-dessous = clavier)
    results = await driver.find_elements(text=location, contains=True, clickable=True, refresh=True)
    # Filtrer : garder les resultats dans la zone de resultats (pas search bar, pas clavier)
    location_results = [
        r for r in results
        if 240 < r.get('tap', {}).get('y', 0) < 550
        and r.get('text', '').lower() != location.lower()  # exclure le texte tape
    ]
    if not location_results:
        # Fallback: chercher "Nom du lieu" (ancien format)
        results2 = await driver.find_elements(text="Nom du lieu", contains=True, clickable=True, refresh=True)
        location_results = [r for r in results2 if 240 < r.get('tap', {}).get('y', 0) < 700]

    if location_results:
        chosen = location_results[0]
        tap = chosen.get('tap', {})
        log("   selectionne '%s'" % (chosen.get('text', '')[:50]))
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)

        # Si un ecran de confirmation "Ajouter" apparait (apercu carte)
        add_btn = await driver.find_element(text="Ajouter", clickable=True, refresh=True)
        if add_btn:
            # Verifier que c'est pas "Ajouter un lieu" (y < 600)
            add_y = add_btn.get('tap', {}).get('y', 0)
            if add_y > 600:
                tap = add_btn.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(1.5)
    else:
        log("   ! aucun resultat pour '%s'" % location)
        return False

    # BUG FREEZE: l'ecran se fige apres Ajouter → workaround
    await _unfreeze_after_sticker(driver, log)

    # Variantes visuelles (tap sur le sticker pour cycler)
    if variant_taps > 0:
        sticker = await driver.find_element(text="Sticker de lieu", contains=True, clickable=True, refresh=True)
        if sticker:
            tap = sticker.get('tap', {})
            for i in range(variant_taps):
                log("   variante %d/%d" % (i + 1, variant_taps))
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.6)

    log("   sticker lieu ajoute")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Sticker Mention
# ═══════════════════════════════════════════════════════════════════════════

async def add_mention_sticker(driver, username, variant_taps=0, log=print):
    """Ajoute un sticker de mention a la story.

    Flow: Stickers → Sticker de mention → Recherche → Choisir compte →
          "C'est fait" (invisible) → "C'est fait" (visible, 328,69).

    Args:
        username: nom d'utilisateur a mentionner (sans @)
        variant_taps: nombre de taps pour changer la variante visuelle
    """
    log("   [sticker] mention -> @%s" % username)
    if not await _open_stickers(driver, log):
        return False

    el = await _find_sticker_in_menu(driver, "Sticker de mention", log)
    if not el:
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Rechercher le compte
    search = await driver.find_element(text="Rechercher des comptes", contains=True, clickable=True, refresh=True)
    if search:
        tap = search.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await _human_pause()
        await driver.type_text(username, method="fast")
        await asyncio.sleep(2)

    # Selectionner le compte dans les resultats
    # Match exact sur le username recherche, y > 100 (sous la barre de recherche)
    els = await driver.find_elements(clickable=True, refresh=True)
    best = None
    for e in els:
        t = (e.get('text', '') or '').strip()
        tp = e.get('tap', {})
        y = tp.get('y', 0)
        if t.lower() == username.lower() and y > 100:
            best = e
            break

    if best:
        tap = best.get('tap', {})
        log("   selectionne '%s' @ (%d, %d)" % (best.get('text', '')[:30], tap['x'], tap['y']))
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1)
    else:
        log("   ! match exact non trouve pour '%s', fallback premier resultat" % username)
        # Fallback: premier element sous la barre de recherche
        for e in els:
            tp = e.get('tap', {})
            r = e.get('rect', {})
            if tp.get('y', 0) > 100 and r.get('height', 0) > 40:
                t = (e.get('text', '') or '')
                if t and t not in ("Rechercher", "Annuler", "Effacer"):
                    log("   fallback: '%s'" % t[:30])
                    await driver.ht.tap(tp['x'], tp['y'])
                    await asyncio.sleep(1)
                    break

    # "C’est fait" est invisible dans l’arbre sur cet ecran → coords directes
    log("   -> C’est fait (coords 331, 91)")
    await driver.ht.tap(331, 91)
    await driver.wait('transition')
    await asyncio.sleep(0.5)

    # Deuxieme "C’est fait" pour confirmer l’ajout
    log("   -> C’est fait x2 (coords 331, 91)")
    await driver.ht.tap(331, 91)
    await driver.wait('transition')
    await asyncio.sleep(1)

    # Variantes visuelles
    if variant_taps > 0:
        sticker = await driver.find_element(text="Sticker de mention", contains=True, clickable=True, refresh=True)
        if sticker:
            tap = sticker.get('tap', {})
            for i in range(variant_taps):
                log("   variante %d/%d" % (i + 1, variant_taps))
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.6)

    log("   sticker mention ajoute")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Sticker Question (boite a questions)
# ═══════════════════════════════════════════════════════════════════════════

async def add_question_sticker(driver, question=None, log=print):
    """Ajoute un sticker question (boite a questions) a la story.

    Flow: Stickers → Sticker de question → (place directement) →
          tap sur le sticker → ecrire la question → "C'est fait".

    Args:
        question: texte de la question (optionnel, garde le defaut)
    """
    log("   [sticker] question%s" % (" -> '%s'" % question[:30] if question else ""))
    if not await _open_stickers(driver, log):
        return False

    el = await _find_sticker_in_menu(driver, "Sticker de question", log)
    if not el:
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)
    # Le sticker est place directement sur la story

    # Modifier la question si demande
    if question:
        # Le sticker est deja la, on tape dessus pour l'editer
        q_el = await driver.find_element(text="Sticker de question", contains=True, clickable=True, refresh=True)
        if q_el:
            tap = q_el.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1)

        # Trouver le champ texte "Posez-moi une question"
        field = await driver.find_element(text="Posez-moi une question", contains=True, clickable=True, refresh=True)
        if field:
            tap = field.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await _human_pause()
            # Effacer le texte par defaut
            for _ in range(30):
                await driver.ht._call("press_key", {"key": "backspace"})
            await asyncio.sleep(0.3)
            await driver.type_text(question, method="natural")
            await asyncio.sleep(0.5)

        await _tap_done(driver, log)

    log("   sticker question ajoute")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Sticker Sondage
# ═══════════════════════════════════════════════════════════════════════════

async def add_poll_sticker(driver, question, options=None, log=print):
    """Ajoute un sticker sondage a la story.

    Flow: Stickers → Sticker de sondage → Ecrire question →
          Modifier options (Oui/Non par defaut) →
          (optionnel: "Ajoutez une option" pour 3e/4e) → "C'est fait".

    Args:
        question: la question du sondage
        options: liste des options (defaut: on garde Oui/Non)
    """
    log("   [sticker] sondage -> '%s'" % question[:30])
    if not await _open_stickers(driver, log):
        return False

    el = await _find_sticker_in_menu(driver, "Sticker de sondage", log)
    if not el:
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Ecrire la question — champ "POSEZ UNE QUESTION…"
    q_field = await driver.find_element(text="POSEZ UNE QUESTION", contains=True, clickable=True, refresh=True)
    if q_field:
        tap = q_field.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await _human_pause()
        await driver.type_text(question, method="natural")
        await asyncio.sleep(0.5)

    # Modifier les options si fournies
    if options and len(options) >= 1:
        # Option 1 : tap sur "Oui" → le texte disparait, on ecrit directement
        opt1 = await driver.find_element(text="Oui", clickable=True, refresh=True)
        if opt1:
            tap = opt1.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await _human_pause(0.2, 0.4)
            await driver.type_text(options[0], method="natural")
            await asyncio.sleep(0.3)

    if options and len(options) >= 2:
        # Option 2 : tap sur "Non" → idem
        opt2 = await driver.find_element(text="Non", clickable=True, refresh=True)
        if opt2:
            tap = opt2.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await _human_pause(0.2, 0.4)
            await driver.type_text(options[1], method="natural")
            await asyncio.sleep(0.3)

    # Options supplementaires (3e et 4e)
    if options:
        for i in range(2, min(len(options), 4)):
            add_opt = await driver.find_element(text="Ajoutez une option", contains=True, clickable=True, refresh=True)
            if add_opt:
                tap = add_opt.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await _human_pause(0.2, 0.4)
                await driver.type_text(options[i], method="natural")
                await asyncio.sleep(0.3)

    await _tap_done(driver, log)
    log("   sticker sondage ajoute")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Sticker Lien
# ═══════════════════════════════════════════════════════════════════════════

async def add_link_sticker(driver, url, text=None, log=print):
    """Ajoute un sticker lien a la story.

    Flow: Stickers → Sticker à lien → Champ URL (placeholder "https://example.com")
          → Ecrire URL → (optionnel: "Personnaliser le texte du sticker") → "C'est fait".

    Args:
        url: l'URL du lien
        text: texte personnalise du sticker (optionnel)
    """
    log("   [sticker] lien -> %s" % url[:40])
    if not await _open_stickers(driver, log):
        return False

    el = await _find_sticker_in_menu(driver, "Sticker à lien", log)
    if not el:
        # Fallback : chercher juste "lien"
        el = await _find_sticker_in_menu(driver, "lien", log)
    if not el:
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Champ URL — le placeholder est "https://example.com"
    url_field = await driver.find_element(text="https://example.com", contains=True, clickable=True, refresh=True)
    if not url_field:
        url_field = await driver.find_element(text="URL", clickable=True, refresh=True)
    if url_field:
        tap = url_field.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await _human_pause()
        await driver.type_text(url, method="fast")
        await asyncio.sleep(0.5)

    # Personnaliser le texte si demande
    if text:
        await asyncio.sleep(0.5)
        text_btn = await driver.find_element(text="Personnaliser le texte du sticker", contains=True, clickable=True, refresh=True)
        if text_btn:
            tap = text_btn.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await _human_pause()
            await driver.type_text(text, method="natural")
            await asyncio.sleep(0.5)

    await _tap_done(driver, log)
    log("   sticker lien ajoute")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Sticker Musique (Audio)
# ═══════════════════════════════════════════════════════════════════════════

async def add_music_sticker(driver, song=None, artist=None,
                            style=None, clip_duration=None,
                            log=print):
    """Ajoute de la musique a la story via le bouton Audio.

    Flow: Audio → Recherche → Tap titre → Bouton confirmation (337, 750) →
          Config style/duree → "C'est fait".

    Args:
        song: titre du morceau a rechercher
        artist: nom de l'artiste pour verifier (optionnel)
        style: style visuel parmi:
            "uniquement de la musique", "affichage dynamique",
            "machine à écrire", "affichage cube", "karaoké", "bouton musique"
        clip_duration: duree du clip en secondes (ex: 5, 10, 15, 20)
    """
    log("   [sticker] musique%s" % (" -> '%s'" % song[:30] if song else ""))

    # Ouvrir le selecteur audio (bouton a droite de l'editeur)
    el = await driver.find_element(text="Audio, bouton", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(text="Audio", contains=True, clickable=True, refresh=True)
    if not el:
        log("   ! bouton Audio non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # Rechercher le morceau
    if song:
        search = await driver.find_element(text="Recherche", contains=True, clickable=True, refresh=True)
        if search:
            tap = search.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await _human_pause()
            await driver.type_text(song, method="fast")
            await asyncio.sleep(2.5)

    # Trouver le morceau dans les resultats
    # Un morceau = titre (ex: "WALLET, Explicite") + ligne artiste (ex: "Ninho · 2:53")
    _skip = ("Enregistrer", "Annuler", "Fermer", "Recherche", "Pour vous",
             "Populaire", "Audio", "Effacer", "Commande", "Artiste", "Titre",
             "Paroles", "Vibe", "Type", "Emoji", "Dicter", "espace",
             "rechercher", "nombres", "majuscule", "supprimer")
    els = await driver.find_elements(refresh=True, clickable=True)

    songs = []
    for i, e in enumerate(els):
        t = (e.get('text', '') or '')
        r = e.get('rect', {})
        # Titre : largeur > 150, y > 180, pas un bouton connu
        if (r.get('width', 0) > 150 and r.get('y', 0) > 180
                and not any(s.lower() in t.lower() for s in _skip)
                and t and len(t) > 2):
            # Chercher la ligne artiste en dessous (contient "reels" ou "·")
            artist_line = ""
            for j in range(i + 1, min(i + 3, len(els))):
                tj = (els[j].get('text', '') or '')
                if '·' in tj or 'reels' in tj.lower():
                    artist_line = tj
                    break
            songs.append({"title": t, "artist_line": artist_line, "element": e})

    # Matcher le bon morceau
    selected = None
    for s in songs:
        if artist and artist.lower() not in s["artist_line"].lower():
            continue
        selected = s
        break
    if not selected and songs:
        selected = songs[0]
        log("   ! match exact non trouve, prend le premier")
    if not selected:
        log("   ! aucun morceau trouve")
        return False

    # Taper sur le titre pour le selectionner
    tap = selected["element"].get('tap', {})
    log("   selectionne '%s' | %s" % (selected["title"][:30], selected["artist_line"][:30]))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(2)

    # Confirmer la selection : bouton en bas a droite (337, 750)
    # Ce bouton apparait comme "Bouton" dans le dump, pas d'autre identifiant
    confirm = None
    els = await driver.find_elements(clickable=True, refresh=True)
    for e in els:
        t = (e.get('text', '') or '')
        r = e.get('rect', {})
        if ('Bouton' in t and r.get('x', 0) > 300 and r.get('y', 0) > 700):
            confirm = e
            break
    if confirm:
        tap = confirm.get('tap', {})
        log("   confirmation (%d, %d)" % (tap['x'], tap['y']))
        await driver.ht.tap(tap['x'], tap['y'])
    else:
        # Fallback coords
        log("   confirmation (fallback 337, 750)")
        await driver.ht.tap(337, 750)
    await asyncio.sleep(2)

    # --- Ecran de configuration du son ---
    # Styles disponibles dans le dump:
    #   "uniquement de la musique" | "affichage dynamique" |
    #   "machine à écrire" | "affichage cube" | "karaoké" | "bouton musique"
    # Style par defaut: "uniquement de la musique" (pas de sticker visible)
    target = (style or "uniquement de la musique").lower()
    found = False
    for attempt in range(4):
        els = await driver.find_elements(clickable=True, refresh=True)
        for e in els:
            t = (e.get("text", "") or "").lower()
            if target in t or (target == "karaoké" and "karaok" in t):
                tap = e.get("tap", {})
                log("   style: '%s' @ (%d, %d)" % (t.strip()[:30], tap["x"], tap["y"]))
                await driver.ht.tap(tap["x"], tap["y"])
                await asyncio.sleep(1)
                found = True
                break
        if found:
            break
        # Le style cherche est hors ecran → taper sur le premier element
        # visible pour scroller dans sa direction (gauche = debut de la liste)
        style_els = [e for e in els
                     if e.get('tap', {}).get('y', 0) == 541
                     and (e.get('text', '') or '').strip()]
        if style_els:
            first = style_els[0]
            tap = first.get('tap', {})
            log("   navigation styles: tap '%s'" % (first.get('text', '')[:20]))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.8)
    if not found:
        log("   ! style '%s' non trouve" % target)

    # Modifier la duree du clip
    if clip_duration:
        all_els = await driver.find_elements(refresh=True, clickable=True)
        for e in all_els:
            t = (e.get('text', '') or '')
            r = e.get('rect', {})
            if t.isdigit() and r.get('y', 0) > 550 and r.get('x', 0) < 100:
                tap = e.get('tap', {})
                log("   duree actuelle: %ss" % t)
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(1)
                break

        # Ajuster la duree avec le picker
        import re
        for _ in range(20):
            picker = await driver.find_element(text="secondes", contains=True, refresh=True)
            if not picker:
                break
            m = re.search(r'(\d+)', picker.get('text', ''))
            current = int(m.group(1)) if m else 10
            if current == clip_duration:
                log("   duree clip: %ds OK" % clip_duration)
                break
            diff = clip_duration - current
            step = 1 if abs(diff) == 1 else 2
            target_y = 621.5 + (step * 33 * (1 if diff > 0 else -1))
            await driver.ht.tap(187.5, target_y)
            await asyncio.sleep(0.6)

        # Confirmer le picker
        all_done = await driver.find_elements(text="Arr", contains=True, clickable=True, refresh=True)
        if not all_done:
            all_done = await driver.find_elements(text="Termin", contains=True, clickable=True, refresh=True)
        if all_done:
            best = max(all_done, key=lambda d: d.get('rect', {}).get('y', 0))
            tap = best.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1)

    # Terminer
    await _tap_done(driver, log)
    log("   musique ajoutee")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Highlight (mise a la une) — apres publication
# ═══════════════════════════════════════════════════════════════════════════

async def add_to_highlight(driver, highlight_name=None, create_new=False, log=print):
    """Ajoute la story publiee a un contenu a la une.

    Appeler depuis l'ecran de visionnage de la story (post-publication).
    Utilise l'OCR (ocr_screen) pour localiser les highlights existants
    et le bouton "Nouveau" qui ne sont pas dans l'arbre d'accessibilite.

    Flow valide:
      Story ouverte → "Mettre à la une" → bottom sheet →
      (Nouveau ou highlight existant) → nom → "Ajouter" → popup "C'est fait"

    Args:
        highlight_name: nom du highlight a utiliser/creer
        create_new: True pour creer un nouveau highlight
    """
    log("   [highlight] %s%s" % (
        highlight_name or "(premier disponible)",
        " (nouveau)" if create_new else ""))

    # 1. Tap "Mettre à la une" depuis l'ecran story
    el = await driver.find_element(text="Mettre", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(text="la une", contains=True, clickable=True, refresh=True)
    if not el:
        log("   ! bouton highlight non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(1.5)
    await _human_pause(0.3, 0.6)

    # 2. Bottom sheet: "Ajouter au contenu à la une" apparait
    #    Les highlights existants et "Nouveau" ne sont PAS dans l'arbre
    #    d'accessibilite → on utilise l'OCR pour les localiser.

    if highlight_name and not create_new:
        # Chercher un highlight existant par OCR
        ocr = await driver.ht._call("ocr_screen")
        found = False
        if ocr:
            import json
            try:
                content = ocr.get("content", [])
                if content and isinstance(content, list):
                    data = json.loads(content[0].get("text", "{}"))
                    for item in data.get("texts", []):
                        if highlight_name.lower() in item.get("text", "").lower():
                            tx = item["tap"]["x"]
                            ty = item["tap"]["y"]
                            log("   OCR: highlight '%s' trouve a (%d, %d)" % (
                                highlight_name, tx, ty))
                            await driver.ht.tap(tx, ty)
                            found = True
                            break
            except Exception:
                pass

        if not found:
            # Fallback: chercher dans l'arbre d'accessibilite
            existing = await driver.find_element(
                text=highlight_name, clickable=True, refresh=True)
            if existing:
                tap = existing.get('tap', {})
                log("   highlight '%s' trouve dans arbre" % highlight_name)
                await driver.ht.tap(tap['x'], tap['y'])
                found = True

        if not found:
            log("   ! highlight '%s' non trouve, creation..." % highlight_name)
            create_new = True

    if create_new:
        # Le bouton "Nouveau" n'est pas dans l'arbre → OCR
        ocr = await driver.ht._call("ocr_screen")
        nouveau_found = False
        if ocr:
            import json
            try:
                content = ocr.get("content", [])
                if content and isinstance(content, list):
                    data = json.loads(content[0].get("text", "{}"))
                    for item in data.get("texts", []):
                        txt = item.get("text", "").lower()
                        if "nouveau" in txt or "new" in txt:
                            tx = item["tap"]["x"]
                            ty = item["tap"]["y"]
                            log("   OCR: Nouveau a (%d, %d)" % (tx, ty))
                            await driver.ht.tap(tx, ty)
                            nouveau_found = True
                            break
            except Exception:
                pass
        if not nouveau_found:
            # Fallback coords (valide sur iPhone X)
            log("   Nouveau (fallback 65, 744)")
            await driver.ht.tap(65, 744)
        await asyncio.sleep(1.5)
        await _human_pause(0.2, 0.5)

        # 3. Ecran de saisie du nom
        if highlight_name:
            await driver.ht.type_text(highlight_name)
            await asyncio.sleep(0.5)

    await _human_pause(0.3, 0.6)

    # 4. Confirmer: tap "Ajouter" par coordonnees (l'arbre renvoie
    #    "Ajouter à la barre..." au lieu du bouton "Ajouter")
    ajouter = await driver.find_element(text="Ajouter", clickable=True, refresh=True)
    if ajouter:
        tap = ajouter.get('tap', {})
        # Verifier que c'est le bon "Ajouter" (pas "Ajouter à la barre...")
        el_text = ajouter.get("text", "")
        if len(el_text) < 15:
            await driver.ht.tap(tap['x'], tap['y'])
        else:
            # C'est le mauvais → utiliser l'OCR pour trouver le vrai
            ocr = await driver.ht._call("ocr_screen")
            if ocr:
                import json
                try:
                    content = ocr.get("content", [])
                    if content and isinstance(content, list):
                        data = json.loads(content[0].get("text", "{}"))
                        for item in data.get("texts", []):
                            if item.get("text", "").strip().lower() == "ajouter":
                                await driver.ht.tap(
                                    item["tap"]["x"], item["tap"]["y"])
                                break
                except Exception:
                    pass
    else:
        # Fallback: coordonnees validees (188, 342)
        log("   Ajouter (fallback 188, 342)")
        await driver.ht.tap(188, 342)
    await asyncio.sleep(2)

    # 5. Popup de confirmation → "C'est fait"
    await asyncio.sleep(1)
    done = await driver.find_element(
        text="C\u2019est fait", contains=True, clickable=True, refresh=True)
    if not done:
        done = await driver.find_element(
            text="Termin", contains=True, clickable=True, refresh=True)
    if done:
        tap = done.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
    else:
        # Fallback: tap_element natif MCP (cherche arbre + OCR)
        log("   C\u2019est fait (fallback tap_element natif)")
        await driver.ht.tap_by_text("C\u2019est fait", match="contains")
    await asyncio.sleep(1)

    log("   highlight ajoute")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Sticker Texte
# ═══════════════════════════════════════════════════════════════════════════

async def add_text_sticker(driver, text, style=None, log=print):
    """Ajoute du texte sur la story.

    Flow: "Texte, bouton" → Ecrire → (optionnel: choisir style) → "C’est fait".

    Le bouton s'appelle "Texte, bouton" dans l'arbre (pas "Aa").

    Args:
        text: le texte a afficher
        style: style visuel parmi "Modern", "Classic", "Signature" (optionnel)
    """
    log("   [sticker] texte -> '%s'" % text[:30])

    el = await driver.find_element(text="Texte, bouton", contains=True, clickable=True, refresh=True)
    if not el:
        log("   ! bouton Texte non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1)

    # Ecrire le texte
    await driver.type_text(text, method="natural")
    await asyncio.sleep(0.5)

    # Choisir le style si demande
    if style:
        style_el = await driver.find_element(
            text="style du texte : %s", contains=True % style, clickable=True, refresh=True)
        if style_el:
            tap = style_el.get('tap', {})
            log("   style: '%s'" % style)
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.5)
        else:
            log("   ! style '%s' non trouve" % style)

    # Valider
    await _tap_done(driver, log)
    log("   texte ajoute")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Publication story
# ═══════════════════════════════════════════════════════════════════════════

async def publish_story(driver, log=print):
    """Publie la story depuis l'editeur.

    Tap sur "Partager dans votre story" (85, 745).
    """
    log("   [story] publication...")
    el = await driver.find_element(text="Partager dans votre story", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(text="Partager", contains=True, clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        log("   story publiee")
        await asyncio.sleep(3)
        return True
    log("   ! bouton Partager non trouve")
    return False


# ═══════════════════════════════════════════════════════════════════════════
# Ouverture story (profil → menu → Story → choisir media)
# ═══════════════════════════════════════════════════════════════════════════

async def open_story_editor(driver, media_index=0, log=print):
    """Ouvre l'editeur story depuis le profil.

    Flow: Profil → Menu creation (28, 69) → "Story" (188, 526) →
          Choisir media → (popup OK) → editeur story.

    Args:
        media_index: index du media dans la galerie (0 = le plus recent)
    """
    log("   [story] ouverture editeur...")

    # 1. Menu de creation
    menu = await driver.find_element(text="menu de cr", contains=True, clickable=True, refresh=True)
    if not menu:
        menu = await driver.find_element(text="menu de cr", contains=True, clickable=True, refresh=True)
    if menu:
        tap = menu.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
    else:
        # Fallback coords
        log("   menu creation (fallback 28, 69)")
        await driver.ht.tap(28, 69)
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # 2. Tap "Story"
    story_btn = await driver.find_element(text="Story", clickable=True, refresh=True)
    if story_btn:
        tap = story_btn.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
    else:
        log("   Story (fallback 188, 526)")
        await driver.ht.tap(188, 526)
    await driver.wait('transition')
    await asyncio.sleep(2)

    # 3. Choisir le media (meme logique que publish.py/_select_photo)
    photos = []
    for attempt in range(3):
        els = await driver.find_elements(text="Miniature", contains=True, clickable=True, refresh=True)
        # Filtrer : garder les elements dans la grille (y > 220 exclut le header)
        photos = [e for e in els if e.get("tap", {}).get("y", 0) > 350]
        photos.sort(key=lambda e: (e.get('tap', {}).get('y', 0),
                                   e.get('tap', {}).get('x', 0)))
        if photos:
            break
        log("   [retry %d] galerie pas encore chargee" % (attempt + 1))
        await asyncio.sleep(1.5)

    if photos:
        idx = min(media_index, len(photos) - 1)
        tap = photos[idx].get('tap', {})
        log("   media #%d selectionne (y=%d, %d dispo)" % (idx, tap.get('y', 0), len(photos)))
        await driver.ht.tap(tap['x'], tap['y'])
    else:
        log("   ! aucune photo, fallback (62, 378)")
        await driver.ht.tap(62, 378)
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # 4. Popup "stories peuvent toucher plus de monde" → OK
    ok_btn = await driver.find_element(text="OK", clickable=True, refresh=True)
    if ok_btn:
        tap = ok_btn.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1)

    log("   editeur story ouvert")
    return True
