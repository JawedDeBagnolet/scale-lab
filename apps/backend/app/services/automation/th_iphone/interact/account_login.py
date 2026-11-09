"""
th_iphone/interact/account_login.py — Login/Create Threads via SSO Instagram (async).

Le compte IG doit etre deja log dans le container actif.

Usage:
    from ..interact.account_login import threads_sso_login
    await threads_sso_login(driver, navigator, log=print)
"""

import asyncio


async def threads_sso_login(driver, navigator, log=print):
    """Login ou creation compte Threads via SSO Instagram.

    Returns: dict {ok, username, created}
    """
    log("-> Threads SSO login")
    result = {"ok": False, "username": "", "created": False}

    await navigator.open_threads()
    await asyncio.sleep(3)

    # Detecter l ecran
    els = await driver.get_elements(refresh=True)
    texts = [e.get("text", "") for e in els]
    all_text = " ".join(texts).lower()

    # Deja sur le feed?
    if "menu latéral" in all_text:
        log("   deja connecte")
        result["ok"] = True
        return result

    # Chercher le bouton SSO
    sso = None
    for e in els:
        t = e.get("text", "")
        if "Se connecter" in t and "profil" in t and "Instagram" in t:
            sso = e
            break

    if not sso:
        log("   ! bouton SSO non trouve")
        return result

    # Extraire le username
    t = sso.get("text", "")
    if "@" in t:
        result["username"] = t.split("@")[1].split(" ")[0].strip()
    log("   SSO: %s" % t[:60])

    # 1. Tap SSO
    await driver.ht.tap(sso["tap"]["x"], sso["tap"]["y"])
    await asyncio.sleep(4)

    # 2. Ecran "Configurez votre experience" -> Suivant
    els = await driver.get_elements(refresh=True)
    all_text = " ".join([e.get("text", "") for e in els]).lower()

    if "configurez votre" in all_text:
        log("   config experience -> Suivant")
        result["created"] = True
        await driver.tap_element(text="Suivant")
        await asyncio.sleep(4)
    elif "menu latéral" in all_text:
        log("   connecte directement")
        result["ok"] = True
        await navigator._dismiss_popups()
        return result

    # 3. Ecran "Confirmez" -> Confirmer et rejoindre Threads
    els = await driver.get_elements(refresh=True)
    all_text = " ".join([e.get("text", "") for e in els]).lower()

    if "confirmez" in all_text:
        log("   confirmer et rejoindre")
        await driver.tap_element(text="Confirmer et rejoindre Threads")
        await asyncio.sleep(6)

    # 4. Dismiss popups
    await navigator._dismiss_popups()
    await asyncio.sleep(1)
    await navigator._dismiss_popups()

    # 5. Verifier feed
    screen = await driver.detect_current_screen()
    if screen == "feed":
        log("   Threads login OK!")
        result["ok"] = True
    else:
        log("   ecran final: %s" % screen)
        await navigator._dismiss_popups()
        await asyncio.sleep(1)
        screen = await driver.detect_current_screen()
        result["ok"] = (screen == "feed")

    return result
