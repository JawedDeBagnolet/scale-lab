"""
th_iphone/interact/profile_config.py — Configuration profil Threads (async).

Flow: toute modification passe par l'ecran "Modifier le profil".
IMPORTANT: il faut taper "Terminé" a la fin pour sauvegarder TOUTES les modifs.

Usage:
    from ..interact.profile_config import full_profile_setup
"""

import asyncio
import random
import time


async def _go_to_edit_profile(driver, navigator, log):
    """Navigate vers l'ecran Modifier le profil."""
    if not await driver.ensure_screen("profile"):
        await navigator.go_profile()
        await asyncio.sleep(2)

    if not await driver.tap_element(contains="Modifier le profil", refresh=True):
        log("   ! bouton Modifier le profil non trouve")
        return False

    await driver.wait('transition')
    await asyncio.sleep(2)
    return True


async def _save_edit_profile(driver, log):
    """Tap Terminé sur l'ecran principal d'edition pour sauvegarder."""
    els = await driver.get_elements(refresh=True)
    for e in els:
        if "terminé" in e.get("text", "").lower() and e.get("tap", {}).get("y", 999) < 100:
            await driver.ht.tap(e["tap"]["x"], e["tap"]["y"])
            log("   -> Terminé (sauvegarde)")
            await driver.wait('transition')
            await asyncio.sleep(2)
            return True
    log("   ! bouton Terminé non trouve")
    return False


async def _save_sub_screen(driver, log):
    """Tap Terminé dans un sous-ecran (bio, liens, etc.)."""
    els = await driver.get_elements(refresh=True)
    for e in els:
        if "terminé" in e.get("text", "").lower() and e.get("tap", {}).get("y", 999) < 100:
            await driver.ht.tap(e["tap"]["x"], e["tap"]["y"])
            log("   -> Terminé (sous-ecran)")
            await driver.wait('transition')
            await asyncio.sleep(1.5)
            return True
    return False


async def edit_name(driver, navigator, name, log=print):
    """Modifie le nom affiche."""
    log("-> Modification nom: %s" % name)

    name_el = await driver.find_element(contains="Nom", clickable=True, refresh=True)
    if name_el and name_el.get("tap") and name_el["tap"].get("y", 0) < 200:
        x, y = name_el["tap"]["x"], name_el["tap"]["y"]
        await driver.ht.tap(x, y)
        await driver.wait('tap')
        await asyncio.sleep(0.5)
        await driver.ht._call("long_press", {"x": x, "y": y, "duration": 800})
        await asyncio.sleep(1)
        if not await driver.tap_element(contains="Tout sélectionner", refresh=True):
            await driver.tap_element(contains="Sélectionner tout", refresh=True)
        await asyncio.sleep(0.3)
    else:
        log("   ! champ nom non trouve")
        return False

    await driver.type_text(name, method="slow")
    await asyncio.sleep(0.8)
    await _save_sub_screen(driver, log)
    log("   nom modifie: %s" % name)
    return True


async def edit_bio(driver, navigator, bio_text, log=print):
    """Modifie la bio."""
    log("-> Modification bio")

    if not await driver.tap_element(contains="Bio", refresh=True):
        log("   ! champ bio non trouve")
        return False

    await driver.wait('transition')
    await asyncio.sleep(1.5)

    effacer = await driver.find_element(contains="Effacer", clickable=True, refresh=True)
    if effacer and effacer.get("tap"):
        await driver.ht.tap(effacer["tap"]["x"], effacer["tap"]["y"])
        await driver.wait('tap')
        await asyncio.sleep(0.5)
    else:
        bio_field = await driver.find_element(contains="Bio", clickable=True, refresh=True)
        if bio_field and bio_field.get("tap"):
            x, y = bio_field["tap"]["x"], bio_field["tap"]["y"]
            await driver.ht.tap(x, y)
            await driver.wait('tap')
            await asyncio.sleep(0.5)
            await driver.ht._call("long_press", {"x": x, "y": y, "duration": 800})
            await asyncio.sleep(1)
            if not await driver.tap_element(contains="Tout sélectionner", refresh=True):
                await driver.tap_element(contains="Sélectionner tout", refresh=True)
            await asyncio.sleep(0.3)
        await driver.ht._call("press_key", {"key": "delete"})
        await asyncio.sleep(0.5)

    log("   ecriture bio (%d chars)" % len(bio_text))
    await driver.type_text(bio_text, method="slow")
    await asyncio.sleep(0.8)
    await _save_sub_screen(driver, log)
    log("   bio modifiee")
    return True


async def edit_photo(driver, navigator, photo_index=0, log=print):
    """Change la photo de profil."""
    log("-> Changement photo de profil")

    if not await driver.tap_element(contains="Photo de profil", refresh=True):
        log("   ! photo de profil non trouvee")
        return False

    await driver.wait('transition')
    await asyncio.sleep(1.5)

    if not await driver.tap_element(contains="Choisir dans la bibliothèque", refresh=True):
        log("   ! option bibliotheque non trouvee")
        await driver.tap_element(contains="Annuler")
        return False

    await driver.wait('transition')
    await asyncio.sleep(2)

    photos = await driver.find_elements(contains="Photo", clickable=True, refresh=True)
    photos = [p for p in photos if p.get("tap", {}).get("y", 0) > 150]

    if not photos:
        log("   ! aucune photo dans la galerie")
        await driver.tap_element(contains="Annuler")
        return False

    idx = min(photo_index, len(photos) - 1)
    await driver.ht.tap(photos[idx]["tap"]["x"], photos[idx]["tap"]["y"])
    log("   photo #%d selectionnee" % idx)
    await driver.wait('transition')
    await asyncio.sleep(2)

    if not await driver.tap_element(contains="Choisir", refresh=True):
        log("   ! bouton Choisir non trouve")
        await driver.tap_element(contains="Annuler")
        return False

    await driver.wait('transition')
    await asyncio.sleep(2)

    log("   photo de profil changee")
    return True


async def add_link(driver, navigator, url, title="", log=print):
    """Ajoute un lien au profil."""
    log("-> Ajout lien: %s" % url)

    if not await driver.tap_element(contains="Liens", refresh=True):
        log("   ! champ liens non trouve")
        return False

    await driver.wait('transition')
    await asyncio.sleep(1.5)

    if not await driver.tap_element(contains="Ajouter un lien", refresh=True):
        log("   ! bouton ajouter lien non trouve")
        await _save_sub_screen(driver, log)
        return False

    await driver.wait('transition')
    await asyncio.sleep(1.5)

    url_field = await driver.find_element(contains="URL", clickable=True, refresh=True)
    if url_field and url_field.get("tap"):
        await driver.ht.tap(url_field["tap"]["x"], url_field["tap"]["y"])
        await driver.wait('tap')
        await asyncio.sleep(0.5)
        await driver.type_text(url, method="normal")
        await asyncio.sleep(0.8)

    if title:
        title_field = await driver.find_element(contains="Titre", clickable=True, refresh=True)
        if title_field and title_field.get("tap"):
            await driver.ht.tap(title_field["tap"]["x"], title_field["tap"]["y"])
            await driver.wait('tap')
            await asyncio.sleep(0.5)
            await driver.type_text(title, method="slow")
            await asyncio.sleep(0.5)

    await _save_sub_screen(driver, log)
    await asyncio.sleep(1)
    await _save_sub_screen(driver, log)

    log("   lien ajoute")
    return True


async def set_privacy(driver, navigator, private=True, log=print):
    """Change la confidentialite du profil."""
    log("-> Confidentialite: %s" % ("prive" if private else "public"))

    priv_el = await driver.find_element(contains="Public", clickable=True, refresh=True)
    if not priv_el:
        priv_el = await driver.find_element(contains="Privé", clickable=True, refresh=True)

    if not priv_el:
        log("   ! toggle confidentialite non trouve")
        return False

    current = priv_el.get("text", "").lower()
    is_private = "privé" in current

    if private == is_private:
        log("   deja en mode %s" % ("prive" if private else "public"))
        return True

    await driver.ht.tap(priv_el["tap"]["x"], priv_el["tap"]["y"])
    await driver.wait('transition')
    await asyncio.sleep(1.5)

    coche = await driver.find_element(contains="Profil privé", clickable=True, refresh=True)
    if coche and coche.get("tap"):
        await driver.ht.tap(coche["tap"]["x"], coche["tap"]["y"])
        await driver.wait('transition')
        await asyncio.sleep(1)

    if private:
        await driver.tap_element(contains="OK", refresh=True)
        await driver.wait('transition')
        await asyncio.sleep(1)

    await driver.tap_element(contains="Retour", refresh=True)
    await driver.wait('transition')
    await asyncio.sleep(1)

    log("   confidentialite changee: %s" % ("prive" if private else "public"))
    return True


async def toggle_badge_instagram(driver, log=print):
    """Toggle l'affichage du badge Instagram."""
    if await driver.tap_element(contains="Afficher le badge Instagram", refresh=True):
        log("   badge Instagram toggle")
        await driver.wait('tap')
        return True
    return False


async def toggle_vues_recentes(driver, log=print):
    """Toggle l'affichage des vues recentes."""
    if await driver.tap_element(contains="Afficher les vues récentes", refresh=True):
        log("   vues recentes toggle")
        await driver.wait('tap')
        return True
    return False


async def full_profile_setup(driver, navigator, name=None, bio=None, photo_index=None,
                              link_url=None, link_title="", private=None,
                              show_badge=None, show_views=None, interests=None, log=print):
    """Configure le profil complet en une fois."""
    start = time.time()
    results = {"success": False, "actions_done": [], "duration_s": 0}

    log("-> Setup profil complet")

    if not await _go_to_edit_profile(driver, navigator, log):
        results["duration_s"] = round(time.time() - start)
        return results

    if name:
        if await edit_name(driver, navigator, name, log=log):
            results["actions_done"].append("name")
        await asyncio.sleep(0.5)

    if bio:
        if await edit_bio(driver, navigator, bio, log=log):
            results["actions_done"].append("bio")
        await asyncio.sleep(0.5)

    if photo_index is not None:
        if await edit_photo(driver, navigator, photo_index, log=log):
            results["actions_done"].append("photo")
        await asyncio.sleep(0.5)

    if link_url:
        if await add_link(driver, navigator, link_url, link_title, log=log):
            results["actions_done"].append("link")
        await asyncio.sleep(0.5)

    if show_badge is not None:
        await toggle_badge_instagram(driver, log=log)
        results["actions_done"].append("badge")
        await asyncio.sleep(0.5)

    if show_views is not None:
        await toggle_vues_recentes(driver, log=log)
        results["actions_done"].append("views")
        await asyncio.sleep(0.5)

    if private is not None:
        if await set_privacy(driver, navigator, private=private, log=log):
            results["actions_done"].append("privacy")
        await asyncio.sleep(0.5)

    if await _save_edit_profile(driver, log):
        results["success"] = True

    results["duration_s"] = round(time.time() - start)
    log("-> Setup profil termine: %s (%ds)" % (results["actions_done"], results["duration_s"]))
    return results
