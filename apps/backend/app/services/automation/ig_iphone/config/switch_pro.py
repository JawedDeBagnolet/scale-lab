"""
ig_iphone/config/switch_pro.py — Passage en compte professionnel IG.

Types: "Creator" ou "Professionnel"

Ported from VPS — adapted to async.
"""

import asyncio
import json
from typing import Callable


async def _get_elements(driver) -> list:
    """Recupere les elements UI bruts via MCP."""
    r = await driver.ht._call("get_ui_elements", {"clickable_only": False, "max_elements": 50})
    if not r:
        return []
    for c in r.get("content", []):
        if c.get("type") == "text":
            try:
                data = json.loads(c["text"])
                return data.get("elements", [])
            except Exception:
                pass
    return []


async def _find_and_tap(driver, elements, text, log=None, max_len=80) -> bool:
    """Cherche un element par texte et tape dessus."""
    text_lower = text.lower()
    for el in elements:
        t = (el.get("text") or "")
        if text_lower in t.lower() and len(t) < max_len:
            tap = el.get("tap", {})
            if tap.get("x") and tap.get("y"):
                if log:
                    log("   tap '%s'" % t[:40])
                await driver.ht.tap(tap["x"], tap["y"])
                return True
    return False


def _has_text(elements, text) -> bool:
    """Verifie si un texte est present."""
    text_lower = text.lower()
    for el in elements:
        if text_lower in (el.get("text") or "").lower():
            return True
    return False


async def switch_to_pro(driver, navigator, category="Artiste", account_type="Creator",
                        show_category=True, log: Callable = print) -> bool:
    """Passe en compte professionnel.

    Args:
        category: categorie du profil (ex: "Artiste", "Photographe", "Blog personnel")
        account_type: "Creator" ou "Professionnel"
        show_category: afficher la categorie sur le profil
    """
    log("-> Switch Pro: %s (%s)" % (category, account_type))

    await navigator.go_profile()
    await asyncio.sleep(1)

    # Ouvrir Modifier le profil
    for attempt in range(3):
        els = await _get_elements(driver)
        found_edit = False
        for el in els:
            t = (el.get("text") or "")
            if t in ("Modifier", "Modifier le profil"):
                tap = el.get("tap", {})
                if tap.get("x") and tap.get("y"):
                    log("   tap '%s'" % t)
                    await driver.ht.tap(tap["x"], tap["y"])
                    found_edit = True
                    break
        if found_edit:
            await asyncio.sleep(2)
            break
        log("   'Modifier le profil' non visible, scroll up (%d)" % (attempt + 1))
        await driver.scroll_up('light')
        await asyncio.sleep(1)

    # Verifier qu'on est sur l'ecran d'edition
    els = await _get_elements(driver)
    if (not _has_text(els, "Modifier le profil") and not _has_text(els, "Bio")
            and not _has_text(els, "Nom complet")):
        log("   ! ecran edition non atteint")
        return False

    # Scroll pour trouver "compte professionnel"
    for attempt in range(5):
        els = await _get_elements(driver)
        if _has_text(els, "compte professionnel"):
            await _find_and_tap(driver, els, "compte professionnel", log, max_len=50)
            break
        if not _has_text(els, "Bio") and not _has_text(els, "Nom") and not _has_text(els, "profil"):
            log("   ! sorti de l'edition, retour")
            await navigator.go_profile()
            await asyncio.sleep(1)
            continue
        log("   scroll pour trouver 'compte professionnel' (%d)" % (attempt + 1))
        await driver.scroll_down('light')
        await asyncio.sleep(1)
    else:
        log("   ! option compte pro non trouvee")
        return False

    await asyncio.sleep(2)

    # Etape 0: Ecran avantages → Suivant
    els = await _get_elements(driver)
    if _has_text(els, "Obtenez plus") or _has_text(els, "outils"):
        log("   ecran avantages -> Suivant")
        await _find_and_tap(driver, els, "Suivant", log, max_len=15)
        await asyncio.sleep(2)

    # Etape 1: Categories — chercher la categorie
    els = await _get_elements(driver)
    if _has_text(els, "Recherchez dans les"):
        await _find_and_tap(driver, els, "Recherchez dans les", log, max_len=50)
        await asyncio.sleep(0.5)
        await driver.type_text(category, method="fast")
        await asyncio.sleep(1.5)

        els = await _get_elements(driver)
        if not await _find_and_tap(driver, els, category, log, max_len=60):
            log("   ! categorie '%s' non trouvee" % category)
            return False
        await asyncio.sleep(1)

    # Toggle "Afficher sur le profil"
    els = await _get_elements(driver)
    if _has_text(els, "Afficher sur le profil"):
        if not show_category:
            await _find_and_tap(driver, els, "Commutateur", log, max_len=20)
            await asyncio.sleep(0.5)

    # Tap "Passer à un profil professionnel"
    els = await _get_elements(driver)
    if await _find_and_tap(driver, els, "Passer à un profil", log, max_len=50):
        log("   -> passage en pro (attente ~30s)")
        for wait in range(15):
            await asyncio.sleep(2)
            els = await _get_elements(driver)
            if _has_text(els, "Quel type") or _has_text(els, "Creator"):
                break

    # Etape 2: Type — Creator ou Professionnel
    els = await _get_elements(driver)
    if _has_text(els, "Quel type"):
        if account_type == "Professionnel":
            await _find_and_tap(driver, els, "Professionnel. Id", log, max_len=100)
            await asyncio.sleep(0.5)
        await _find_and_tap(driver, els, "Suivant", log, max_len=15)
        await asyncio.sleep(3)

    # Etape 3: Securite — tap OK
    els = await _get_elements(driver)
    if _has_text(els, "Modifications apport") or _has_text(els, "curit"):
        await _find_and_tap(driver, els, "OK", log, max_len=5)
        await asyncio.sleep(2)

    # Etape 3b: E-mails promotionnels
    els = await _get_elements(driver)
    if _has_text(els, "E-mails promotionnels") or _has_text(els, "ressources et des offres"):
        log("   ecran e-mails promo -> decocher + Suivant")
        await _find_and_tap(driver, els, "E-mails promotionnels", log, max_len=100)
        await asyncio.sleep(0.5)
        els = await _get_elements(driver)
        await _find_and_tap(driver, els, "Suivant", log, max_len=15)
        await asyncio.sleep(2)

    # Etape 4: Ecran configuration → Annuler
    for _ in range(3):
        els = await _get_elements(driver)
        if (_has_text(els, "Configurez votre") or _has_text(els, "compte professionnel")
                or _has_text(els, "tapes termin")):
            await _find_and_tap(driver, els, "Annuler", log, max_len=15)
            await asyncio.sleep(1.5)
        else:
            break

    log("   compte %s (%s) active" % (account_type, category))
    return True
