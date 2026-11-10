"""
th_iphone/interact/account_create.py — Creation compte Threads (async).

Cree un profil Threads a partir d'un compte IG existant.
Flow: login IG → privacy → confirm → notif → suggestions → feed

Usage:
    from ..interact.account_create import create_threads_account
"""

import asyncio
import random
import time


def _detect_creation_screen_sync(els):
    """Detecte l'ecran actuel du flow de creation (from cached elements)."""
    all_text = " ".join([e.get("text", "").lower() for e in els])

    if "menu latéral" in all_text or "quoi de neuf" in all_text:
        return "feed"
    if "choisissez comment vous inscrire" in all_text:
        return "welcome"
    if "threads de meta" in all_text and "mot de passe" in all_text:
        return "login_form"
    if "vérifiez vos notifications" in all_text:
        return "2fa_notif"
    if "choisissez un moyen de confirmer" in all_text:
        return "2fa_choice"
    if "accédez à votre application" in all_text or ("authentification" in all_text and "code" in all_text):
        return "2fa_code"
    if "configurez votre expérience" in all_text:
        return "privacy_setup"
    if "confirmer et rejoindre threads" in all_text:
        return "confirm_join"
    if "enregistrer vos informations de connexion" in all_text:
        return "save_login"
    if "veuillez activer les notifications" in all_text:
        return "notif_popup"
    if "suggestions de suivi" in all_text:
        return "follow_suggestions"
    if "challenge" in all_text or "suspect" in all_text:
        return "checkpoint"
    if "incorrect" in all_text or "réessayer" in all_text:
        return "login_error"

    return "unknown"


async def _detect_creation_screen(driver, log):
    els = await driver.get_elements(refresh=True)
    return _detect_creation_screen_sync(els)


async def create_threads_account(driver, navigator, username, password,
                                  totp_secret=None, code_2fa=None,
                                  private=False, log=print):
    """Cree un compte Threads a partir d'un compte IG."""
    start = time.time()
    stats = {
        "success": False,
        "checkpoint": False,
        "needs_2fa": False,
        "error": None,
        "duration_s": 0,
    }

    log("-> Creation compte Threads @%s" % username)

    await driver.ht.launch_app("com.burbn.barcelona")
    await driver.wait('transition')
    await asyncio.sleep(4)

    max_steps = 20
    for step in range(max_steps):
        screen = await _detect_creation_screen(driver, log)
        log("   [create] ecran: %s (step %d)" % (screen, step + 1))

        # Feed = succes
        if screen == "feed":
            stats["success"] = True
            log("   ✅ compte Threads cree!")
            break

        # Welcome
        elif screen == "welcome":
            if await driver.tap_element(contains="Continuer avec Instagram", refresh=True):
                log("   -> Continuer avec Instagram")
            elif await driver.tap_element(contains="Se connecter", refresh=True):
                log("   -> Se connecter")
            await driver.wait('transition')
            await asyncio.sleep(3)

        # Login form
        elif screen == "login_form":
            user_field = await driver.find_element(contains="Nom de profil", clickable=True, refresh=True)
            if not user_field:
                user_field = await driver.find_element(contains="e-mail", clickable=True, refresh=True)

            if user_field and user_field.get("tap"):
                await driver.ht.tap(user_field["tap"]["x"], user_field["tap"]["y"])
                await driver.wait('tap')
                await asyncio.sleep(0.5)
                log("   saisie username")
                await driver.type_text(username, method="slow")
                await asyncio.sleep(0.8)

            pw_field = await driver.find_element(contains="Mot de passe", clickable=True, refresh=True)
            if pw_field and pw_field.get("tap"):
                await driver.ht.tap(pw_field["tap"]["x"], pw_field["tap"]["y"])
                await driver.wait('tap')
                await asyncio.sleep(0.5)
                log("   saisie mot de passe")
                await driver.type_text(password, method="slow")
                await asyncio.sleep(0.8)

            if await driver.tap_element(contains="Se connecter", refresh=True):
                log("   -> Se connecter")
            await driver.wait('transition')
            await asyncio.sleep(5)

        # 2FA notification
        elif screen == "2fa_notif":
            if await driver.tap_element(contains="Essayer d'une autre", refresh=True):
                log("   -> Essayer d'une autre façon")
            await driver.wait('transition')
            await asyncio.sleep(2)

        # 2FA choix methode
        elif screen == "2fa_choice":
            if await driver.tap_element(contains="Application d'authentification", refresh=True):
                log("   -> Application d'authentification")
                await driver.wait('tap')
                await asyncio.sleep(1)
            if await driver.tap_element(contains="Continuer", refresh=True):
                log("   -> Continuer")
            await driver.wait('transition')
            await asyncio.sleep(3)

        # 2FA code
        elif screen == "2fa_code":
            actual_code = code_2fa
            if totp_secret:
                try:
                    import pyotp
                    actual_code = pyotp.TOTP(totp_secret).now()
                    log("   code TOTP genere: %s" % actual_code)
                except Exception as e:
                    log("   ! erreur TOTP: %s" % str(e)[:60])

            if not actual_code:
                log("   ⚠️  code 2FA requis mais non fourni")
                stats["needs_2fa"] = True
                stats["error"] = "needs_2fa_code"
                break

            code_field = await driver.find_element(text="Code", clickable=True, refresh=True)
            if not code_field:
                els = await driver.get_elements(refresh=True)
                for e in els:
                    if e.get("text", "").strip() == "Code" and e.get("tap", {}).get("y", 0) > 400:
                        code_field = e
                        break

            if code_field and code_field.get("tap"):
                await driver.ht.tap(code_field["tap"]["x"], code_field["tap"]["y"])
                await driver.wait('tap')
                await asyncio.sleep(0.5)
                log("   saisie code 2FA")
                await driver.type_text(str(actual_code), method="slow")
                await asyncio.sleep(0.8)

            if await driver.tap_element(contains="Continuer", refresh=True):
                log("   -> Continuer")
            await driver.wait('transition')
            await asyncio.sleep(5)

        # Privacy setup
        elif screen == "privacy_setup":
            if private:
                if await driver.tap_element(contains="Profil privé", refresh=True):
                    log("   -> Profil prive")
            else:
                if await driver.tap_element(contains="Profil public", refresh=True):
                    log("   -> Profil public")
            await driver.wait('tap')
            await asyncio.sleep(1)

            if await driver.tap_element(contains="Suivant", refresh=True):
                log("   -> Suivant")
            await driver.wait('transition')
            await asyncio.sleep(3)

        # Confirm join
        elif screen == "confirm_join":
            els = await driver.get_elements(refresh=True)
            confirm_btn = None
            for e in els:
                if "confirmer et rejoindre" in e.get("text", "").lower() and e.get("tap", {}).get("y", 0) > 680:
                    confirm_btn = e
                    break

            if confirm_btn:
                await driver.ht.tap(confirm_btn["tap"]["x"], confirm_btn["tap"]["y"])
                log("   -> Confirmer et rejoindre Threads")
            else:
                log("   ! bouton confirmer non trouve, fallback")
                els_match = [e for e in els if "confirmer et rejoindre" in e.get("text", "").lower()]
                if els_match:
                    last = max(els_match, key=lambda e: e.get("tap", {}).get("y", 0))
                    await driver.ht.tap(last["tap"]["x"], last["tap"]["y"])
                    log("   -> Confirmer (fallback y:%d)" % last["tap"]["y"])
            await driver.wait('transition')
            await asyncio.sleep(5)

        # Save login
        elif screen == "save_login":
            els = await driver.get_elements(refresh=True)
            save_btn = None
            for e in els:
                if "enregistrer" in e.get("text", "").lower() and e.get("tap", {}).get("y", 0) > 600:
                    save_btn = e
                    break
            if save_btn:
                await driver.ht.tap(save_btn["tap"]["x"], save_btn["tap"]["y"])
                log("   -> Enregistrer")
            else:
                await driver.tap_element(contains="Plus tard", refresh=True)
                log("   -> Plus tard (save)")
            await driver.wait('transition')
            await asyncio.sleep(3)

        # Notification popup
        elif screen == "notif_popup":
            if await driver.tap_element(contains="Plus tard", refresh=True):
                log("   -> Plus tard (notifications)")
            await driver.wait('transition')
            await asyncio.sleep(2)

        # Follow suggestions
        elif screen == "follow_suggestions":
            if await driver.tap_element(contains="Ignorer", refresh=True):
                log("   -> Ignorer (suggestions)")
            await driver.wait('transition')
            await asyncio.sleep(3)

        # Login error
        elif screen == "login_error":
            log("   ❌ erreur de login")
            stats["error"] = "wrong_credentials"
            break

        # Checkpoint
        elif screen == "checkpoint":
            log("   ⚠️  CHECKPOINT detecte")
            stats["checkpoint"] = True
            stats["error"] = "checkpoint"
            break

        # Unknown
        elif screen == "unknown":
            log("   ? ecran inconnu, attente...")
            await asyncio.sleep(3)
            screen2 = await _detect_creation_screen(driver, log)
            log("   [create] retry: %s" % screen2)
            if screen2 == "unknown":
                els = await driver.get_elements(refresh=True)
                for e in els:
                    text = e.get("text", "").lower()
                    y = e.get("tap", {}).get("y", 0)
                    if text in ["ok", "plus tard", "ne pas autoriser", "autoriser"] and y > 400:
                        await driver.ht.tap(e["tap"]["x"], e["tap"]["y"])
                        log("   popup fermee: %s" % text)
                        await asyncio.sleep(2)
                        break
                else:
                    screen3 = await _detect_creation_screen(driver, log)
                    if screen3 == "unknown":
                        log("   !! ecran toujours inconnu, abort")
                        stats["error"] = "unknown_screen"
                        break

    stats["duration_s"] = round(time.time() - start)
    return stats
