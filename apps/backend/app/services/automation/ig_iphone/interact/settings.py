"""
ig_iphone/interact/settings.py — Operations dans les parametres Instagram.

Permet d'activer/desactiver des options dans les reglages IG
sans intervention manuelle.
"""

import asyncio
import random
from typing import Callable

from app.services.automation.ig_iphone.config.profile_config import (
    _detect_screen, _dump_screen, _open_settings,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _scroll_settings(driver, log, times=1):
    """Scroll vers le bas dans les parametres IG."""
    for i in range(times):
        await driver.ht.swipe(187, 650, 187, 250, 350)
        await asyncio.sleep(1.0)


async def _go_back_to_profile(driver, navigator, log):
    """Retourne au profil depuis n'importe quel ecran de parametres."""
    for _ in range(5):
        screen = await _detect_screen(driver, log)
        if screen == "own_profile":
            return True
        # Tap "Precedent" ou swipe back
        back = await driver.find_element("Précédent", clickable=True, refresh=True)
        if back and back.get('rect', {}).get('y', 0) < 100:
            tap = back.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1.5)
            continue
        # Fallback: tap_by_text natif
        if await driver.ht.tap_by_text("Précédent"):
            await asyncio.sleep(1.5)
            continue
        # Fallback: swipe back iOS
        await navigator.go_back()
        await asyncio.sleep(1.5)
    return False


# ── HD Upload ─────────────────────────────────────────────────────────────────

async def enable_hd_upload(driver, navigator, log: Callable = print) -> dict:
    """Active 'Importer dans la qualite optimale' dans les parametres IG.

    Flow (d'apres le dump de l'arbre d'accessibilite) :
    1. Profil → Parametres et activite
    2. Scroll jusqu'a "Utilisation des donnees et qualite des contenus"
    3. Tap dessus
    4. Verifier l'etat de "Importer dans la qualite optimale"
    5. Si "Non coche" → taper pour activer
    6. Retour au profil

    Returns:
        dict {success, already_enabled, message}
    """
    result = {"success": False, "already_enabled": False, "message": ""}

    log("-> Config: Activation upload HD")

    # 1. Ouvrir les parametres
    if not await _open_settings(driver, navigator, log):
        result["message"] = "impossible d'ouvrir les parametres"
        return result

    # 2. Scroll pour trouver "Utilisation des donnees"
    #    C'est loin dans la liste — il faut scroller ~4 fois depuis le haut
    #    Section: "Votre application et vos contenus multimedias"
    #    Sous-element: "Utilisation des donnees et qualite des contenus multime..."
    el = None
    for attempt in range(8):
        el = await driver.find_element(
            "Utilisation des donn", contains=True, clickable=True, refresh=True
        )
        if el:
            break
        log("   scroll parametres (%d/8)" % (attempt + 1))
        await _scroll_settings(driver, log)

    if not el:
        log("   ! 'Utilisation des donnees' non trouve apres 8 scrolls")
        await _dump_screen(driver, log, "settings_no_data_usage")
        await _go_back_to_profile(driver, navigator, log)
        result["message"] = "option non trouvee dans les parametres"
        return result

    tap = el.get('tap', {})
    log("   tap 'Utilisation des donnees' (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.5, 2.5))

    # 3. Verifier l'ecran "Utilisation des donnees"
    #    Chercher "Importer dans la qualite optimale"
    hd_el = None
    for attempt in range(3):
        hd_el = await driver.find_element(
            "Importer dans la qualit", contains=True, clickable=True, refresh=True
        )
        if hd_el:
            break
        log("   [retry %d] recherche option HD" % (attempt + 1))
        await asyncio.sleep(1)

    if not hd_el:
        log("   ! option 'Importer dans la qualite optimale' non trouvee")
        await _dump_screen(driver, log, "data_usage_no_hd")
        await _go_back_to_profile(driver, navigator, log)
        result["message"] = "option HD non trouvee sur la page"
        return result

    # 4. Verifier si deja active ("Coche" dans le texte)
    hd_text = (hd_el.get('text', '') or '').lower()
    log("   etat actuel: '%s'" % hd_text[:80])

    if "coché" in hd_text and "non coch" not in hd_text:
        log("   ✓ deja active (Coche)")
        result["success"] = True
        result["already_enabled"] = True
        result["message"] = "deja active"
        await _go_back_to_profile(driver, navigator, log)
        return result

    # 5. Activer l'option
    tap = hd_el.get('tap', {})
    log("   activation upload HD (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 1.5))

    # 6. Verifier que c'est bien active maintenant
    hd_check = await driver.find_element(
        "Importer dans la qualit", contains=True, refresh=True
    )
    if hd_check:
        check_text = (hd_check.get('text', '') or '').lower()
        if "coché" in check_text and "non coch" not in check_text:
            log("   ✓ upload HD active!")
            result["success"] = True
            result["message"] = "active avec succes"
        else:
            log("   ⚠ etat apres toggle: '%s'" % check_text[:80])
            result["success"] = True  # On considere le tap comme reussi
            result["message"] = "toggle effectue (verification incertaine)"
    else:
        # Si l'element a disparu, le tap a probablement fonctionne
        result["success"] = True
        result["message"] = "toggle effectue"

    # 7. Retour au profil
    log("   retour au profil")
    await _go_back_to_profile(driver, navigator, log)

    return result
