"""
ig_iphone/auth/login.py — Connexion a un compte IG.

Ported from VPS — adapted to async.

Usage:
    from ig_iphone.auth.login import login
    await login(driver, navigator, username="user", password="pass", totp_secret="SECRET")
"""

import asyncio
import json
from typing import Callable


async def _get_elements(driver) -> list:
    """Recupere les elements UI bruts via MCP (bypass find_element bugge)."""
    r = await driver.ht._call("get_ui_elements", {"clickable_only": False, "max_elements": 40})
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


async def _find_and_tap(driver, elements, text, log=None, max_len=40) -> bool:
    """Cherche un element par texte et tape dessus."""
    text_lower = text.lower()
    for el in elements:
        t = (el.get("text") or "")
        if text_lower in t.lower() and len(t) < max_len:
            tap = el.get("tap", {})
            if tap.get("x") and tap.get("y"):
                if log:
                    log("   tap '%s'" % t[:30])
                await driver.ht.tap(tap["x"], tap["y"])
                return True
    return False


def _has_text(elements, text) -> bool:
    """Verifie si un texte est present dans les elements."""
    text_lower = text.lower()
    for el in elements:
        t = (el.get("text") or "")
        if text_lower in t.lower():
            return True
    return False


async def _dismiss_post_login_popups(driver, log, max_popups=8) -> bool:
    """Gere les popups post-login."""
    prefer = ["Enregistrer", "Plus tard", "Non merci", "Pas maintenant", "Passer"]

    for i in range(max_popups):
        await asyncio.sleep(2)
        els = await _get_elements(driver)

        # Verifier si on est sur le feed/profil
        if _has_text(els, "Fil principal") or _has_text(els, "Explorer"):
            log("   connecte !")
            return True

        # Chercher un bouton connu (< 20 chars = bouton, pas titre)
        found = False
        for pref in prefer:
            for el in els:
                t = (el.get("text") or "")
                if pref.lower() in t.lower() and len(t) < 20:
                    tap = el.get("tap", {})
                    if tap.get("x") and tap.get("y"):
                        log("   popup: '%s'" % t)
                        await driver.ht.tap(tap["x"], tap["y"])
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        found = True
                        break
            if found:
                break

        if not found:
            log("   popup #%d: aucun bouton connu" % (i + 1))
            for el in els:
                t = (el.get("text") or "")[:40]
                if t:
                    log("      > %s" % t)
            break

    return False


async def _handle_2fa(driver, code, totp_secret, log) -> bool:
    """Gere le flow 2FA complet via elements bruts."""
    # Attendre que l'ecran 2FA charge (retry)
    els = []
    for wait in range(5):
        await asyncio.sleep(2)
        els = await _get_elements(driver)
        if (_has_text(els, "notifications") or _has_text(els, "approbation") or
                _has_text(els, "Choisissez") or _has_text(els, "6 chiffres") or
                _has_text(els, "Code")):
            break
        if _has_text(els, "Fil principal") or _has_text(els, "Explorer"):
            return True  # Pas de 2FA, deja connecte

    # Etape 1: ecran "Vérifiez vos notifications" → tap "Essayer d'une autre façon"
    if _has_text(els, "notifications") or _has_text(els, "approbation"):
        log("   2FA: notifications -> essayer autre")
        if not await _find_and_tap(driver, els, "autre fa", log, max_len=50):
            # Fallback coordonnees
            await driver.ht.tap(187, 567)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(2)
        els = await _get_elements(driver)

    # Etape 2: "Choisissez un moyen" → "Application d'authentification" → "Continuer"
    if _has_text(els, "Choisissez") or _has_text(els, "moyen de confirmer"):
        log("   2FA: choix methode -> application")
        await _find_and_tap(driver, els, "authentification", log, max_len=100)
        await asyncio.sleep(0.5)
        els = await _get_elements(driver)
        await _find_and_tap(driver, els, "Continuer", log)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        await asyncio.sleep(2)
        els = await _get_elements(driver)

    # Etape 3: ecran code TOTP
    if _has_text(els, "6 chiffres") or _has_text(els, "Code"):
        log("   2FA: ecran code")

        # Generer le code TOTP
        if totp_secret and not code:
            try:
                import pyotp
                code = pyotp.TOTP(totp_secret).now()
                log("   TOTP: %s" % code)
            except Exception as e:
                log("   ! TOTP erreur: %s" % str(e)[:80])
                return False

        if not code:
            log("   ! 2FA: aucun code fourni")
            return False

        # Taper le code
        await _find_and_tap(driver, els, "Code", log)
        await asyncio.sleep(0.5)
        await driver.type_text(str(code), method="fast")
        await asyncio.sleep(1)

        # Continuer
        els = await _get_elements(driver)
        await _find_and_tap(driver, els, "Continuer", log)

        # Attendre la fin du chargement
        for wait in range(8):
            await asyncio.sleep(2)
            els = await _get_elements(driver)
            if _has_text(els, "Chargement"):
                log("   chargement 2FA...")
                continue
            if _has_text(els, "6 chiffres") or _has_text(els, "Code"):
                continue  # Toujours sur l'ecran code
            break  # Ecran change

        return True

    return False


import random


async def login(driver, navigator, username, password,
                code_2fa=None, totp_secret=None, log: Callable = print) -> bool:
    """Connecte un compte IG."""
    log("-> Auth: login '%s'" % username)

    await driver.ht.launch("com.burbn.instagram")
    await asyncio.sleep(4)

    # Boucle de navigation vers l'ecran de login
    for attempt in range(3):
        els = await _get_elements(driver)

        # Deja connecte ?
        if _has_text(els, "Fil principal") or _has_text(els, "Explorer"):
            log("   deja connecte")
            return True

        # Ecran d'accueil "Rejoignez Instagram"
        if _has_text(els, "Rejoignez") or _has_text(els, "marrer"):
            if await _find_and_tap(driver, els, "profil", log, max_len=30):
                await asyncio.sleep(2)
                continue

        # Ecran de login
        if _has_text(els, "Se connecter") or _has_text(els, "Mot de passe"):
            break

        # Ecran inconnu — fermer/retour
        log("   ecran inconnu, tentative retour (%d)" % (attempt + 1))
        await driver.ht._call("press_key", {"key": "home"})
        await asyncio.sleep(1)
        await driver.ht.launch("com.burbn.instagram")
        await asyncio.sleep(4)

    # Ecran de login
    els = await _get_elements(driver)
    if not _has_text(els, "Mot de passe"):
        log("   ! ecran login non atteint")
        return False

    # Username
    await _find_and_tap(driver, els, "profil, e-mail", log, max_len=60)
    if not await _find_and_tap(driver, els, "profil, e-mail", log, max_len=60):
        await _find_and_tap(driver, els, "Nom de profil", log, max_len=60)
    await asyncio.sleep(0.5)
    await driver.type_text(username, method="fast")
    await asyncio.sleep(1)

    # Password — afficher puis taper
    els = await _get_elements(driver)
    await _find_and_tap(driver, els, "Mot de passe", log, max_len=20)
    await asyncio.sleep(0.5)
    els = await _get_elements(driver)
    if await _find_and_tap(driver, els, "Afficher le mot", log, max_len=30):
        await asyncio.sleep(0.3)
        els = await _get_elements(driver)
        await _find_and_tap(driver, els, "Mot de passe", log, max_len=20)
        await asyncio.sleep(0.3)
    log("   typing password (%d chars)" % len(password))
    await driver.type_text(password, method="natural")
    await asyncio.sleep(1)

    # Se connecter
    els = await _get_elements(driver)
    if await _find_and_tap(driver, els, "Se connecter", log, max_len=20):
        log("   -> Se connecter")
    await asyncio.sleep(8)

    # 2FA
    await _handle_2fa(driver, code_2fa, totp_secret, log)

    # Popups post-login
    if await _dismiss_post_login_popups(driver, log):
        log("   login OK")
        return True

    # Dernier check
    els = await _get_elements(driver)
    if _has_text(els, "Fil principal") or _has_text(els, "Explorer"):
        log("   login OK")
        return True

    if _has_text(els, "incorrect") or _has_text(els, "introuvable"):
        log("   ! identifiants incorrects")
        return False

    log("   ! login echoue")
    return False


async def logout(driver, navigator, log: Callable = print) -> bool:
    """Deconnecte le compte IG actuel."""
    log("-> Auth: logout")
    await navigator.go_profile()
    await asyncio.sleep(1)

    # Burger menu
    await driver.ht._ensure_screen()
    await driver.ht.tap(driver.ht.screen_w - 30, 55)
    await asyncio.sleep(1.5)

    els = await _get_elements(driver)
    if not await _find_and_tap(driver, els, "aramètre", log, max_len=30):
        await _find_and_tap(driver, els, "Param", log, max_len=30)
    await asyncio.sleep(1.5)

    for _ in range(5):
        els = await _get_elements(driver)
        if await _find_and_tap(driver, els, "connexion", log, max_len=20):
            await asyncio.sleep(1.5)
            els = await _get_elements(driver)
            # Confirmation
            for el in els:
                t = (el.get("text") or "")
                r = el.get("rect", {})
                if "connexion" in t.lower() and len(t) < 20 and r.get("width", 0) >= 200:
                    tap = el.get("tap", {})
                    await driver.ht.tap(tap["x"], tap["y"])
                    await asyncio.sleep(3)
                    break
            break
        await driver.scroll_down('normal')
        await asyncio.sleep(1)

    log("   logout OK")
    return True


async def switch_account(driver, navigator, username, password,
                         code_2fa=None, totp_secret=None, log: Callable = print) -> bool:
    """Deconnecte et connecte un autre compte."""
    log("-> Auth: switch -> '%s'" % username)
    await logout(driver, navigator, log=log)
    await asyncio.sleep(2)
    return await login(driver, navigator, username, password,
                       code_2fa=code_2fa, totp_secret=totp_secret, log=log)
