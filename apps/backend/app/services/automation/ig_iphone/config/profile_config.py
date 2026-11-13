"""
ig_iphone/config/profile_config.py — Configuration du profil Instagram.

Modifie le nom, username, bio, photo, genre, liens, confidentialite, etc.

Ported from VPS (803 lines) — adapted to async.
"""

import asyncio
import random
from typing import Any, Callable


# ── Navigation helpers ────────────────────────────────────────────────────────

async def _open_edit_profile(driver, navigator, log) -> bool:
    """Ouvre l'ecran Modifier le profil."""
    await navigator.go_profile()
    await asyncio.sleep(1)
    el = await driver.find_element(text="Modifier le profil", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="Modifier le profil", clickable=True, refresh=True)
    if not el:
        log("   ! bouton 'Modifier le profil' non trouve")
        return False
    tap = el.get('tap', {})
    log("   ouvre edition profil")
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(1.5)
    return True


async def _open_settings(driver, navigator, log) -> bool:
    """Ouvre l'ecran Parametres et activite."""
    await navigator.go_profile()
    await asyncio.sleep(1)
    el = await driver.find_element(contains="param", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="activit", clickable=True, refresh=True)
    if not el:
        log("   ! bouton parametres non trouve")
        return False
    tap = el.get('tap', {})
    log("   ouvre parametres")
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(1.5)
    return True


async def _tap_field(driver, log, field_name) -> bool:
    """Tape sur un champ dans l'ecran d'edition."""
    el = await driver.find_element(contains=field_name, clickable=True, refresh=True)
    if not el:
        log("   ! champ '%s' non trouve" % field_name)
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(1)
    return True


async def _clear_and_type(driver, log, text, current_text=""):
    """Efface le texte existant puis tape le nouveau naturellement."""
    # Methode 1 : bouton "Effacer le texte"
    clear_btn = await driver.find_element(contains="Effacer le texte", clickable=True, refresh=True)
    if clear_btn:
        tap = clear_btn.get('tap', {})
        log("   efface texte (bouton X)")
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(0.5)
        # Re-tap the text field area to restore focus after clearing
        # The clear button may dismiss the keyboard
        await asyncio.sleep(0.3)
    elif current_text:
        # Methode 2 : backspaces
        n = len(current_text) + 5
        log("   efface texte (%d backspaces)" % n)
        for _ in range(n):
            await driver.ht._call("press_key", {"key": "backspace"})
        await asyncio.sleep(0.3)

    # Taper le nouveau texte via input_text (direct insertion, more reliable)
    log("   saisie texte: '%s'" % text[:40])
    await driver.ht._call("input_text", {"text": text})
    await asyncio.sleep(0.5)


async def _dismiss_popup(driver, log, wait=1.5):
    """Gere les popups de confirmation apres modification."""
    await asyncio.sleep(wait)
    confirm = await driver.find_element(contains="Modifier le", clickable=True, refresh=True)
    if confirm:
        r = confirm.get('rect', {})
        if r.get('width', 0) >= 200:
            tap = confirm.get('tap', {})
            log("   confirme modification")
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await asyncio.sleep(1)
            return
    ok = await driver.find_element(text="OK", clickable=True, refresh=True)
    if ok:
        r = ok.get('rect', {})
        if r.get('width', 0) >= 100:
            tap = ok.get('tap', {})
            log("   confirme (OK)")
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.5)
            return


async def _verify_on_edit_screen(driver, log) -> bool:
    """Verifie qu'on est bien sur l'ecran d'edition de profil."""
    els = await driver.find_elements(contains="Modifier le profil", refresh=True)
    if els:
        return True
    log("   ! pas sur l'ecran edit -> retour")
    await driver.ht._ensure_screen()
    y = driver.ht.screen_h * 0.4
    await driver.ht.swipe(5, y, driver.ht.screen_w * 0.6, y, 250)
    await asyncio.sleep(1)
    els = await driver.find_elements(contains="Modifier le profil", refresh=True)
    return bool(els)


async def _tap_done(driver, log) -> bool:
    """Tape sur 'C'est fait' ou 'Terminé' pour sauvegarder le champ."""
    el = await driver.find_element(contains="est fait", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(text="Terminé", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="Termin", clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        log("   -> Termine")
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(1)
        return True
    log("   ! Termine non trouve")
    return False


async def _go_back(driver, navigator, log):
    """Retour arriere."""
    await navigator.go_back()
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(0.5)


# ── Fonctions individuelles ──────────────────────────────────────────────────

async def set_name(driver, navigator, name, log: Callable = print) -> bool:
    """Change le nom complet du profil."""
    log("-> Config: nom -> '%s'" % name)
    if not await _open_edit_profile(driver, navigator, log):
        return False
    if not await _tap_field(driver, log, "Nom complet"):
        await _go_back(driver, navigator, log)
        return False
    await _clear_and_type(driver, log, name)
    await _tap_done(driver, log)
    await _go_back(driver, navigator, log)
    log("   nom modifie")
    return True


async def set_username(driver, navigator, username, log: Callable = print) -> bool:
    """Change le nom de profil (username)."""
    log("-> Config: username -> '@%s'" % username)
    if not await _open_edit_profile(driver, navigator, log):
        return False
    if not await _tap_field(driver, log, "Nom de profil"):
        await _go_back(driver, navigator, log)
        return False
    await _clear_and_type(driver, log, username)
    await _tap_done(driver, log)
    await _go_back(driver, navigator, log)
    log("   username modifie")
    return True


async def set_bio(driver, navigator, bio, log: Callable = print) -> bool:
    """Change la bio du profil."""
    log("-> Config: bio -> '%s'" % bio[:40])
    if not await _open_edit_profile(driver, navigator, log):
        return False
    els = await driver.find_elements(text="Bio", clickable=True, refresh=True)
    best = None
    for e in els:
        w = e.get('rect', {}).get('width', 0)
        if not best or w > best.get('rect', {}).get('width', 0):
            best = e
    if not best:
        log("   ! champ Bio non trouve")
        await _go_back(driver, navigator, log)
        return False
    tap = best.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(1)
    await _clear_and_type(driver, log, bio)
    await _tap_done(driver, log)
    await _go_back(driver, navigator, log)
    log("   bio modifiee")
    return True


async def set_pronouns(driver, navigator, pronouns, log: Callable = print) -> bool:
    """Change les pronoms."""
    log("-> Config: pronoms -> '%s'" % pronouns)
    if not await _open_edit_profile(driver, navigator, log):
        return False
    if not await _tap_field(driver, log, "Pronoms"):
        await _go_back(driver, navigator, log)
        return False
    await _clear_and_type(driver, log, pronouns)
    await _tap_done(driver, log)
    await _go_back(driver, navigator, log)
    log("   pronoms modifies")
    return True


async def set_gender(driver, navigator, gender, log: Callable = print) -> bool:
    """Change le genre."""
    log("-> Config: genre -> '%s'" % gender)
    if not await _open_edit_profile(driver, navigator, log):
        return False
    await driver.scroll_down('light')
    await asyncio.sleep(0.5)
    if not await _tap_field(driver, log, "Genre"):
        await _go_back(driver, navigator, log)
        return False
    option = await driver.find_element(contains=gender, clickable=True, refresh=True)
    if option:
        tap = option.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(0.5)
    await _tap_done(driver, log)
    await _go_back(driver, navigator, log)
    log("   genre modifie")
    return True


async def add_link(driver, navigator, url, title=None, log: Callable = print) -> bool:
    """Ajoute un lien au profil."""
    log("-> Config: lien -> '%s'" % url)
    if not await _open_edit_profile(driver, navigator, log):
        return False
    if not await _tap_field(driver, log, "Ajouter des liens"):
        await _go_back(driver, navigator, log)
        return False
    el = await driver.find_element(contains="lien externe", clickable=True, refresh=True)
    if not el:
        el = await driver.find_element(contains="Ajouter un lien", clickable=True, refresh=True)
    if el:
        tap = el.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(1)
        url_field = await driver.find_element(contains="URL", clickable=True, refresh=True)
        if url_field:
            tap = url_field.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(0.3)
            await driver.ht._call("input_text", {"text": url})
            await asyncio.sleep(0.5)
        if title:
            title_field = await driver.find_element(contains="Titre", clickable=True, refresh=True)
            if title_field:
                tap = title_field.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(0.3)
                await driver.ht._call("input_text", {"text": title})
                await asyncio.sleep(0.5)
        await _tap_done(driver, log)
    await _go_back(driver, navigator, log)
    await _go_back(driver, navigator, log)
    log("   lien ajoute")
    return True


async def set_profile_photo(driver, navigator, photo_index=0, log: Callable = print) -> bool:
    """Change la photo de profil."""
    log("-> Config: photo de profil (index=%d)" % photo_index)
    if not await _open_edit_profile(driver, navigator, log):
        return False
    el = await driver.find_element(contains="Modifier la photo", clickable=True, refresh=True)
    if not el:
        log("   ! bouton photo profil non trouve")
        await _go_back(driver, navigator, log)
        return False
    tap = el.get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(1.5)
    gallery = await driver.find_element(contains="galerie", clickable=True, refresh=True)
    if not gallery:
        gallery = await driver.find_element(contains="biblioth", clickable=True, refresh=True)
    if not gallery:
        gallery = await driver.find_element(contains="Nouvelle photo", clickable=True, refresh=True)
    if gallery:
        tap = gallery.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(2)
        photos = await driver.find_elements(contains="Miniature", clickable=True, refresh=True)
        if photos and photo_index < len(photos):
            tap = photos[photo_index].get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await asyncio.sleep(1)
            await _tap_done(driver, log)
            await asyncio.sleep(2)
    await _go_back(driver, navigator, log)
    log("   photo de profil modifiee")
    return True


async def set_private(driver, navigator, private=True, log: Callable = print) -> bool:
    """Passe le compte en prive ou public."""
    log("-> Config: compte %s" % ("prive" if private else "public"))
    if not await _open_settings(driver, navigator, log):
        return False

    conf_el = None
    for attempt in range(3):
        els = await driver.find_elements(refresh=True, clickable=True)
        for e in els:
            t = (e.get('text', '') or '')
            if 'Confidentialit' in t:
                conf_el = e
                break
        if conf_el:
            break
        log("   scroll pour trouver Confidentialite (%d)" % (attempt + 1))
        await driver.scroll_down('light')
        await asyncio.sleep(2)

    if not conf_el:
        log("   ! Confidentialite introuvable")
        await _go_back(driver, navigator, log)
        return False

    # Re-refresh pour avoir les positions apres inertie
    els = await driver.find_elements(refresh=True, clickable=True)
    for e in els:
        t = (e.get('text', '') or '')
        if 'Confidentialit' in t:
            conf_el = e
            break

    tap = conf_el.get('tap', {})
    log("   tap '%s' (y=%d)" % (conf_el.get('text', '')[:40], tap.get('y', 0)))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))
    await asyncio.sleep(2)

    check = await driver.find_element(contains="Compte priv", refresh=True)
    if not check:
        log("   ! pas sur l'ecran confidentialite")
        await _go_back(driver, navigator, log)
        await _go_back(driver, navigator, log)
        return False

    # Detecter l'etat
    all_els = await driver.find_elements(refresh=False, clickable=None)
    is_currently_private = True
    for e in all_els:
        t = (e.get('text', '') or '')
        if 'Non coch' in t and 'Compte priv' in t:
            is_currently_private = False
            break
    log("   etat actuel: %s" % ("prive" if is_currently_private else "public"))

    if private == is_currently_private:
        log("   deja %s" % ("prive" if private else "public"))
        await _go_back(driver, navigator, log)
        await _go_back(driver, navigator, log)
        return True

    # Toggle
    toggle = await driver.find_element(contains="Compte priv", clickable=True, refresh=True)
    if toggle:
        rect = toggle.get('rect', {})
        switch_x = rect.get('x', 0) + rect.get('width', 375) - 40
        switch_y = rect.get('y', 92) + rect.get('height', 48) / 2
        log("   toggle switch (%d, %d)" % (switch_x, switch_y))
        await driver.ht.tap(switch_x, switch_y)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(2)

        # Popup de confirmation
        confirms = await driver.find_elements(contains="Passer", clickable=True, refresh=True)
        confirmed = False
        for c in confirms:
            r = c.get('rect', {})
            if r.get('width', 0) >= 200 and r.get('height', 0) >= 40:
                tap = c.get('tap', {})
                log("   confirme changement (y=%d)" % tap.get('y', 0))
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await asyncio.sleep(2)
                confirmed = True
                break

        if not confirmed:
            ok_el = await driver.find_element(text="OK", clickable=True, refresh=True)
            if ok_el:
                tap = ok_el.get('tap', {})
                log("   ! impossible (compte Creator?) -> OK")
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(1)
        else:
            await asyncio.sleep(1.5)
            ok_el = await driver.find_element(text="OK", clickable=True, refresh=True)
            if ok_el:
                r = ok_el.get('rect', {})
                if r.get('width', 0) >= 100:
                    tap = ok_el.get('tap', {})
                    log("   second popup -> OK")
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(1)

    await _go_back(driver, navigator, log)
    await _go_back(driver, navigator, log)
    log("   confidentialite -> %s" % ("prive" if private else "public"))
    return True


async def set_public(driver, navigator, log: Callable = print) -> bool:
    return await set_private(driver, navigator, private=False, log=log)


# ── Config batch (ouvre edit profil UNE SEULE FOIS) ───────────────────────────

async def configure_profile(driver, navigator, config: dict, log: Callable = print) -> dict:
    """Applique une config complete au profil en une seule passe.

    config = {
        "name": "Cassie Garcia",
        "username": "cassie.garcia",
        "bio": "Living my best life",
        "pronouns": "elle",
        "gender": "Femme",
        "link": {"url": "https://example.com", "title": "Mon site"},
        "photo_index": 0,
        "private": False,
        "pro": True,
    }
    """
    log("=" * 50)
    log("CONFIG PROFIL IG")
    log("=" * 50)

    results = {}

    # ── Phase 1 : champs dans "Modifier le profil" ──
    edit_fields = {}
    for key in ("name", "username", "bio", "pronouns", "gender", "link", "photo_index"):
        if key in config:
            edit_fields[key] = config[key]

    if edit_fields:
        if not await _open_edit_profile(driver, navigator, log):
            return results

        if "name" in edit_fields:
            log("   [1] nom -> '%s'" % edit_fields["name"])
            if await _tap_field(driver, log, "Nom complet"):
                await _clear_and_type(driver, log, edit_fields["name"])
                await _tap_done(driver, log)
                await _dismiss_popup(driver, log)
                await _verify_on_edit_screen(driver, log)
                results["name"] = True

        if "username" in edit_fields:
            log("   [2] username -> '@%s'" % edit_fields["username"])
            if await _tap_field(driver, log, "Nom de profil"):
                await _clear_and_type(driver, log, edit_fields["username"])
                await _tap_done(driver, log)
                await _dismiss_popup(driver, log)
                await _verify_on_edit_screen(driver, log)
                results["username"] = True

        if "bio" in edit_fields:
            log("   [3] bio -> '%s'" % str(edit_fields["bio"])[:40])
            best = None
            bio_els = await driver.find_elements(text="Bio", clickable=True, refresh=True)
            for e in bio_els:
                w = e.get('rect', {}).get('width', 0)
                if not best or w > best.get('rect', {}).get('width', 0):
                    best = e
            if best:
                tap = best.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await asyncio.sleep(1)
                # Select all existing text via backspaces then type new text
                # First try "Tout sélectionner" if available, else backspaces
                for _ in range(200):
                    await driver.ht._call("press_key", {"key": "backspace"})
                await asyncio.sleep(0.3)
                log("   saisie bio: '%s'" % edit_fields["bio"][:40])
                await driver.ht._call("type_text", {"text": edit_fields["bio"], "interval": 55})
                await asyncio.sleep(0.5)
                await _tap_done(driver, log)
                await _dismiss_popup(driver, log)
                await _verify_on_edit_screen(driver, log)
                results["bio"] = True

        if "link" in edit_fields:
            link = edit_fields["link"]
            if link and link != "":
                url = link.get("url", link) if isinstance(link, dict) else str(link)
                title = link.get("title") if isinstance(link, dict) else None
                log("   [4] lien -> '%s'" % url[:40])
            else:
                url = ""
                title = None
                log("   [4] lien -> (supprimer)")

            if await _tap_field(driver, log, "Ajouter des liens"):
                if url:
                    el = await driver.find_element(contains="Ajouter un lien", clickable=True, refresh=True)
                    if el:
                        tap = el.get('tap', {})
                        await driver.ht.tap(tap['x'], tap['y'])
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        await asyncio.sleep(1)
                        url_f = await driver.find_element(text="URL", clickable=True, refresh=True)
                        if url_f:
                            tap = url_f.get('tap', {})
                            await driver.ht.tap(tap['x'], tap['y'])
                            await asyncio.sleep(0.3)
                            await driver.type_text(url, method="fast")
                            await asyncio.sleep(0.5)
                        if title:
                            title_f = await driver.find_element(text="Titre", clickable=True, refresh=True)
                            if title_f:
                                tap = title_f.get('tap', {})
                                await driver.ht.tap(tap['x'], tap['y'])
                                await asyncio.sleep(0.3)
                                await driver.type_text(title, method="natural")
                                await asyncio.sleep(0.5)
                        await _tap_done(driver, log)
                        await asyncio.sleep(1)

                await _go_back(driver, navigator, log)
                results["link"] = True

        if "gender" in edit_fields:
            log("   [5] genre -> '%s'" % edit_fields["gender"])
            await driver.scroll_down('light')
            await asyncio.sleep(0.5)
            if await _tap_field(driver, log, "Genre"):
                option = await driver.find_element(contains=edit_fields["gender"], clickable=True, refresh=True)
                if option:
                    tap = option.get('tap', {})
                    log("   selectionne %s" % edit_fields["gender"])
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(0.5)
                await _tap_done(driver, log)
                await _dismiss_popup(driver, log)
                await _verify_on_edit_screen(driver, log)
                results["gender"] = True

        if "photo_index" in edit_fields:
            log("   [6] photo de profil")
            el = await driver.find_element(contains="Modifier la photo", clickable=True, refresh=True)
            if not el:
                await driver.scroll_up('normal')
                await asyncio.sleep(0.5)
                el = await driver.find_element(contains="Modifier la photo", clickable=True, refresh=True)
            if el:
                tap = el.get('tap', {})
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(random.uniform(1.0, 2.0))
                await asyncio.sleep(1.5)
                gallery = await driver.find_element(contains="Choisir dans la", clickable=True, refresh=True)
                if not gallery:
                    gallery = await driver.find_element(contains="biblioth", clickable=True, refresh=True)
                if gallery:
                    tap = gallery.get('tap', {})
                    log("   choisir dans la bibliotheque")
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    await asyncio.sleep(2)
                    photos = await driver.find_elements(contains="Miniature", clickable=True, refresh=True)
                    idx = edit_fields["photo_index"]
                    if photos and idx < len(photos):
                        tap = photos[idx].get('tap', {})
                        await driver.ht.tap(tap['x'], tap['y'])
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        await asyncio.sleep(1)
                        await _tap_done(driver, log)
                        log("   attente chargement photo...")
                        for _ in range(15):
                            await asyncio.sleep(1)
                            check = await driver.find_element(contains="Modifier le profil", refresh=True)
                            if check:
                                log("   photo chargee")
                                break
                results["photo"] = True

        # Fermer l'edit profil
        await _go_back(driver, navigator, log)

    # ── Phase 2 : switch pro ────
    if config.get("pro"):
        from .switch_pro import switch_to_pro
        results["pro"] = await switch_to_pro(driver, navigator, log=log)

    # ── Phase 3 : confidentialite ───────────────────────
    if "private" in config:
        results["private"] = await set_private(driver, navigator, config["private"], log)

    log("=" * 50)
    log("CONFIG TERMINEE: %s" % results)
    log("=" * 50)

    return results
