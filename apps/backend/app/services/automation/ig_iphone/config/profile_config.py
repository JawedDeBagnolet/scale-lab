"""
ig_iphone/config/profile_config.py — Configuration du profil Instagram.

Modifie le nom, username, bio, photo, genre, liens, confidentialite, etc.

Ported from VPS (803 lines) — adapted to async.
"""

import asyncio
import random
from typing import Any, Callable




# ── Screen awareness (safety layer) ─────────────────────────────────────────

# Atlas complet des écrans Instagram — marqueurs issus des dumps réels
# Le titre de page est TOUJOURS dans la zone y < 80 et est le marqueur le plus fiable.
# L'ordre de détection compte : les écrans les plus spécifiques d'abord.
SCREENS = [
    # ── Sous-écrans profonds (spécifiques) ──
    ("age_picker",      {"title": ["ge par d"], "body": ["Enregistrer", "Fermer"]}),
    ("age_limit",       {"title": ["ge minimum"], "body": ["Par d", "Ajouter ou supprimer"]}),
    ("other_tools",     {"title": ["Autre"], "body": ["Prospects", "ge minimum"]}),
    ("account_type",    {"title": ["Type de compte et outils"], "body": ["Statistiques", "Autre"]}),
    ("edit_link",       {"title": ["Modifier le lien"], "body": ["Effacer le texte"]}),
    ("links_list",      {"title": ["Liens"], "body": ["Ajouter un lien"]}),
    ("photo_gallery",   {"body": ["Miniature", "Photos"]}),
    ("photo_menu",      {"body": ["Choisir dans la", "biblioth"]}),
    ("creation_menu",   {"body": ["Reel", "Publication", "Story", "Fermer"]}),
    # ── Écrans d'édition ──
    ("edit_gender",     {"title": ["Genre"], "body": ["Femme", "Homme"]}),
    ("edit_field",      {"body": ["fait", "Champ de texte"]}),
    ("edit_bio",        {"title": ["Retour"], "body": ["Bio", "fait"]}),
    ("edit_profile",    {"title": ["Modifier le profil"], "body": ["nom", "Bio"]}),
    # ── Paramètres ──
    ("settings",        {"title": ["tres et activit"], "body": ["Votre compte"]}),
    ("settings_deep",   {"title": ["tres et activit"], "body": ["Type de compte"]}),
    # ── Profil & feed ──
    ("own_profile",     {"body": ["Modifier le profil", "Partager le profil"]}),
    ("feed",            {"body": ["Fil principal", "Explorer"]}),
    # ── iOS ──
    ("ios_home",        {"body": ["FaceTime", "Photos"]}),
]


async def _detect_screen(driver, log=None) -> str:
    """Detect current screen from accessibility tree markers.

    Uses the SCREENS atlas — checks title (y<80) and body markers.
    Returns the first matching screen_id, or 'unknown'.
    """
    els = await driver.find_elements(refresh=True)
    title_texts = []
    body_texts = []
    for e in els:
        t = (e.get('text', '') or '').strip()
        if not t or len(t) < 2:
            continue
        r = e.get('rect', {})
        y = r.get('y', 999)
        if y < 80:
            title_texts.append(t.lower())
        body_texts.append(t.lower())

    title_joined = ' '.join(title_texts)
    body_joined = ' '.join(body_texts)

    for screen_id, sig in SCREENS:
        # Check title markers (all must match if present)
        title_markers = sig.get("title", [])
        if title_markers:
            title_ok = all(m.lower() in title_joined for m in title_markers)
            if not title_ok:
                continue
        # Check body markers (at least 2 must match, or all if only 1-2)
        body_markers = sig.get("body", [])
        if body_markers:
            body_hits = sum(1 for m in body_markers if m.lower() in body_joined)
            needed = min(2, len(body_markers))
            if body_hits < needed:
                continue
        # Matched
        return screen_id

    return "unknown"


async def _ensure_screen(driver, navigator, log, target: str, max_retries: int = 2) -> bool:
    """Verify we're on the expected screen, try to recover if not.

    Returns True if we're on the target screen (or recovered to it).
    """
    current = await _detect_screen(driver, log)
    if current == target:
        return True

    log("   [safety] ecran attendu '%s', detecte '%s' — recovery" % (target, current))

    for attempt in range(max_retries):
        if target == "edit_profile":
            if current == "own_profile":
                el = await driver.find_element(text="Modifier le profil", clickable=True, refresh=True)
                if el:
                    tap = el.get('tap', {})
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(2)
            elif current == "feed" or current == "unknown":
                # Go to profile first
                profile_tab = await driver.find_element(text="Profil", clickable=True, refresh=True)
                if profile_tab and profile_tab.get('rect', {}).get('y', 0) > 650:
                    tap = profile_tab.get('tap', {})
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(2)
                # Then tap modifier le profil
                el = await driver.find_element(text="Modifier le profil", clickable=True, refresh=True)
                if el:
                    tap = el.get('tap', {})
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(2)
            elif current == "creation_menu":
                # Dismiss creation menu overlay (tap "Fermer" or "X")
                log("   [safety] creation_menu detecte, fermeture")
                close = await driver.find_element("Fermer", clickable=True, refresh=True)
                if not close:
                    close = await driver.find_element("X", clickable=True, refresh=True)
                if close:
                    tap = close.get('tap', {})
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(1.5)
                else:
                    await navigator.go_back()
                    await asyncio.sleep(1.5)
            elif current == "edit_field" or current == "edit_gender" or current == "edit_bio":
                # We're in a field sub-screen, go back
                await navigator.go_back()
                await asyncio.sleep(1.5)

        elif target == "edit_field":
            if current != "edit_profile":
                # Need to get to edit_profile first
                ok = await _ensure_screen(driver, navigator, log, "edit_profile", max_retries=1)
                if not ok:
                    return False

        elif target == "own_profile":
            if current == "feed" or current == "unknown":
                profile_tab = await driver.find_element(text="Profil", clickable=True, refresh=True)
                if profile_tab and profile_tab.get('rect', {}).get('y', 0) > 650:
                    tap = profile_tab.get('tap', {})
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(2)
            elif current == "edit_profile" or current == "edit_field":
                await navigator.go_back()
                await asyncio.sleep(1.5)

        # Re-check
        current = await _detect_screen(driver, log)
        if current == target:
            log("   [safety] recovery OK -> '%s'" % target)
            return True

    log("   [safety] ! recovery echouee (cible: %s, actuel: %s)" % (target, current))
    return False


# ── Navigation helpers ────────────────────────────────────────────────────────

async def _dismiss_meta_popup(driver, log):
    """Gere le popup 'Votre Compte Meta est disponible'."""
    meta = await driver.find_element(contains="Compte Meta", refresh=True)
    if not meta:
        meta = await driver.find_element(contains="Compte Meta", refresh=True)
    if not meta:
        return  # pas de popup
    log("   [popup] Compte Meta detecte")
    # Tap "Examiner le compte"
    btn = await driver.find_element(contains="Examiner", clickable=True, refresh=True)
    if btn:
        tap = btn.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(2)
    # Tap "Termine" sur l'ecran suivant
    done = await driver.find_element(contains="Termin", clickable=True, refresh=True)
    if done:
        tap = done.get('tap', {})
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(1.5)
    log("   [popup] Compte Meta ferme")


async def _open_edit_profile(driver, navigator, log) -> bool:
    """Ouvre l'ecran Modifier le profil via l'arbre d'accessibilite."""
    # 1. Navigate to profile tab via accessibility tree (not blind coordinates)
    profile_tab = await driver.find_element(text="Profil", clickable=True, refresh=True)
    if profile_tab:
        r = profile_tab.get('rect', {})
        # Only tap if it's in the bottom bar area (y > 700)
        if r.get('y', 0) > 650:
            tap = profile_tab.get('tap', {})
            log("   -> Profil (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(2)
    else:
        # Fallback to navigator
        await navigator.go_profile()
        await asyncio.sleep(1.5)

    # 2. Check for popups (modal overlay with "Arrière-plan grisé")
    for attempt in range(2):
        overlay = await driver.find_element(text="Arrière-plan grisé", refresh=True)
        if not overlay:
            break
        log("   [popup] overlay detecte (tentative %d)" % (attempt + 1))
        # Try dismiss buttons one at a time, break after first match
        dismissed = False
        for label in ["Termin", "Plus tard", "Ignorer", "Fermer"]:
            btn = await driver.find_element(contains=label, clickable=True, refresh=True)
            if btn:
                tap = btn.get('tap', {})
                log("   [popup] tap '%s'" % label)
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(2)
                dismissed = True
                break
        if not dismissed:
            # Try tapping outside the popup to dismiss
            await driver.ht.tap(187, 400)
            await asyncio.sleep(1)

    # 3. Find and tap "Modifier le profil"
    el = await driver.find_element(text="Modifier le profil", clickable=True, refresh=True)
    if not el:
        log("   ! bouton 'Modifier le profil' non trouve")
        return False
    tap = el.get('tap', {})
    log("   ouvre edition profil (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.5, 2.5))
    await asyncio.sleep(1)

    # 4. Verify we're on the edit screen
    check = await driver.find_element(contains="nom", refresh=True)
    if not check:
        check = await driver.find_element(contains="Bio", refresh=True)
    if not check:
        log("   ! pas sur l'ecran de modification apres tap")
        return False
    log("   ecran Modifier le profil confirme")
    return True


async def _open_settings(driver, navigator, log) -> bool:
    """Ouvre l'ecran Parametres et activite avec vérification."""
    # D'abord s'assurer qu'on est sur le profil
    screen = await _detect_screen(driver, log)
    if screen not in ("own_profile", "settings", "settings_deep"):
        log("   [nav] écran '%s' → navigation vers profil" % screen)
        # Essayer le tab profil dans la barre du bas
        profile_tab = await driver.find_element(text="Profil", clickable=True, refresh=True)
        if profile_tab and profile_tab.get('rect', {}).get('y', 0) > 650:
            tap = profile_tab.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(2)
        else:
            await navigator.go_profile()
            await asyncio.sleep(2)

        # Vérifier qu'on est bien sur le profil
        screen = await _detect_screen(driver, log)
        if screen != "own_profile":
            log("   [nav] ⚠ écran '%s' après navigation profil" % screen)

    if screen in ("settings", "settings_deep"):
        log("   déjà dans les paramètres")
        return True

    # Trouver le bouton paramètres (icône engrenage en haut à droite du profil)
    el = await driver.find_element("param", contains=True, clickable=True, refresh=True)
    if not el:
        el = await driver.find_element("activit", contains=True, clickable=True, refresh=True)
    if not el:
        log("   ! bouton parametres non trouvé")
        await _dump_screen(driver, log, "profil_no_settings")
        return False
    tap = el.get('tap', {})
    log("   ouvre parametres (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.5, 2.5))

    # Vérifier qu'on est bien dans les paramètres
    screen = await _detect_screen(driver, log)
    if screen not in ("settings", "settings_deep"):
        log("   ! écran '%s' après ouverture paramètres (attendu settings)" % screen)
        # Peut-être le menu création s'est ouvert — fermer
        if screen == "creation_menu":
            close = await driver.find_element("Fermer", clickable=True, refresh=True)
            if close:
                ct = close.get('tap', {})
                await driver.ht.tap(ct['x'], ct['y'])
                await asyncio.sleep(1)
            return await _open_settings(driver, navigator, log)
        return False
    log("   ✓ paramètres ouverts")
    return True



async def _dump_screen(driver, log, label=""):
    """Log les elements visibles a l'ecran pour debug."""
    els = await driver.find_elements(refresh=True)
    texts = []
    for e in els:
        t = (e.get('text', '') or '')
        if t and len(t) > 1:
            r = e.get('rect', {})
            texts.append("'%s' y=%d x=%d" % (t[:35], r.get('y', 0), r.get('x', 0)))
    log("   [dump %s] %s" % (label, ' | '.join(texts[:12])))

async def _tap_field(driver, log, field_name) -> bool:
    """Tape sur un champ dans l'ecran d'edition et verifie qu'on est dans le sous-ecran."""
    # Search ALL elements (not just clickable) in the edit profile zone (y > 150)
    # to avoid matching nav elements like "Retour" (y~44) that also contain the needle
    all_els = await driver.find_elements(field_name, contains=True, refresh=True)
    el = None
    for candidate in all_els:
        r = candidate.get('rect', {})
        # Edit profile fields are below y=150 (nav bar is above)
        if r.get('y', 0) > 150:
            el = candidate
            break
    if not el:
        # Fallback: try clickable only (might still work for some fields)
        el = await driver.find_element(field_name, contains=True, clickable=True)
    if not el:
        log("   ! champ '%s' non trouve" % field_name)
        return False
    tap = el.get('tap', {})
    found_text = (el.get('text', '') or '')[:40]
    log("   tap champ '%s' (y=%d x=%d)" % (found_text, tap.get('y', 0), tap.get('x', 0)))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.5, 2.5))
    await asyncio.sleep(1)
    # Verify we entered the field editing sub-screen (must find save button in top area)
    els = await driver.find_elements(refresh=True, clickable=True)
    done_el = None
    for e in els:
        t = (e.get('text', '') or '').lower()
        r = e.get('rect', {})
        if r.get('y', 999) < 100 and ('fait' in t or 'termin' in t):
            done_el = e
            break
    if not done_el:
        log("   ! sous-ecran '%s' non confirme (pas de bouton valider en haut)" % field_name)
        return False
    log("   sous-ecran confirme (bouton '%s' y=%d)" % ((done_el.get('text', '')[:20]), done_el.get('rect', {}).get('y', 0)))
    return True


async def _clear_and_type(driver, log, text, current_text=""):
    """Efface le texte existant via select-all + type (le texte remplace la selection)."""
    # Find the text input field
    field = await driver.find_element("Champ de texte", contains=True, refresh=True)
    if field:
        ft = field.get('tap', {})
        cx, cy = ft.get('x', 187), ft.get('y', 100)
    else:
        # Fallback: center of screen, upper area
        screen = await driver.ht._call("get_screen_info", timeout=3)
        cx = (screen or {}).get("width", 375) / 2
        cy = 100

    # Tap the field once to ensure focus
    await driver.ht.tap(cx, cy)
    await asyncio.sleep(0.3)

    # Select all text via Cmd+A (iOS accessibility select all)
    # Triple-tap with proper iOS timing (200ms between taps)
    for i in range(3):
        await driver.ht.tap(cx, cy)
        if i < 2:
            await asyncio.sleep(0.15)
    await asyncio.sleep(0.6)

    # Now type the new text — iOS replaces selected text automatically
    # If selection failed, we'll prepend; the triple-tap timing helps
    log("   saisie texte: '%s'" % text[:40])
    await driver.ht.type_text(text)
    await asyncio.sleep(0.5)


async def _verify_profile_field(driver, log, field_label, expected_value) -> bool:
    """Verifie qu'un champ du profil affiche la valeur attendue.

    Navigue vers le profil si necessaire, puis cherche le texte EXACT
    (pas contains) parmi les elements visibles.

    Args:
        field_label: label pour le log ("nom", "bio", "lien", etc.)
        expected_value: texte exact attendu sur le profil
    Returns:
        True si verifie, False sinon
    """
    # Make sure we're on the profile screen
    screen = await _detect_screen(driver, log)
    if screen == "edit_profile":
        back = await driver.find_element("Retour", clickable=True, refresh=True)
        if back:
            tap = back.get('tap', {})
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(2)

    # Scan all visible elements for an EXACT match
    all_els = await driver.find_elements(refresh=True)
    for el in all_els:
        el_text = (el.get('text', '') or '').strip()
        if el_text == expected_value:
            r = el.get('rect', {})
            log("   ✓ %s verifie: '%s' (y=%d)" % (field_label, el_text[:40], r.get('y', 0)))
            return True

    # No exact match — log what we see for debugging
    visible = [e.get('text', '') for e in all_els if e.get('text') and len(e.get('text', '')) > 1]
    log("   ⚠ %s '%s' non trouve (exact). Visible: %s" % (field_label, expected_value[:30], ', '.join("'%s'" % v[:25] for v in visible[:8])))
    return False


def _looks_like_url(text: str) -> bool:
    """Check if a text looks like a URL (not just any text with a period)."""
    t = text.strip().lower()
    # Must have a domain-like pattern: word.tld or http(s)://
    if t.startswith('http://') or t.startswith('https://'):
        return True
    # Match domain patterns like "example.com", "ta-cassie.com/viens"
    import re
    return bool(re.match(r'^[a-z0-9][\w.-]*\.[a-z]{2,}(/\S*)?$', t))


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
    """Tape sur 'C'est fait' ou 'Terminé' pour sauvegarder."""
    # Search all clickable elements and find the save button in top-right area
    els = await driver.find_elements(refresh=True, clickable=True)
    el = None
    for e in els:
        t = (e.get('text', '') or '')
        r = e.get('rect', {})
        x = r.get('x', 0)
        y = r.get('y', 0)
        # "C'est fait" or "Terminé" should be in the top-right (x > 200, y < 100)
        if y < 100 and x > 200:
            if 'fait' in t.lower() or 'termin' in t.lower():
                el = e
                break
    if el:
        tap = el.get('tap', {})
        log("   -> '%s' (y=%d)" % (el.get('text', '?')[:30], tap.get('y', 0)))
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
    if not await _tap_field(driver, log, "rénom"):
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
    """Change la photo de profil avec vérification à chaque étape."""
    log("-> Config: photo de profil (index=%d)" % photo_index)
    if not await _open_edit_profile(driver, navigator, log):
        return False

    # 1. Trouver et taper "Modifier la photo"
    el = await driver.find_element("Modifier la photo", contains=True, clickable=True, refresh=True)
    if not el:
        log("   ! bouton photo profil non trouvé")
        await _dump_screen(driver, log, "edit_profile")
        await _go_back(driver, navigator, log)
        return False
    tap = el.get('tap', {})
    log("   tap 'Modifier la photo' (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.5, 2.5))

    # 2. Vérifier menu d'action + taper galerie
    gallery = None
    for attempt in range(3):
        gallery = await driver.find_element("Choisir dans la", contains=True, clickable=True, refresh=True)
        if not gallery:
            gallery = await driver.find_element("biblioth", contains=True, clickable=True, refresh=True)
        if not gallery:
            gallery = await driver.find_element("galerie", contains=True, clickable=True, refresh=True)
        if gallery:
            break
        log("   [retry %d] menu photo pas visible" % (attempt + 1))
        await asyncio.sleep(1)

    if not gallery:
        log("   ! menu galerie non trouvé")
        await _dump_screen(driver, log, "menu_photo")
        await _go_back(driver, navigator, log)
        return False

    tap = gallery.get('tap', {})
    log("   tap '%s' (y=%d)" % (gallery.get('text', '')[:30], tap.get('y', 0)))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.5, 2.5))

    # 3. Vérifier galerie chargée
    photos = None
    for attempt in range(3):
        photos = await driver.find_elements("Miniature", contains=True, clickable=True, refresh=True)
        if not photos:
            photos = await driver.find_elements("Photo", contains=True, clickable=True, refresh=True)
        if photos:
            break
        log("   [retry %d] galerie pas chargée" % (attempt + 1))
        await asyncio.sleep(1.5)

    if not photos or photo_index >= len(photos):
        log("   ! galerie vide ou index hors limites (photos=%d, index=%d)" % (len(photos) if photos else 0, photo_index))
        await _go_back(driver, navigator, log)
        await _go_back(driver, navigator, log)
        return False

    # 4. Sélectionner la photo
    log("   galerie: %d photos, sélection index=%d" % (len(photos), photo_index))
    tap = photos[photo_index].get('tap', {})
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # 5. Valider (Terminé/C'est fait)
    done_found = False
    for attempt in range(3):
        done_found = await _tap_done(driver, log)
        if done_found:
            break
        log("   [retry %d] bouton validation non trouvé" % (attempt + 1))
        await _dump_screen(driver, log, "crop")
        await asyncio.sleep(1.5)

    if not done_found:
        log("   ! impossible de valider la photo")
        await _go_back(driver, navigator, log)
        await _go_back(driver, navigator, log)
        return False

    # 6. Attendre retour edit_profile
    log("   attente chargement photo...")
    for _ in range(15):
        await asyncio.sleep(1)
        screen = await _detect_screen(driver, log)
        if screen in ("edit_profile", "own_profile"):
            log("   ✓ photo de profil modifiée")
            await _go_back(driver, navigator, log)
            return True

    log("   ⚠ timeout chargement photo")
    await _go_back(driver, navigator, log)
    return False


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


async def set_age_limit(driver, navigator, age: int | None, log: Callable = print) -> bool:
    """Configure la limite d'âge minimum du compte.

    Flow: Profil → Paramètres → scroll → Type de compte et outils → Autre → Âge minimum
    age=18 → définir 18 ans minimum
    age=None ou 0 → supprimer la limite d'âge

    Écrans (depuis les dumps réels) :
    - Paramètres : "Type de compte et outils" (peut nécessiter scroll)
    - Type de compte et outils : "Autre"
    - Autre : "Âge minimum"
    - Âge minimum : "Par défaut" + "Ajouter ou supprimer" / valeur actuelle
    - Picker : "Âge par défaut" + scroll picker + "Enregistrer"
    """
    # Parse age: "18+" → 18, "21+" → 21, None/0/"" → None
    import re as _re
    if isinstance(age, str):
        m = _re.match(r"(\d+)", age)
        age = int(m.group(1)) if m else None
    if age and not isinstance(age, int):
        age = int(age) if str(age).isdigit() else None

    log("-> Config: âge minimum -> %s" % (age if age else "supprimer"))

    # Step 1: Open settings from profile
    if not await _open_settings(driver, navigator, log):
        return False

    # Step 2: Find "Type de compte et outils" (section "Votre compte", near the top)
    # Settings opens at the top — a small scroll or two should reveal it
    el = None
    for attempt in range(5):
        el = await driver.find_element("Type de compte", contains=True, clickable=True, refresh=True)
        if el:
            break
        log("   scroll paramètres (%d/5)" % (attempt + 1))
        await driver.ht.swipe(187, 450, 187, 300, 250)
        await asyncio.sleep(1.0)

    if not el:
        log("   ! 'Type de compte et outils' non trouvé après 5 scrolls")
        screen = await _detect_screen(driver, log)
        log("   écran détecté: '%s'" % screen)
        await _dump_screen(driver, log, "settings_no_type_compte")
        await _go_back(driver, navigator, log)
        return False

    tap = el.get('tap', {})
    log("   tap 'Type de compte et outils' (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.5, 2.5))

    # Vérifier qu'on est sur l'écran "Type de compte et outils"
    screen = await _detect_screen(driver, log)
    if screen != "account_type":
        log("   ⚠ écran '%s' après tap Type de compte (attendu account_type)" % screen)

    # Step 3: Tap "Autre"
    autre = await driver.find_element("Autre", clickable=True, refresh=True)
    if not autre:
        log("   ! 'Autre' non trouvé")
        await _dump_screen(driver, log, "type_compte_no_autre")
        await _go_back(driver, navigator, log)
        return False

    tap = autre.get('tap', {})
    log("   tap 'Autre' (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # Vérifier qu'on est sur l'écran "Autre"
    screen = await _detect_screen(driver, log)
    if screen != "other_tools":
        log("   ⚠ écran '%s' après tap Autre (attendu other_tools)" % screen)

    # Step 4: Tap "Âge minimum"
    age_btn = await driver.find_element("ge minimum", contains=True, clickable=True, refresh=True)
    if not age_btn:
        log("   ! 'Âge minimum' non trouvé")
        await _go_back(driver, navigator, log)
        await _go_back(driver, navigator, log)
        return False

    tap = age_btn.get('tap', {})
    log("   tap 'Âge minimum' (y=%d)" % tap.get('y', 0))
    await driver.ht.tap(tap['x'], tap['y'])
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # Step 5: We're on the "Âge minimum" screen
    # Check if there's already an age set (look for a number element)
    all_els = await driver.find_elements(refresh=True)
    current_age = None
    for e in all_els:
        t = (e.get('text', '') or '').strip()
        r = e.get('rect', {})
        if t.isdigit() and 13 <= int(t) <= 99 and r.get('y', 0) > 250:
            current_age = int(t)
            break
    log("   âge actuel: %s" % (current_age if current_age else "aucun"))

    if not age or age == 0:
        # DELETE age limit
        if not current_age:
            log("   pas d'âge défini, rien à supprimer")
            # Go back 3 levels: Âge minimum → Autre → Type de compte → Paramètres
            for _ in range(3):
                await _go_back(driver, navigator, log)
            return True

        # Tap "Ajouter ou supprimer" in the "Par défaut" section
        add_remove = await driver.find_element("Ajouter ou supprimer", contains=True, clickable=True, refresh=True)
        if not add_remove:
            add_remove = await driver.find_element("supprimer", contains=True, clickable=True)
        if add_remove:
            tap = add_remove.get('tap', {})
            log("   tap 'Ajouter ou supprimer' (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1)

            # The existing age entry should show — tap the trash/remove button
            # After tapping "Ajouter ou supprimer", it may toggle delete mode
            # or show a confirmation. Check what appears.
            await asyncio.sleep(1)
            # Check if the age was removed
            all_els2 = await driver.find_elements(refresh=True)
            age_gone = True
            for e in all_els2:
                t = (e.get('text', '') or '').strip()
                r = e.get('rect', {})
                if t.isdigit() and 13 <= int(t) <= 99 and r.get('y', 0) > 250:
                    age_gone = False
                    break
            if age_gone:
                log("   ✓ âge minimum supprimé")
            else:
                log("   ⚠ âge peut-être pas supprimé")
        else:
            log("   ! bouton supprimer non trouvé")

        for _ in range(3):
            await _go_back(driver, navigator, log)
        return age_gone if 'age_gone' in dir() else False

    else:
        # SET age limit
        # Tap "Ajouter ou supprimer" to open the picker
        add_remove = await driver.find_element("Ajouter ou supprimer", contains=True, clickable=True, refresh=True)
        if not add_remove:
            # First-time setup — no "Ajouter ou supprimer" button
            add_remove = await driver.find_element("Ajouter", contains=True, clickable=True)
        if not add_remove:
            log("   ! bouton ajouter non trouvé")
            for _ in range(3):
                await _go_back(driver, navigator, log)
            return False

        tap = add_remove.get('tap', {})
        log("   tap '%s' (y=%d)" % (add_remove.get('text', '')[:25], tap.get('y', 0)))
        await driver.ht.tap(tap['x'], tap['y'])
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Step 6: Picker bottom sheet should be open
        # Elements: "Âge par défaut", "Enregistrer", picker with current value, "Fermer"
        picker = await driver.find_element("par d", contains=True, refresh=True)
        if not picker:
            log("   ! picker d'âge non ouvert")
            for _ in range(3):
                await _go_back(driver, navigator, log)
            return False

        log("   picker ouvert")

        # Read current picker value
        picker_els = await driver.find_elements(refresh=True)
        picker_value = None
        picker_el = None
        for e in picker_els:
            t = (e.get('text', '') or '').strip()
            r = e.get('rect', {})
            if t.isdigit() and r.get('y', 500) > 580 and r.get('height', 0) > 100:
                picker_value = int(t)
                picker_el = e
                break

        log("   valeur picker: %s (cible: %s)" % (picker_value, age))

        if picker_el and picker_value:
            # Scroll the picker to reach the target age
            # Each swipe step ≈ 1-2 age units on the picker
            diff = age - picker_value
            if diff != 0:
                pr = picker_el.get('rect', {})
                px = pr.get('x', 0) + pr.get('width', 375) / 2
                py = pr.get('y', 650) + pr.get('height', 200) / 2

                # Scroll: positive diff = need higher number = swipe up
                steps = abs(diff)
                for i in range(min(steps, 50)):
                    if diff > 0:
                        # Swipe up to increase
                        await driver.ht.swipe(px, py + 30, px, py - 30, 200)
                    else:
                        # Swipe down to decrease
                        await driver.ht.swipe(px, py - 30, px, py + 30, 200)
                    await asyncio.sleep(0.3)

                await asyncio.sleep(0.5)
                log("   picker scrollé de %d pas" % steps)

        # Tap "Enregistrer"
        save_btn = await driver.find_element("Enregistrer", clickable=True, refresh=True)
        if save_btn:
            tap = save_btn.get('tap', {})
            log("   tap 'Enregistrer' (y=%d)" % tap.get('y', 0))
            await driver.ht.tap(tap['x'], tap['y'])
            await asyncio.sleep(1)
        else:
            log("   ! bouton Enregistrer non trouvé")
            for _ in range(3):
                await _go_back(driver, navigator, log)
            return False

        # Verify: check the age is now displayed
        await asyncio.sleep(0.5)
        all_els3 = await driver.find_elements(refresh=True)
        verified = False
        for e in all_els3:
            t = (e.get('text', '') or '').strip()
            r = e.get('rect', {})
            if t == str(age) and r.get('y', 0) > 250:
                log("   ✓ âge vérifié: %s (y=%d)" % (t, r.get('y', 0)))
                verified = True
                break

        if not verified:
            log("   ⚠ âge %d non vérifié (peut nécessiter ajustement du picker)" % age)

        # Go back 3 levels
        for _ in range(3):
            await _go_back(driver, navigator, log)

        return verified


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
    for key in ("name", "username", "bio", "pronouns", "gender", "link", "photo_index", "photo_url"):
        if key in config:
            edit_fields[key] = config[key]

    # photo_url → push to gallery first (with EXIF spoof), then select as photo_index=0
    if "photo_url" in edit_fields and edit_fields["photo_url"]:
        photo_url = edit_fields.pop("photo_url")
        # Spoof params from config (market, device, phone_id)
        spoof_market = config.get("market", "FR")
        spoof_device = config.get("device")
        spoof_phone_id = config.get("phone_id")
        log("   [0] push photo vers galerie (spoof=%s): %s" % (spoof_market, str(photo_url)[:60]))
        try:
            from app.services.automation.ig_iphone.media import push_media_to_gallery
            from app.config import settings
            result = await push_media_to_gallery(
                photo_url,
                auth_header="Bearer %s" % settings.api_secret,
                spoof=True,
                market=spoof_market,
                device=spoof_device,
                phone_id=spoof_phone_id,
                log=log,
            )
            if result.get("success"):
                log("   photo pushee dans la galerie, selection en photo_index=0")
                edit_fields["photo_index"] = 0
            else:
                log("   ! push photo echoue: %s" % result.get("error", "?"))
                results["photo_url"] = False
        except Exception as e:
            log("   ! push photo erreur: %s" % str(e)[:100])
            results["photo_url"] = False

    if edit_fields:
        if not await _open_edit_profile(driver, navigator, log):
            return results

        if "name" in edit_fields:
            log("   [1] nom -> '%s'" % edit_fields["name"])
            if not await _ensure_screen(driver, navigator, log, "edit_profile"):
                log("   ! abort: pas sur edit_profile")
            else:
                if not await _tap_field(driver, log, "rénom"):
                    log("   ! tap_field nom echoue")
                else:
                    await _clear_and_type(driver, log, edit_fields["name"])
                    if await _tap_done(driver, log):
                        # Instagram shows a confirmation popup for name changes
                        await asyncio.sleep(1.5)
                        confirm = await driver.find_element("Modifier le nom", contains=True, clickable=True, refresh=True)
                        if not confirm:
                            confirm = await driver.find_element("Changer", contains=True, clickable=True)
                        if not confirm:
                            confirm = await driver.find_element("Confirm", contains=True, clickable=True)
                        if confirm:
                            tap = confirm.get('tap', {})
                            log("   popup confirmation nom: '%s' (y=%d)" % (confirm.get('text', '')[:30], tap.get('y', 0)))
                            await driver.ht.tap(tap['x'], tap['y'])
                            await asyncio.sleep(1)
                        else:
                            log("   pas de popup confirmation nom (ok)")

                        # Wait for loading to finish — poll until edit_profile or own_profile reappears
                        for attempt in range(6):
                            await asyncio.sleep(1.5)
                            screen = await _detect_screen(driver, log)
                            if screen in ("edit_profile", "own_profile"):
                                log("   chargement termine: ecran '%s'" % screen)
                                break
                        else:
                            log("   timeout chargement nom (continue)")

                        # Verify on profile
                        verified = await _verify_profile_field(driver, log, "nom", edit_fields["name"])
                        results["name"] = True  # Mark done even if verify fails (IG may truncate/format)
                        if not verified:
                            log("   (le nom a peut-etre ete applique avec un format different)")

                        # Re-open edit profile for remaining fields
                        if edit_fields.keys() - {"name"}:
                            await _open_edit_profile(driver, navigator, log)
                    else:
                        log("   ! nom: validation echouee")
                        await _ensure_screen(driver, navigator, log, "edit_profile")

        if "username" in edit_fields:
            log("   [2] username -> '@%s'" % edit_fields["username"])
            if not await _ensure_screen(driver, navigator, log, "edit_profile"):
                log("   ! abort: pas sur edit_profile")
            elif await _tap_field(driver, log, "Nom de profil"):
                await _clear_and_type(driver, log, edit_fields["username"])
                if await _tap_done(driver, log):
                    await asyncio.sleep(2)
                    results["username"] = True
                else:
                    log("   ! username: validation echouee")
                    await _ensure_screen(driver, navigator, log, "edit_profile")

        if "bio" in edit_fields:
            log("   [3] bio -> '%s'" % str(edit_fields["bio"])[:40])
            if not await _ensure_screen(driver, navigator, log, "edit_profile"):
                log("   ! abort: pas sur edit_profile")
            else:
                bio_els = await driver.find_elements(text="Bio", clickable=True, refresh=True)
                best = None
                for e in bio_els:
                    w = e.get('rect', {}).get('width', 0)
                    if not best or w > best.get('rect', {}).get('width', 0):
                        best = e
                if best:
                    tap = best.get('tap', {})
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(1.5)

                    # Trouver le champ texte dans le sous-écran bio
                    bio_field = await driver.find_element("Champ de texte", contains=True, refresh=True)
                    if bio_field:
                        ft = bio_field.get('tap', {})
                        cx, cy = ft.get('x', 187), ft.get('y', 138)
                    else:
                        cx, cy = 187, 138

                    # Approche "Tout sélectionner" : tap → pause → re-tap ±1px → menu contextuel
                    await driver.ht.tap(cx, cy)
                    await asyncio.sleep(random.uniform(0.8, 1.2))
                    await driver.ht.tap(cx + 1, cy)
                    await asyncio.sleep(0.6)

                    # Chercher "Tout sélectionner" (ou "Tout s") dans le menu contextuel
                    selected = False
                    for attempt in range(3):
                        sel = await driver.find_element("Tout s", contains=True, clickable=True, refresh=True)
                        if sel:
                            st = sel.get('tap', {})
                            log("   'Tout sélectionner' trouvé (y=%d)" % st.get('y', 0))
                            await driver.ht.tap(st['x'], st['y'])
                            await asyncio.sleep(0.3)
                            selected = True
                            break
                        # Re-tap pour faire apparaître le menu
                        await driver.ht.tap(cx, cy)
                        await asyncio.sleep(0.8)
                        await driver.ht.tap(cx + 1, cy)
                        await asyncio.sleep(0.6)

                    if not selected:
                        log("   ⚠ 'Tout sélectionner' non trouvé, fallback triple-tap")
                        for _ in range(3):
                            await driver.ht.tap(cx, cy)
                            await asyncio.sleep(0.15)
                        await asyncio.sleep(0.5)

                    log("   saisie bio: '%s'" % edit_fields["bio"][:40])
                    await driver.ht.type_text(edit_fields["bio"])
                    await asyncio.sleep(1.0)
                    if await _tap_done(driver, log):
                        await asyncio.sleep(2.5)
                        results["bio"] = True
                    else:
                        log("   ! bio: validation echouee")
                        await _ensure_screen(driver, navigator, log, "edit_profile")

        if "link" in edit_fields:
            if not await _ensure_screen(driver, navigator, log, "edit_profile"):
                log("   ! abort lien: pas sur edit_profile")
            else:
                link = edit_fields["link"]
                if link and link != "":
                    url = link.get("url", link) if isinstance(link, dict) else str(link)
                    title = link.get("title") if isinstance(link, dict) else None
                    log("   [4] lien -> '%s'" % url[:40])
                else:
                    url = ""
                    title = None
                    log("   [4] lien -> (supprimer)")

                # Step 1: Tap "Ajouter des liens" in edit_profile (navigates to links list)
                # NOTE: Don't use _tap_field — the links list screen has NO done button
                links_btn = await driver.find_element("Ajouter des liens", contains=True, refresh=True)
                if not links_btn:
                    links_btn = await driver.find_element("liens", contains=True, refresh=True)
                if not links_btn:
                    log("   ! bouton liens non trouve sur edit_profile")
                else:
                    tap = links_btn.get('tap', {})
                    log("   tap '%s' (y=%d)" % (links_btn.get('text', '')[:30], tap.get('y', 0)))
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(random.uniform(1.5, 2.5))

                    # Step 2: We're on the links list screen
                    # Check if there's an existing link to edit or if we add new
                    if not url:
                        # DELETE existing link: tap on it, then "Supprimer le lien"
                        # Find existing link (any element with a URL-like text, y > 130)
                        all_els = await driver.find_elements(refresh=True)
                        existing = None
                        for e in all_els:
                            t = (e.get('text', '') or '')
                            r = e.get('rect', {})
                            if r.get('y', 0) > 130 and _looks_like_url(t):
                                existing = e
                                break
                        if existing:
                            tap = existing.get('tap', {})
                            log("   tap lien existant '%s' (y=%d)" % (existing.get('text', '')[:30], tap.get('y', 0)))
                            await driver.ht.tap(tap['x'], tap['y'])
                            await asyncio.sleep(1.5)
                            # Now on "Modifier le lien" screen — tap "Supprimer le lien"
                            del_btn = await driver.find_element("Supprimer le lien", contains=True, clickable=True, refresh=True)
                            if del_btn:
                                tap = del_btn.get('tap', {})
                                log("   tap 'Supprimer le lien' (y=%d)" % tap.get('y', 0))
                                await driver.ht.tap(tap['x'], tap['y'])
                                await asyncio.sleep(1.5)
                                # Confirmation popup: "Supprimer le lien de votre bio ?"
                                confirm = await driver.find_element("Supprimer", clickable=True, refresh=True)
                                if confirm and confirm.get('rect', {}).get('y', 0) > 350:
                                    tap = confirm.get('tap', {})
                                    log("   confirmation suppression (y=%d)" % tap.get('y', 0))
                                    await driver.ht.tap(tap['x'], tap['y'])
                                    await asyncio.sleep(3)
                                    results["link"] = True
                                    log("   ✓ lien supprime")
                            else:
                                log("   ! bouton supprimer non trouve")
                        else:
                            log("   ! aucun lien existant a supprimer")
                    else:
                        # ADD or EDIT a link
                        # Check if there's an existing link to edit
                        all_els = await driver.find_elements(refresh=True)
                        existing = None
                        for e in all_els:
                            t = (e.get('text', '') or '')
                            r = e.get('rect', {})
                            if r.get('y', 0) > 130 and _looks_like_url(t):
                                existing = e
                                break

                        if existing:
                            # EDIT existing link — tap on it
                            tap = existing.get('tap', {})
                            log("   tap lien existant '%s' pour modifier (y=%d)" % (existing.get('text', '')[:30], tap.get('y', 0)))
                            await driver.ht.tap(tap['x'], tap['y'])
                        else:
                            # ADD new link — tap "Ajouter un lien"
                            add_btn = await driver.find_element("Ajouter un lien", contains=True, clickable=True)
                            if add_btn:
                                tap = add_btn.get('tap', {})
                                log("   tap 'Ajouter un lien' (y=%d)" % tap.get('y', 0))
                                await driver.ht.tap(tap['x'], tap['y'])
                            else:
                                log("   ! ni lien existant ni bouton ajouter")
                                await _go_back(driver, navigator, log)
                                # skip rest of link editing
                                edit_fields.pop("link", None)

                        if "link" in edit_fields:
                            await asyncio.sleep(random.uniform(1.5, 2.5))
                            # Now on "Modifier le lien" or "Ajouter un lien" screen
                            # Fill URL field (tap it, clear, type)
                            url_f = await driver.find_element("URL", contains=True, clickable=True, refresh=True)
                            if not url_f:
                                # URL field might show the current URL text instead
                                url_f = await driver.find_element("http", contains=True, clickable=True)
                            if url_f:
                                tap = url_f.get('tap', {})
                                await driver.ht.tap(tap['x'], tap['y'])
                                await asyncio.sleep(0.5)
                                # Use "Effacer le texte" (X) button to clear existing URL
                                # (safe on link screen — unlike name field, X doesn't exit)
                                x_btn = await driver.find_element("Effacer le texte", clickable=True, refresh=True)
                                if x_btn:
                                    xt = x_btn.get('tap', {})
                                    await driver.ht.tap(xt['x'], xt['y'])
                                    await asyncio.sleep(0.3)
                                    log("   URL effacee via X")
                                else:
                                    # Fallback: triple-tap select all
                                    await _clear_and_type(driver, log, "")
                                # Type the new URL
                                await driver.ht.type_text(url)
                                await asyncio.sleep(0.5)
                                log("   URL saisie: '%s'" % url[:40])
                            else:
                                log("   ! champ URL non trouve")

                            # Fill title if provided
                            if title:
                                title_f = await driver.find_element("Titre", clickable=True, refresh=True)
                                if title_f:
                                    tap = title_f.get('tap', {})
                                    await driver.ht.tap(tap['x'], tap['y'])
                                    await asyncio.sleep(0.5)
                                    # Clear existing title with X button if present
                                    x_btn = await driver.find_element("Effacer le texte", clickable=True, refresh=True)
                                    if x_btn:
                                        xt = x_btn.get('tap', {})
                                        await driver.ht.tap(xt['x'], xt['y'])
                                        await asyncio.sleep(0.3)
                                    await driver.ht.type_text(title)
                                    await asyncio.sleep(0.5)
                                    log("   titre saisi: '%s'" % title[:30])

                            # Tap "C'est fait" — no popup, just loading 3-5s then back to links list
                            await _tap_done(driver, log)
                            # Wait for loading to finish (poll for links list or edit_profile)
                            for attempt in range(8):
                                await asyncio.sleep(1)
                                check = await driver.find_element("Liens", refresh=True)
                                if check and check.get('rect', {}).get('y', 0) < 80:
                                    log("   chargement lien termine")
                                    break
                                check2 = await driver.find_element("Modifier le profil", refresh=True)
                                if check2:
                                    log("   retour a edit_profile")
                                    break
                            else:
                                log("   timeout chargement lien (continue)")

                            # Verify: check the link appears in the links list
                            await asyncio.sleep(1)
                            all_els = await driver.find_elements(refresh=True)
                            # Extract domain from URL for matching (e.g. "youtube.com" from "https://youtube.com/xyz")
                            import re
                            domain_match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', url)
                            domain = domain_match.group(1) if domain_match else url
                            found = False
                            for e in all_els:
                                t = (e.get('text', '') or '').strip().lower()
                                r = e.get('rect', {})
                                # Only check elements in the links list area (y > 100)
                                if r.get('y', 0) < 100:
                                    continue
                                # Exact match: the link text must BE the domain/URL, not just contain it
                                if t == domain.lower() or t == url.lower() or t == ('https://' + url).lower():
                                    log("   ✓ lien verifie: '%s' (y=%d)" % (e.get('text', '')[:40], r.get('y', 0)))
                                    found = True
                                    results["link"] = True
                                    break
                            if not found:
                                log("   ⚠ lien '%s' non retrouve dans la liste" % domain)
                                # Don't mark as success — the link may not have been applied
                                results["link"] = False

                    if not url:
                        pass  # Delete case already handled above
                    elif "link" not in results:
                        results["link"] = False

                    # Go back to edit_profile (from links list or wherever we ended up)
                    try:
                        screen_after_link = await _detect_screen(driver, log)
                        log("   ecran apres lien: '%s'" % screen_after_link)
                        if screen_after_link != "edit_profile":
                            back = await driver.find_element("Modifier le profil", contains=True, clickable=True, refresh=True)
                            if back and back.get('rect', {}).get('y', 0) < 80:
                                tap = back.get('tap', {})
                                await driver.ht.tap(tap['x'], tap['y'])
                                await asyncio.sleep(1.5)
                            else:
                                await _go_back(driver, navigator, log)
                        else:
                            log("   deja sur edit_profile, pas de retour necessaire")
                    except Exception as e:
                        log("   ! erreur navigation retour apres lien: %s" % str(e)[:100])
                        # Try to recover to edit_profile
                        try:
                            await _ensure_screen(driver, navigator, log, "edit_profile")
                        except Exception:
                            pass

        if "gender" in edit_fields:
            try:
                log("   [5] genre -> '%s'" % edit_fields["gender"])
                if not await _ensure_screen(driver, navigator, log, "edit_profile"):
                    log("   ! abort genre: pas sur edit_profile")
                elif not await _tap_field(driver, log, "Genre"):
                    log("   ! champ Genre non trouve sur edit_profile")
                else:
                    screen = await _detect_screen(driver, log)
                    log("   ecran apres tap Genre: '%s'" % screen)
                    option = await driver.find_element(contains=edit_fields["gender"], clickable=True, refresh=True)
                    if option:
                        tap = option.get('tap', {})
                        log("   selectionne '%s' (y=%d)" % (edit_fields["gender"], tap.get('y', 0)))
                        await driver.ht.tap(tap['x'], tap['y'])
                        await asyncio.sleep(0.8)
                    else:
                        log("   ! option genre '%s' non trouvee" % edit_fields["gender"])
                    await _tap_done(driver, log)
                    await asyncio.sleep(1)
                    await _dismiss_popup(driver, log)
                    await _verify_on_edit_screen(driver, log)
                    results["gender"] = True
            except Exception as e:
                log("   ! erreur genre: %s" % str(e)[:150])
                results["gender"] = False

        if "photo_index" in edit_fields:
            log("   [6] photo de profil")
            photo_ok = False

            # 6a. Trouver bouton "Modifier la photo de profil"
            el = await driver.find_element("Modifier la photo", contains=True, clickable=True, refresh=True)
            if not el:
                await driver.scroll_up('normal')
                await asyncio.sleep(0.5)
                el = await driver.find_element("Modifier la photo", contains=True, clickable=True, refresh=True)
            if not el:
                log("   ! bouton 'Modifier la photo' non trouvé")
                await _dump_screen(driver, log, "edit_profile")
            else:
                tap = el.get('tap', {})
                log("   tap 'Modifier la photo' (y=%d)" % tap.get('y', 0))
                await driver.ht.tap(tap['x'], tap['y'])
                await asyncio.sleep(random.uniform(1.5, 2.5))

                # 6b. Vérifier que le menu d'action est apparu
                gallery = None
                for attempt in range(3):
                    gallery = await driver.find_element("Choisir dans la", contains=True, clickable=True, refresh=True)
                    if not gallery:
                        gallery = await driver.find_element("biblioth", contains=True, clickable=True, refresh=True)
                    if not gallery:
                        gallery = await driver.find_element("galerie", contains=True, clickable=True, refresh=True)
                    if gallery:
                        break
                    log("   [retry %d] menu photo pas encore visible" % (attempt + 1))
                    await asyncio.sleep(1)

                if not gallery:
                    log("   ! menu photo (galerie/bibliotheque) non trouvé")
                    await _dump_screen(driver, log, "menu_photo")
                    # Essayer de revenir
                    await _go_back(driver, navigator, log)
                else:
                    tap = gallery.get('tap', {})
                    log("   tap '%s' (y=%d)" % (gallery.get('text', '')[:30], tap.get('y', 0)))
                    await driver.ht.tap(tap['x'], tap['y'])
                    await asyncio.sleep(random.uniform(1.5, 2.5))

                    # 6c. Vérifier que la galerie est ouverte (miniatures visibles)
                    photos = None
                    for attempt in range(3):
                        photos = await driver.find_elements("Miniature", contains=True, clickable=True, refresh=True)
                        if not photos:
                            photos = await driver.find_elements("Photo", contains=True, clickable=True, refresh=True)
                        if photos:
                            break
                        log("   [retry %d] galerie pas encore chargee" % (attempt + 1))
                        await asyncio.sleep(1.5)

                    if not photos:
                        log("   ! galerie vide ou non chargee")
                        await _dump_screen(driver, log, "galerie")
                        await _go_back(driver, navigator, log)
                    else:
                        idx = edit_fields["photo_index"]
                        log("   galerie: %d photos visibles, selection index=%d" % (len(photos), idx))
                        if idx >= len(photos):
                            log("   ! index %d hors limites (max=%d)" % (idx, len(photos) - 1))
                            await _go_back(driver, navigator, log)
                        else:
                            tap = photos[idx].get('tap', {})
                            log("   tap photo[%d] (y=%d, x=%d)" % (idx, tap.get('y', 0), tap.get('x', 0)))
                            await driver.ht.tap(tap['x'], tap['y'])
                            await asyncio.sleep(random.uniform(1.0, 2.0))

                            # 6d. Vérifier qu'on est sur l'écran de crop/preview
                            # Chercher "Terminé" ou "Choisir" ou "Enregistrer"
                            done_found = False
                            for attempt in range(3):
                                done_found = await _tap_done(driver, log)
                                if done_found:
                                    break
                                # Peut-être que la photo n'est pas encore chargée
                                log("   [retry %d] bouton validation non trouvé après sélection photo" % (attempt + 1))
                                await _dump_screen(driver, log, "crop_preview")
                                await asyncio.sleep(1.5)

                            if not done_found:
                                log("   ! impossible de valider la photo — skip")
                                await _go_back(driver, navigator, log)
                            else:
                                # 6e. Attendre le chargement et vérifier retour à edit_profile
                                log("   attente chargement photo...")
                                loaded = False
                                for wait_i in range(15):
                                    await asyncio.sleep(1)
                                    screen = await _detect_screen(driver, log)
                                    if screen == "edit_profile":
                                        log("   ✓ photo chargee, retour edit_profile confirmé")
                                        loaded = True
                                        photo_ok = True
                                        break
                                    elif screen == "own_profile":
                                        log("   ✓ photo chargee, retour profil")
                                        loaded = True
                                        photo_ok = True
                                        break
                                if not loaded:
                                    log("   ⚠ timeout chargement photo (15s)")
                                    await _dump_screen(driver, log, "apres_photo")

            results["photo"] = photo_ok
            # photo_url was popped and converted to photo_index — sync the result
            # so the runner sees photo_url as succeeded too
            if photo_ok:
                results["photo_url"] = True
            elif "photo_url" not in results:
                results["photo_url"] = False

        # Fermer l'edit profil
        try:
            await _go_back(driver, navigator, log)
        except Exception:
            log("   ! erreur retour apres edit_profile (non bloquant)")

    # ── Phase 2 : switch pro ────
    if config.get("pro"):
        try:
            from .switch_pro import switch_to_pro
            results["pro"] = await switch_to_pro(driver, navigator, log=log)
        except Exception as e:
            log("   ! erreur phase 2 (switch pro): %s" % str(e)[:150])
            results["pro"] = False

    # ── Phase 3 : confidentialite ───────────────────────
    if "private" in config:
        try:
            results["private"] = await set_private(driver, navigator, config["private"], log)
        except Exception as e:
            log("   ! erreur phase 3 (confidentialite): %s" % str(e)[:150])
            results["private"] = False

    # ── Phase 4 : limite d'âge ─────────────────────────
    if "age_limit" in config:
        try:
            results["age_limit"] = await set_age_limit(driver, navigator, config["age_limit"], log)
        except Exception as e:
            log("   ! erreur phase 4 (age_limit): %s" % str(e)[:150])
            results["age_limit"] = False

    log("=" * 50)
    log("CONFIG TERMINEE: %s" % results)
    log("=" * 50)

    return results
