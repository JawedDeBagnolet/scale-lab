"""
ig_iphone/interact/story_stickers.py — Stickers avances pour stories IG.

Chaque fonction suppose qu'on est sur l'editeur story (apres selection photo).

Usage:
    from app.services.automation.ig_iphone.interact.story_stickers import add_link_sticker, add_poll_sticker
    add_link_sticker(driver, "https://youtube.com", text="Mon YouTube")
"""

import asyncio
import time
import random


async def _open_stickers(driver, log):
    """Ouvre le panneau de stickers."""
    el = await driver.find_element(contains="Stickers, bouton", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="Stickers", clickable=True, refresh=True)
    if not el:
        log("   ! bouton Stickers non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)
    return True


async def _tap_done(driver, log):
    """Tape sur Termine."""
    el = await driver.find_element(text="Terminé", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="Termin", clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        log("   -> Termine")
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(1)
        return True
    return False


# ── Sticker Lien ──────────────────────────────────────────────────────────────

async def add_link_sticker(driver, url, text=None, log=print):
    """Ajoute un sticker lien a la story.

    Args:
        url: l'URL du lien
        text: texte personnalise du sticker (optionnel, sinon affiche l'URL)
    """
    log("   [sticker] lien -> %s" % url[:40])
    if not _open_stickers(driver, log):
        return False

    # Trouver "Sticker à lien" dans la liste des stickers
    el = await driver.find_element(contains="lien", clickable=True, refresh=True)
    if not el:
        log("   ! sticker lien non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Taper l'URL
    url_field = await driver.find_element(text="URL", clickable=True, refresh=True)
    if url_field:
        tap = url_field.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('tap')
        await asyncio.sleep(0.3)
        # Effacer l'URL par defaut si presente
        clear = await driver.find_element(contains="Effacer", clickable=True, refresh=True)
        if clear:
            tap = clear.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.3)
        await driver.type_text(url, method="fast")
        await asyncio.sleep(0.5)

    # Personnaliser le texte si demande
    if text:
        text_field = await driver.find_element(contains="Personnaliser le texte", clickable=True, refresh=True)
        if not text_field:
            text_field = await driver.find_element(contains="Texte du sticker", clickable=True, refresh=True)
        if text_field:
            tap = text_field.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
            await asyncio.sleep(0.5)
            await driver.type_text(text, method="natural")
            await asyncio.sleep(0.5)

    _tap_done(driver, log)
    log("   sticker lien ajoute")
    return True


# ── Sticker Sondage ───────────────────────────────────────────────────────────

async def add_poll_sticker(driver, question, options=None, log=print):
    """Ajoute un sticker sondage a la story.

    Args:
        question: la question du sondage
        options: liste des options (defaut ["Oui", "Non"])
    """
    if options is None:
        options = ["Oui", "Non"]
    log("   [sticker] sondage -> '%s'" % question[:30])
    if not _open_stickers(driver, log):
        return False

    el = await driver.find_element(contains="sondage", clickable=True, refresh=True)
    if not el:
        log("   ! sticker sondage non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Taper la question (champ "POSEZ UNE QUESTION…")
    q_field = await driver.find_element(contains="POSEZ UNE QUESTION", clickable=True, refresh=True)
    if q_field:
        tap = q_field.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('tap')
        await asyncio.sleep(0.3)
        await driver.type_text(question, method="natural")
        await asyncio.sleep(0.5)

    # Modifier les options (Oui/Non par defaut)
    # Tap sur "Oui" pour le modifier
    if len(options) >= 1:
        opt1 = await driver.find_element(text="Oui", clickable=True, refresh=True)
        if opt1:
            tap = opt1.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
            await asyncio.sleep(0.2)
            # Effacer et taper la nouvelle option
            clear = await driver.find_element(contains="Effacer", clickable=True, refresh=True)
            if clear:
                tap = clear.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.2)
            else:
                # Triple backspace pour "Oui"
                for _ in range(5):
                    await driver.ht._call("press_key", {"key": "backspace"})
            await driver.type_text(options[0], method="natural")
            await asyncio.sleep(0.3)

    if len(options) >= 2:
        opt2 = await driver.find_element(text="Non", clickable=True, refresh=True)
        if opt2:
            tap = opt2.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
            await asyncio.sleep(0.2)
            clear = await driver.find_element(contains="Effacer", clickable=True, refresh=True)
            if clear:
                tap = clear.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.2)
            else:
                for _ in range(5):
                    await driver.ht._call("press_key", {"key": "backspace"})
            await driver.type_text(options[1], method="natural")
            await asyncio.sleep(0.3)

    # Ajouter des options supplementaires
    for i in range(2, len(options)):
        add_opt = await driver.find_element(contains="Ajoutez une option", clickable=True, refresh=True)
        if add_opt:
            tap = add_opt.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
            await asyncio.sleep(0.3)
            await driver.type_text(options[i], method="natural")
            await asyncio.sleep(0.3)

    _tap_done(driver, log)
    log("   sticker sondage ajoute")
    return True


# ── Sticker Question ──────────────────────────────────────────────────────────

async def add_question_sticker(driver, question=None, log=print):
    """Ajoute un sticker question (boite a questions) a la story.

    Args:
        question: texte de la question (optionnel, garde le defaut "Posez-moi une question")
    """
    log("   [sticker] question%s" % (" -> '%s'" % question[:30] if question else ""))
    if not _open_stickers(driver, log):
        return False

    el = await driver.find_element(contains="Sticker de question", clickable=True, refresh=True)
    if not el:
        log("   ! sticker question non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Modifier la question si demande
    if question:
        q_field = await driver.find_element(contains="POSEZ UNE QUESTION", clickable=True, refresh=True)
        if not q_field:
            q_field = await driver.find_element(contains="question", clickable=True, refresh=True)
        if q_field:
            tap = q_field.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
            await asyncio.sleep(0.3)
            # Effacer le texte par defaut
            clear = await driver.find_element(contains="Effacer", clickable=True, refresh=True)
            if clear:
                tap = clear.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.2)
            else:
                for _ in range(30):
                    await driver.ht._call("press_key", {"key": "backspace"})
            await driver.type_text(question, method="natural")
            await asyncio.sleep(0.5)

    _tap_done(driver, log)
    log("   sticker question ajoute")
    return True


# ── Sticker Lieu ──────────────────────────────────────────────────────────────

async def add_location_sticker(driver, location, log=print):
    """Ajoute un sticker de lieu a la story.

    Args:
        location: nom du lieu a rechercher (ex: "Paris", "Tour Eiffel")
    """
    log("   [sticker] lieu -> '%s'" % location)
    if not _open_stickers(driver, log):
        return False

    el = await driver.find_element(contains="Sticker de lieu", clickable=True, refresh=True)
    if not el:
        log("   ! sticker lieu non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # Popup localisation (premiere fois)
    ok = await driver.find_element(text="OK", clickable=True, refresh=True)
    if ok:
        r = ok.get('rect', {})
        if r.get('width', 0) >= 200:
            tap = ok.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('transition')
            await asyncio.sleep(1)

    # Rechercher le lieu
    search = await driver.find_element(contains="Rechercher des lieux", clickable=True, refresh=True)
    if search:
        tap = search.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('tap')
        await asyncio.sleep(0.5)
        await driver.type_text(location, method="fast")
        await asyncio.sleep(2)  # attendre les resultats

    # Selectionner le premier resultat
    results = await driver.find_elements(contains="Nom du lieu", clickable=True, refresh=True)
    if results:
        tap = results[0].get('tap', {})
        log("   selectionne '%s'" % results[0].get('text', '')[:40])
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(1.5)

        # Apercu carte -> "Ajouter"
        add_btn = await driver.find_element(contains="Ajouter un lieu", clickable=True, refresh=True)
        if add_btn:
            r = add_btn.get('rect', {})
            if r.get('width', 0) >= 200:
                tap = add_btn.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('transition')
                await asyncio.sleep(1)

    log("   sticker lieu ajoute")
    return True


# ── Sticker Musique (Audio) ───────────────────────────────────────────────────

async def _parse_duration_s(text):
    """Parse '2:56' ou '2,4 M reels · 2:56' -> 176 secondes."""
    import re
    m = re.search(r'(\d+):(\d+)', text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


async def add_music_sticker(driver, song=None, artist=None, duration_s=None,
                      style=None, clip_duration=None, scrub_position=None,
                      log=print):
    """Ajoute de la musique a la story via le bouton Audio.

    Args:
        song: titre du morceau a rechercher
        artist: nom de l'artiste pour verifier (optionnel)
        duration_s: duree attendue en secondes, tolerance +-5s (optionnel)
        style: style visuel ("uniquement de la musique", "affichage dynamique",
               "machine à écrire", "affichage cube", "karaoké", "simple")
        clip_duration: duree du clip en secondes (ex: 5, 10, 15, 20)
        scrub_position: position dans le morceau, 0.0 (debut) a 1.0 (fin)
    """
    log("   [sticker] musique%s" % (" -> '%s'" % song[:30] if song else ""))

    # Ouvrir le selecteur audio
    el = await driver.find_element(contains="Audio, bouton", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="Audio", clickable=True, refresh=True)
    if not el:
        log("   ! bouton Audio non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(2)

    # Rechercher le morceau
    if song:
        search = await driver.find_element(contains="Recherche", clickable=True, refresh=True)
        if search:
            tap = search.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
            await asyncio.sleep(0.5)
            await driver.type_text(song, method="fast")
            await asyncio.sleep(2)

    # Trouver le bon morceau : titre + artiste + duree
    _skip = ("Enregistrer", "Annuler", "Fermer", "Recherche", "Pour vous",
             "Populaire", "Audio", "Effacer", "Commande", "Emoji", "Dicter",
             "Enregistr")
    els = await driver.find_elements(refresh=True, clickable=True)

    # Construire la liste des morceaux (titre + artiste en dessous)
    songs = []
    for i, e in enumerate(els):
        t = (e.get('text', '') or '')
        r = e.get('rect', {})
        # Titre : width > 150, y > 180, height < 25, pas un bouton connu
        if (r.get('width', 0) > 150 and r.get('y', 0) > 180
                and r.get('height', 0) < 25
                and not any(s in t for s in _skip)
                and t and 'reels' not in t.lower()):
            # Chercher la ligne artiste juste en dessous (contient "reels")
            artist_line = ""
            for j in range(i + 1, min(i + 3, len(els))):
                tj = (els[j].get('text', '') or '')
                if 'reels' in tj.lower():
                    artist_line = tj
                    break
            songs.append({"title": t, "artist_line": artist_line, "element": e})

    # Matcher le bon morceau
    selected = None
    for s in songs:
        # Verifier artiste si demande
        if artist:
            if artist.lower() not in s["artist_line"].lower():
                continue
        # Verifier duree si demandee (tolerance +-5s)
        if duration_s:
            d = _parse_duration_s(s["artist_line"])
            if d and abs(d - duration_s) > 5:
                continue
        selected = s
        break

    if not selected and songs:
        selected = songs[0]  # fallback : premier resultat
        log("   ! match exact non trouve, prend le premier")

    if not selected:
        log("   ! aucun morceau trouve")
        return False

    # Taper le titre
    tap = selected["element"].get('tap', {})
    log("   selectionne '%s' | %s" % (selected["title"][:30], selected["artist_line"][:30]))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(2)

    # Confirmer la selection du son
    # Chercher le bouton de confirmation (fleche ou Termine)
    for attempt in range(5):
        els = await driver.refresh_elements(clickable_only=True)
        
        # Deja sur l'ecran customisation?
        on_custom = any("uniquement" in (e.get("text","") or "").lower() or 
                       "machine" in (e.get("text","") or "").lower() or
                       "karaoké" in (e.get("text","") or "").lower()
                       for e in els)
        if on_custom:
            log("   ecran customisation OK")
            break
        
        # Chercher Termine en haut a droite
        done = None
        for e in els:
            t = (e.get("text","") or "")
            r = e.get("rect", {})
            if "Termin" in t and r.get("x", 0) > 250:
                done = e
                break
        if done:
            log("   ecran customisation OK (Termine visible)")
            break
        
        # Chercher le bouton fleche/suivant en bas a droite
        best_btn = None
        for e in els:
            r = e.get("rect", {})
            t = (e.get("text","") or "")
            # Bouton en bas a droite (x > 300, y > 600)
            if r.get("x", 0) > 300 and r.get("y", 0) > 600 and r.get("width", 0) < 60:
                if "Bouton" in t or not t:
                    best_btn = e
        
        if best_btn:
            tap = best_btn.get("tap", {})
            log("   tap confirmation (%d, %d)" % (tap.get("x",0), tap.get("y",0)))
            await driver.ht.tap(tap["x"], tap["y"])
        else:
            # Fallback coordonnees
            await driver.ht._ensure_screen()
            arrow_x = driver.ht.screen_w - 35
            arrow_y = driver.ht.screen_h * 0.91
            log("   tap fleche fallback (%d, %d)" % (arrow_x, arrow_y))
            await driver.ht.tap(arrow_x, arrow_y)
        
        await asyncio.sleep(2)

    # Choisir le style visuel
    STYLE_ORDER = ["uniquement", "dynamique", "machine", "cube", "karaoke", "simple", "illustration", "vinyle"]
    if style:
        target = style.lower()
        if target == "karaoké": target = "karaoke"
        found = False
        for attempt in range(6):
            # Scanner les styles visibles
            els = await driver.refresh_elements(clickable_only=True)
            visible = []
            for e in els:
                t = (e.get("text") or "").lower()
                r = e.get("rect", {})
                x = r.get("x", 0)
                for i, sn in enumerate(STYLE_ORDER):
                    if sn in t or (sn == "karaoke" and "karaoké" in t):
                        visible.append({"idx": i, "name": sn, "el": e, "x": x})
            
            # Chercher le target dans les visibles
            target_el = None
            for v in visible:
                if target in v["name"] or v["name"] in target:
                    if v["x"] >= 0 and v["x"] < 375:  # visible a l ecran
                        target_el = v
                        break
            
            if target_el:
                tap = target_el["el"].get("tap", {})
                log("   style: %s @ (%d,%d)" % (target_el["name"], tap["x"], tap["y"]))
                await driver.ht.tap(tap["x"], tap["y"])
                await asyncio.sleep(1)
                found = True
                break
            
            # Pas visible - naviguer
            target_idx = next((i for i, sn in enumerate(STYLE_ORDER) if target in sn), -1)
            if visible and target_idx >= 0:
                avg_idx = sum(v["idx"] for v in visible) / len(visible)
                if target_idx > avg_idx:
                    rightmost = max(visible, key=lambda v: v["x"])
                    tap = rightmost["el"].get("tap", {})
                    log("   nav -> droite (%s)" % rightmost["name"])
                    await driver.ht.tap(tap["x"], tap["y"])
                else:
                    leftmost = min(visible, key=lambda v: v["x"])
                    tap = leftmost["el"].get("tap", {})
                    log("   nav -> gauche (%s)" % leftmost["name"])
                    await driver.ht.tap(tap["x"], tap["y"])
            else:
                await driver.ht.tap(350, 540)
            await asyncio.sleep(1)
        if not found:
            log("   ! style '%s' non trouve" % target)

    # Modifier la duree du clip (picker wheel)
    if clip_duration:
        # Taper sur le nombre actuel pour ouvrir le picker
        all_els = await driver.find_elements(refresh=True, clickable=True)
        for e in all_els:
            t = (e.get('text', '') or '')
            r = e.get('rect', {})
            if t.isdigit() and r.get('width', 0) < 50 and r.get('y', 0) > 550:
                tap = e.get('tap', {})
                log("   ouvre picker duree (actuel: %ss)" % t)
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('transition')
                await asyncio.sleep(1)
                break

        # Lire la valeur et tapper au centre du picker pour changer
        import re
        for attempt in range(20):
            picker = await driver.find_element(contains="secondes", refresh=True)
            if not picker:
                log("   ! picker non trouve")
                break
            m = re.search(r'(\d+)', picker.get('text', ''))
            current = int(m.group(1)) if m else 10
            if current == clip_duration:
                log("   duree clip: %ds OK" % clip_duration)
                break
            diff = clip_duration - current
            # Tap au CENTRE du picker (x=187.5) ± 33px par cran
            step = 1 if abs(diff) == 1 else 2
            target_y = 621.5 + (step * 33 * (1 if diff > 0 else -1))
            log("   picker: %ds -> %ds (tap y=%d)" % (current, clip_duration, target_y))
            await driver.ht.tap(187.5, target_y)
            await asyncio.sleep(0.6)

        # Tap "Termine" du picker (le plus BAS, y=755)
        all_done = await driver.find_elements(contains="Termin", clickable=True, refresh=True)
        best = None
        for d in all_done:
            dy = d.get('rect', {}).get('y', 0)
            if not best or dy > best.get('rect', {}).get('y', 0):
                best = d
        if best:
            tap = best.get('tap', {})
            log("   confirme duree picker")
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('transition')
            await asyncio.sleep(1)

    # Deplacer le scrubber (position dans le morceau)
    if scrub_position is not None:
        scrub = await driver.find_element(contains="temps fort audio", clickable=True, refresh=True)
        if scrub:
            r = scrub.get('rect', {})
            # La waveform fait toute la largeur, on drag vers la position
            start_x = r.get('x', 0) + 10
            end_x = r.get('x', 0) + r.get('width', 375) - 10
            target_x = start_x + (end_x - start_x) * scrub_position
            y = r.get('y', 626) + r.get('height', 52) / 2
            # Drag depuis le centre vers la position cible
            center_x = (start_x + end_x) / 2
            log("   scrub: %.0f%% (x=%d)" % (scrub_position * 100, target_x))
            await driver.ht.swipe(center_x, y, target_x, y, 500)
            await asyncio.sleep(0.5)

    # Terminer
    _tap_done(driver, log)
    log("   musique ajoutee")
    return True


# ── Highlight (mise a la une) ─────────────────────────────────────────────────

async def add_to_highlight(driver, highlight_name=None, log=print):
    """Ajoute la story a un contenu a la une (apres publication).
    
    Si highlight_name est fourni, cree ou utilise un highlight existant.
    Sinon, utilise le premier disponible.
    """
    log("   [highlight] %s" % (highlight_name or "(premier disponible)"))

    # Tap "Mettre à la une" ou "Ajouter au contenu à la une"
    el = await driver.find_element(contains="la une", clickable=True, refresh=True)
    if not el:
        log("   ! bouton highlight non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    if highlight_name:
        # Chercher le highlight existant ou le champ pour creer
        existing = await driver.find_element(text=highlight_name, clickable=True, refresh=True)
        if existing:
            tap = existing.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await driver.wait('tap')
        else:
            # Creer un nouveau : taper le nom
            name_field = await driver.find_element(contains="la une", clickable=True, refresh=True)
            if name_field:
                tap = name_field.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await driver.wait('tap')
                await driver.type_text(highlight_name, method="natural")
                await asyncio.sleep(0.5)

    # Tap "Ajouter" ou "Terminé"
    add_btn = await driver.find_element(contains="Ajouter un lieu", clickable=True, refresh=True)
    if not add_btn:
        add_btn = await driver.find_element(text="Suivant", clickable=True, refresh=True)
    if not add_btn:
        add_btn = await driver.find_element(contains="Termin", clickable=True, refresh=True)
    if add_btn:
        tap = add_btn.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(2)

    log("   highlight ajoute")
    return True


# ── Sticker de mise a la une (dans l'editeur, redirige vers un highlight) ─────

async def add_highlight_sticker(driver, highlight_name=None, log=print):
    """Ajoute un sticker qui redirige vers une story a la une.
    
    Flow : Stickers → "Ajouter au sticker à la une" → tap barre highlights
    → ecran detail → choisir type sticker → Terminé
    """
    log("   [sticker] a la une%s" % (" -> '%s'" % highlight_name if highlight_name else ""))
    if not _open_stickers(driver, log):
        return False

    # "Ajouter au sticker à la une"
    el = await driver.find_element(contains="sticker à la une", clickable=True, refresh=True)
    if not el:
        await driver.scroll_down('light')
        await asyncio.sleep(1)
        el = await driver.find_element(contains="sticker à la une", clickable=True, refresh=True)
    if not el:
        log("   ! sticker a la une non trouve")
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    # Tap sur la barre des highlights (grand bloc 375x190)
    bar = await driver.find_element(contains="Ajouter à la barre", clickable=True, refresh=True)
    if bar:
        tap = bar.get('tap', {})
        log("   tap barre highlights")
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('transition')
        await asyncio.sleep(1.5)

    # On est maintenant sur "Ajouter à <name>"
    # Choisir "Sticker de mise à la une" (pas juste l'etiquette)
    sticker_opt = await driver.find_element(contains="Sticker de mise", clickable=True, refresh=True)
    if sticker_opt:
        tap = sticker_opt.get('tap', {})
        log("   type: sticker de mise a la une")
        await driver.ht.tap(tap['x'], tap['y'])
        await driver.wait('tap')
        await asyncio.sleep(0.5)

    _tap_done(driver, log)
    log("   sticker a la une ajoute")
    return True
