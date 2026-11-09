"""
ig_iphone/interact/apply_template.py — Applique un template story sur l'iPhone.

Lit le JSON du builder, ouvre la story, ajoute chaque sticker,
le positionne/resize/rotate selon le template.

Usage:
    from app.services.automation.ig_iphone.interact.apply_template import apply_template
    apply_template(driver, navigator, template_json, publish=False, log=print)
"""

import sys
import time
import json

sys.path.insert(0, "/root")


# Coordonnees template (1080x1920) -> ecran iPhone (375x812)
# Zone story sur iPhone: ~x=0-375, y=56-700 (environ)
TEMPLATE_W = 1080.0
TEMPLATE_H = 1920.0
SCREEN_W = 375.0
SCREEN_H = 812.0
# Zone utile story (sans status bar ni bottom bar)
STORY_TOP = 56.0
STORY_BOTTOM = 700.0
STORY_H = STORY_BOTTOM - STORY_TOP

SCALE_X = SCREEN_W / TEMPLATE_W
SCALE_Y = STORY_H / TEMPLATE_H


def _t2s(tx, ty):
    """Convertit coordonnees template -> ecran."""
    sx = tx * SCALE_X
    sy = STORY_TOP + ty * SCALE_Y
    return int(sx), int(sy)


async def _get_snapshot(driver):
    """Snapshot des elements pour diff avant/apres."""
    els = await driver.refresh_elements(clickable_only=False)
    return els

def _find_new_element(before, after):
    """Trouve l element ajoute entre 2 snapshots."""
    before_rects = set()
    for e in before:
        r = e.get("rect", {})
        before_rects.add((r.get("x",0), r.get("y",0), r.get("width",0), r.get("height",0)))
    for e in after:
        r = e.get("rect", {})
        key = (r.get("x",0), r.get("y",0), r.get("width",0), r.get("height",0))
        if key not in before_rects and r.get("width",0) > 10 and r.get("height",0) > 10 and r.get("width",0) < 370 and r.get("height",0) < 650:
            cx = r.get("x",0) + r.get("width",0) // 2
            cy = r.get("y",0) + r.get("height",0) // 2
            return {"text": e.get("text",""), "cx": cx, "cy": cy, "rect": r}
    return None

async def _find_sticker(driver, name_contains, log=print):
    """Trouve un sticker par nom ou par taille."""
    els = await driver.refresh_elements(clickable_only=False)
    # Chercher par nom
    for e in els:
        t = (e.get("text") or "")
        if name_contains.lower() in t.lower():
            r = e.get("rect", {})
            cx = r.get("x", 0) + r.get("width", 0) // 2
            cy = r.get("y", 0) + r.get("height", 0) // 2
            return {"text": t, "cx": cx, "cy": cy, "rect": r}
    return None


async def _move_sticker(driver, sticker_name, target_x, target_y, log=print):
    """Deplace un sticker de sa position actuelle vers la cible."""
    s = _find_sticker(driver, sticker_name, log)
    if not s:
        log("   ! sticker '%s' non trouve pour drag" % sticker_name)
        return False
    
    log("   drag '%s' de (%d,%d) -> (%d,%d)" % (sticker_name[:20], s["cx"], s["cy"], target_x, target_y))
    await driver.ht.swipe(s["cx"], s["cy"], target_x, target_y, 600)
    await asyncio.sleep(1)
    return True


async def _resize_sticker(driver, sticker_name, scale, log=print):
    """Resize un sticker via pinch."""
    if abs(scale - 1.0) < 0.05:
        return True  # pas besoin
    
    s = _find_sticker(driver, sticker_name, log)
    if not s:
        log("   ! sticker '%s' non trouve pour pinch" % sticker_name)
        return False
    
    log("   pinch '%s' scale=%.2f @ (%d,%d)" % (sticker_name[:20], scale, s["cx"], s["cy"]))
    await driver.ht._call("pinch_screen", {
        "cx": s["cx"], "cy": s["cy"],
        "scale": scale, "duration": 800
    })
    await asyncio.sleep(1)
    return True


async def _rotate_sticker(driver, sticker_name, angle, log=print):
    """Rotate un sticker."""
    if abs(angle) < 2:
        return True  # pas besoin
    
    s = _find_sticker(driver, sticker_name, log)
    if not s:
        log("   ! sticker '%s' non trouve pour rotate" % sticker_name)
        return False
    
    log("   rotate '%s' angle=%.0f @ (%d,%d)" % (sticker_name[:20], angle, s["cx"], s["cy"]))
    await driver.ht._call("rotate_screen", {
        "cx": s["cx"], "cy": s["cy"],
        "angle": angle, "duration": 800
    })
    await asyncio.sleep(1)
    return True


async def _position_sticker(driver, sticker_name, tx, ty, scale, rotation, log=print):
    """Positionne, resize et rotate un sticker."""
    sx, sy = _t2s(tx, ty)
    
    # 1. Drag vers la position cible
    _move_sticker(driver, sticker_name, sx, sy, log)
    await asyncio.sleep(0.5)
    
    # 2. Resize si necessaire
    if abs(scale - 1.0) >= 0.05:
        _resize_sticker(driver, sticker_name, scale, log)
        await asyncio.sleep(0.5)
    
    # 3. Rotate si necessaire
    if abs(rotation) >= 2:
        _rotate_sticker(driver, sticker_name, rotation, log)
        await asyncio.sleep(0.5)


async def _add_and_position(driver, sticker, log=print):
    """Ajoute un sticker et le positionne selon le template."""
    from app.services.automation.ig_iphone.interact.story_stickers import (
        add_music_sticker, add_location_sticker, add_link_sticker,
        add_poll_sticker, add_question_sticker
    )
    
    stype = sticker["type"]
    tx = sticker.get("x", 540)
    ty = sticker.get("y", 960)
    scale = sticker.get("scale", 1.0)
    rotation = sticker.get("rotation", 0)
    
    log("  [%s] ajout..." % stype)
    
    # Snapshot avant ajout
    _before = _get_snapshot(driver)
    
    # Nom du sticker pour le retrouver apres ajout
    sticker_name = None
    
    if stype == "music":
        # Choisir un son au hasard dans la playlist
        import random
        playlist = sticker.get("playlist", [])
        if playlist:
            song = random.choice(playlist)
            song_title = song.get("title", "")
            song_artist = song.get("artist", "")
        else:
            song_title = sticker.get("song", "")
            song_artist = sticker.get("artist", "")
        
        duration = sticker.get("duration_s", 15)
        style = sticker.get("variant", "uniquement")
        add_music_sticker(driver, song=song_title, artist=song_artist, style=style, duration_s=duration, log=log)
        # Le sticker musique contient le nom du morceau
        sticker_name = song_title[:15] if song_title else "musique"
        await asyncio.sleep(1)
    
    elif stype == "location":
        place = sticker.get("place", "Paris")
        add_location_sticker(driver, place, log=log)
        sticker_name = "Sticker de lieu"
        await asyncio.sleep(1)
    
    elif stype == "link":
        url = sticker.get("url", "")
        text = sticker.get("linkText", "")
        add_link_sticker(driver, url, text=text, log=log)
        sticker_name = "Sticker de lien"
        await asyncio.sleep(1)
    
    elif stype == "poll":
        question = sticker.get("question", "")
        opt1 = sticker.get("opt1", "Oui")
        opt2 = sticker.get("opt2", "Non")
        add_poll_sticker(driver, question, options=[opt1, opt2], log=log)
        sticker_name = "Sticker de sondage"
        await asyncio.sleep(1)
    
    elif stype == "question":
        prompt = sticker.get("prompt", "")
        add_question_sticker(driver, prompt, log=log)
        sticker_name = "Sticker de question"
        await asyncio.sleep(1)
    
    elif stype == "mention":
        username = sticker.get("username", "")
        if username:
            # Tap Aa (texte) -> ecrire @username -> Terminé
            await driver.ht.tap(341, 78)  # bouton Aa
            await asyncio.sleep(1)
            await driver.ht._call("input_text", {"text": "@" + username})
            await asyncio.sleep(0.5)
            # Tap Termine
            el = _find_sticker(driver, "Termin", log)
            if el:
                await driver.ht.tap(el["cx"], el["cy"])
                await asyncio.sleep(1)
            sticker_name = "@" + username
    
    elif stype == "text":
        content = sticker.get("content", "Texte")
        # Tap Aa -> ecrire naturellement -> Termine
        log("   [text] -> '%s'" % content[:30])
        aa = await driver.find_element(contains="Texte, bouton", clickable=True, refresh=True)
        if not aa:
            aa = await driver.find_element(contains="Aa", clickable=True, refresh=True)
        if aa:
            await driver.ht.tap(aa["tap"]["x"], aa["tap"]["y"])
        else:
            await driver.ht.tap(341, 78)
        await asyncio.sleep(1)
        for char in content:
            await driver.ht._call("input_text", {"text": char})
            import random
            await asyncio.sleep(random.uniform(0.03, 0.08))
        await asyncio.sleep(0.5)
        el = await driver.find_element(contains="Termin", clickable=True, refresh=True)
        if el:
            await driver.ht.tap(el["tap"]["x"], el["tap"]["y"])
            await asyncio.sleep(1)
        log("   texte ajoute")
        sticker_name = content[:15]
    
    elif stype == "gif_cta":
        gif_query = sticker.get("gifQuery", "new post")
        log("   [sticker] GIF -> recherche '%s'" % gif_query)
        from app.services.automation.ig_iphone.interact.story_stickers import _open_stickers
        if not _open_stickers(driver, log):
            return
        await asyncio.sleep(1)
        # Chercher la barre de recherche dans les stickers
        search = await driver.find_element(contains="Rechercher", clickable=True, refresh=True)
        if not search:
            search = await driver.find_element(contains="rechercher", clickable=True, refresh=True)
        if search:
            await driver.ht.tap(search["tap"]["x"], search["tap"]["y"])
            await asyncio.sleep(0.5)
            await driver.ht._call("input_text", {"text": gif_query})
            await asyncio.sleep(2)
            # Tap le premier GIF (zone sous la recherche)
            # Les GIFs commencent vers y=200 dans le panneau stickers
            await driver.ht.tap(70, 280)
            await asyncio.sleep(2)
        sticker_name = gif_query[:10]
    
    elif stype in ("media_placeholder", "repost_media"):
        # Pas un sticker a ajouter
        return
    
    else:
        log("   ! type inconnu: %s" % stype)
        return
    
    # Positionner le sticker
    if sticker_name:
        await asyncio.sleep(1)
        sx, sy = _t2s(tx, ty)
        
        # Trouver le sticker: par nom, par diff, ou par OCR
        found = _find_sticker(driver, sticker_name, log)
        if not found:
            _after = _get_snapshot(driver)
            found = _find_new_element(_before, _after)
        
        # Position actuelle du sticker
        if found:
            from_x, from_y = found["cx"], found["cy"]
            log("   trouve: cx=%d cy=%d" % (from_x, from_y))
        else:
            # Fallback: IG place les stickers au centre
            from_x, from_y = int(SCREEN_W/2), 400
            log("   fallback centre: cx=%d cy=%d" % (from_x, from_y))
        
        # 1. Drag vers la position cible
        log("   drag (%d,%d) -> (%d,%d)" % (from_x, from_y, sx, sy))
        await driver.ht.swipe(from_x, from_y, sx, sy, 700)
        await asyncio.sleep(1)
        
        # 2. Auto-resize: mesurer la taille reelle et adapter
        target_w = sticker.get("w", 0)
        target_h = sticker.get("h", 0)
        if target_w > 0 or abs(scale - 1.0) >= 0.05:
            # Mesurer la taille actuelle du sticker sur l'ecran
            await asyncio.sleep(0.5)
            actual_w = 0
            els_after = await driver.refresh_elements(clickable_only=False, max_elements=60)
            for e in els_after:
                r = e.get("rect", {})
                ew = r.get("width", 0)
                eh = r.get("height", 0)
                ex = r.get("x", 0)
                ey = r.get("y", 0)
                # Chercher l'element le plus proche de sx,sy avec une taille > 30
                if ew > 30 and eh > 30 and ew < 350:
                    ecx = ex + ew/2
                    ecy = ey + eh/2
                    dist = abs(ecx - sx) + abs(ecy - sy)
                    if dist < 80:
                        actual_w = ew
                        break
            
            if target_w > 0 and actual_w > 0:
                # Convertir target_w de 1080 space -> screen space
                target_screen_w = target_w * SCREEN_W / TEMPLATE_W
                pinch_scale = target_screen_w / actual_w
                # Appliquer le scale du template en plus
                pinch_scale *= scale
                if abs(pinch_scale - 1.0) >= 0.05:
                    log("   auto-resize: actual=%dpx target=%dpx -> pinch=%.2f" % (actual_w, target_screen_w, pinch_scale))
                    await driver.ht._call("pinch_screen", {"cx": sx, "cy": sy, "scale": pinch_scale, "duration": 800})
                    await asyncio.sleep(1)
            elif abs(scale - 1.0) >= 0.05:
                log("   pinch scale=%.2f @ (%d,%d)" % (scale, sx, sy))
                await driver.ht._call("pinch_screen", {"cx": sx, "cy": sy, "scale": scale, "duration": 800})
                await asyncio.sleep(1)
        
        # 3. Rotate si necessaire
        if abs(rotation) >= 2:
            log("   rotate angle=%.0f @ (%d,%d)" % (rotation, sx, sy))
            await driver.ht._call("rotate_screen", {"cx": sx, "cy": sy, "angle": rotation, "duration": 800})
            await asyncio.sleep(1)


async def apply_template(driver, navigator, template, publish=False, photo_index=0, log=print):
    """Applique un template story complet.
    
    Args:
        driver: IGDriver
        navigator: IGNavigator
        template: dict JSON du template (ou str JSON)
        publish: True pour publier, False pour s'arreter avant
        photo_index: index de la photo dans la galerie
        log: fonction de log
    """
    if isinstance(template, str):
        template = json.loads(template)
    
    from app.services.automation.ig_iphone.interact.publish import _open_create_menu, _select_photo
    
    stickers = template.get("stickers", [])
    context = template.get("context", "free")
    
    log("=== apply_template: %s, %d stickers ===" % (context, len(stickers)))
    
    # 1. Ouvrir creation story
    log("[1] Ouvrir menu creation")
    _open_create_menu(driver, navigator, log)
    await asyncio.sleep(2)
    
    # 2. Tap Story
    log("[2] Tap Story")
    el = await driver.find_element(contains="Story", clickable=True, refresh=True)
    if el:
        await driver.ht.tap(el["tap"]["x"], el["tap"]["y"])
        await asyncio.sleep(2)
    
    # 3. Selectionner photo
    log("[3] Select photo")
    _select_photo(driver, log, index=photo_index)
    await asyncio.sleep(3)
    
    # 4. Ajouter chaque sticker (sauf media_placeholder/repost_media)
    real_stickers = [s for s in stickers if s["type"] not in ("media_placeholder", "repost_media")]
    
    for i, sticker in enumerate(real_stickers):
        log("[4.%d] Sticker: %s" % (i+1, sticker["type"]))
        _add_and_position(driver, sticker, log)
        await asyncio.sleep(1)
    
    # 5. Publier ou s'arreter
    if publish:
        log("[5] Publication...")
        el = await driver.find_element(contains="Partager dans votre story", clickable=True, refresh=True)
        if el:
            await driver.ht.tap(el["tap"]["x"], el["tap"]["y"])
            await asyncio.sleep(3)
            log("=== Story publiee ===")
        else:
            log("   ! bouton Partager non trouve")
    else:
        log("=== STOP - publish=False, story prete ===")
    
    return True


if __name__ == "__main__":
    # Test avec un template simple
    test_template = {
        "context": "free",
        "stickers": [
            {"type": "location", "place": "Paris", "x": 540, "y": 400, "scale": 1.0, "rotation": 0},
        ]
    }
    
    from ig_iphone import IGDriver
    from app.services.automation.ig_iphone.navigator import IGNavigator
    
    drv = IGDriver(log=print)
    nav = IGNavigator(drv, log=print)
    apply_template(drv, nav, test_template, publish=False, log=print)


async def repost_to_story(driver, log=print):
    """Partage un post/reel en story. Le post doit etre affiche a l ecran."""
    import asyncio

    log("[REPOST] partage en story...")
    
    # 1. Tap sur le bouton Envoyer (avion) - prendre celui du bas, scroller si besoin
    els = await driver.refresh_elements(clickable_only=True, max_elements=60)
    send_btns = [e for e in els if "Envoyer" in (e.get("text") or "") and e.get("tap",{}).get("y",0) > 400]
    if not send_btns:
        send_btns = [e for e in els if "partage" in (e.get("text") or "").lower() and e.get("tap",{}).get("y",0) > 400]
    if not send_btns:
        log("   ! bouton Envoyer non trouve")
        return False
    el = send_btns[0]
    tap_y = el["tap"]["y"]
    if tap_y > 720:
        log("   scroll up (y=%d)" % tap_y)
        await driver.ht.swipe(187, 500, 187, 300, 400)
        await asyncio.sleep(1.5)
        els = await driver.refresh_elements(clickable_only=True, max_elements=60)
        send_btns = [e for e in els if "Envoyer" in (e.get("text") or "") and e.get("tap",{}).get("y",0) > 200 and e.get("tap",{}).get("y",0) < 760]
        if not send_btns:
            log("   ! bouton Envoyer non trouve apres scroll")
            return False
        el = send_btns[0]
    await driver.ht.tap(el["tap"]["x"], el["tap"]["y"])
    log("   tap Envoyer @ y=%d" % el["tap"]["y"])
    await asyncio.sleep(2)
    
    # 2. Tap sur "Ajouter a la story"
    el = await driver.find_element(contains="Ajouter", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="story", clickable=True, refresh=True)
    if el:
        await driver.ht.tap(el["tap"]["x"], el["tap"]["y"])
        log("   tap Ajouter a la story")
    else:
        log("   ! bouton Ajouter a la story non trouve")
        return False
    await asyncio.sleep(2)
    
    # 2b. Dismiss popups (partage de story, etc.)
    from ig_iphone import IGNavigator
    try:
        nav = IGNavigator(driver, log=log)
        nav._dismiss_popups()
        await asyncio.sleep(1)
        nav._dismiss_popups()
        await asyncio.sleep(1)
    except:
        pass
    
    # 3. Verifier qu on est dans l editeur story
    el = await driver.find_element(contains="Partager dans votre story", clickable=True, refresh=True)
    if el:
        log("[REPOST] editeur story ouvert")
        return True
    
    el = await driver.find_element(contains="Texte", clickable=True, refresh=True)
    if el:
        log("[REPOST] editeur story ouvert")
        return True
    
    log("[REPOST] ! editeur story non detecte")
    return False


async def repost_and_publish(driver, navigator=None, log=print):
    """Partage un post en story et publie. Le post doit etre visible."""
    import asyncio
    ok = await repost_to_story(driver, log=log)
    if not ok:
        return False
    
    await asyncio.sleep(2)
    el = await driver.find_element(contains="Partager dans votre story", clickable=True, refresh=True)
    if el:
        await driver.ht.tap(el["tap"]["x"], el["tap"]["y"])
        log("[REPOST] story publiee!")
        await asyncio.sleep(5)
        return True
    
    log("[REPOST] bouton Partager non trouve")
    return False
