#!/usr/bin/env python3
"""
Test carousel flow — step by step avec dumps.
Usage: python3 test_carousel_flow.py [photo_count] [audio_query]
Exemples:
  python3 test_carousel_flow.py 3
  python3 test_carousel_flow.py 3 "Ninho"
"""

import httpx
import json
import sys
import time

MCP = "http://127.0.0.1:8190/mcp"
PHOTO_COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 3
AUDIO_QUERY = sys.argv[2] if len(sys.argv) > 2 else None


def mcp(method, args=None):
    r = httpx.post(MCP, json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": method, "arguments": args or {}}
    }, timeout=15)
    return json.loads(r.text)


def get_elements():
    r = mcp("get_ui_elements")
    data = json.loads(r["result"]["content"][0]["text"])
    return data.get("elements", [])


def dump(label=""):
    els = get_elements()
    print(f"\n{'='*60}")
    print(f"  DUMP: {label}  ({len(els)} elements)")
    print(f"{'='*60}")
    for i, e in enumerate(els):
        t = e.get("tap", {})
        txt = (e.get("text") or "")[:60]
        print(f"  {i:>2}  ({t.get('x',0):>3},{t.get('y',0):>3})  {txt}")
    return els


def find(els, text=None, contains=None):
    for e in els:
        t = (e.get("text") or "")
        if text and t == text:
            return e
        if contains and contains.lower() in t.lower():
            return e
    return None


def find_all(els, contains=None):
    return [e for e in els if contains and contains.lower() in (e.get("text") or "").lower()]


def tap(e, label=""):
    t = e.get("tap", {})
    x, y = t.get("x", 0), t.get("y", 0)
    print(f"  -> TAP {label} ({x}, {y})")
    mcp("tap_screen", {"x": x, "y": y})
    time.sleep(1.5)


def tap_xy(x, y, label=""):
    print(f"  -> TAP {label} ({x}, {y})")
    mcp("tap_screen", {"x": x, "y": y})
    time.sleep(1.5)


def tap_text(text, label=""):
    print(f"  -> TAP_ELEMENT '{text}' ({label})")
    mcp("tap_element", {"text": text})
    time.sleep(1.5)


def dismiss_popup(els):
    """Cherche et ferme les popups connus."""
    ok = find(els, text="OK")
    fermer = find(els, text="Fermer")
    # Popups connus: "Partager plus", "À votre image", "Partage de publications"
    if find(els, contains="Partager plus") and ok:
        print("  ⚠ POPUP 'Partager plus' -> OK")
        tap(ok, "OK")
        return True
    if find(els, contains="votre image") and ok:
        print("  ⚠ POPUP 'À votre image' -> OK")
        tap(ok, "OK")
        return True
    if find(els, contains="Partage de publications"):
        target = ok or fermer
        if target:
            print("  ⚠ POPUP 'Partage de publications' -> %s" % (target.get("text", "")))
            tap(target, target.get("text", ""))
            return True
    return False


def step(label):
    print(f"\n{'─'*60}")
    print(f"  STEP: {label}")
    print(f"{'─'*60}")


# ══════════════════════════════════════════════════════════════
#  FLOW
# ══════════════════════════════════════════════════════════════

print(f"\n🎠 Test carousel flow — {PHOTO_COUNT} photos" +
      (f" + audio '{AUDIO_QUERY}'" if AUDIO_QUERY else ""))

# ── STEP 1: On devrait etre sur la galerie (apres tap Publication)
step("1. Galerie — activer multi-select")
els = dump("Galerie")

# Chercher "Sélectionner" pour multi-select
sel_btn = find(els, contains="lectionner")
if not sel_btn:
    sel_btn = find(els, contains="Multi")
if sel_btn:
    tap(sel_btn, "Sélectionner (multi-select)")
    time.sleep(1)
    # Popup possible
    els = get_elements()
    dismiss_popup(els)
else:
    print("  ⚠ Bouton Sélectionner non trouvé, peut-être déjà en multi-select?")

# ── STEP 2: Selectionner les photos
step(f"2. Sélectionner {PHOTO_COUNT} photos")
els = dump("Galerie multi-select")

# Filtrer les miniatures (y > 220, exclure Camera)
photos = [e for e in els
          if "Miniature" in (e.get("text") or "")
          and e.get("tap", {}).get("y", 0) > 220
          and "cam" not in (e.get("text") or "").lower()]
photos.sort(key=lambda e: (e.get("tap", {}).get("y", 0), e.get("tap", {}).get("x", 0)))

print(f"  {len(photos)} photos disponibles")
if len(photos) < PHOTO_COUNT:
    print(f"  ⚠ Pas assez de photos ({len(photos)} < {PHOTO_COUNT})")

# La 1ere est deja selectionnee, selectionner les suivantes
for i in range(1, min(PHOTO_COUNT, len(photos))):
    tap(photos[i], f"Photo #{i+1}")
    time.sleep(0.5)

print(f"  ✓ {min(PHOTO_COUNT, len(photos))} photos sélectionnées")

# ── STEP 3: Suivant (galerie → editeur)
step("3. Suivant (galerie → éditeur)")
els = dump("Après sélection")

suivant = find(els, text="Suivant")
if suivant:
    tap(suivant, "Suivant")
    time.sleep(2)
    # Popup possible
    els = get_elements()
    if dismiss_popup(els):
        time.sleep(1)
        els = get_elements()
        dismiss_popup(els)  # Double popup possible
else:
    print("  ✗ ÉCHEC: bouton Suivant non trouvé!")
    dump("ERREUR après sélection")
    sys.exit(1)

# ── STEP 4: Éditeur — ajouter audio si demandé
step("4. Éditeur")
els = dump("Éditeur")

if AUDIO_QUERY:
    step(f"4b. Ajout audio: '{AUDIO_QUERY}'")
    audio_btn = find(els, text="Audio")
    if audio_btn:
        tap(audio_btn, "Audio")
        time.sleep(2)
        els = dump("Recherche audio")

        # Chercher le champ de recherche
        search_field = find(els, contains="Rechercher")
        if search_field:
            tap(search_field, "Champ recherche")
            time.sleep(1)
        else:
            # Essayer tap_element natif
            tap_text("Rechercher", "Champ recherche (natif)")
            time.sleep(1)

        # Taper le texte
        print(f"  -> TYPE '{AUDIO_QUERY}'")
        mcp("type_text", {"text": AUDIO_QUERY})
        time.sleep(3)

        # Sélectionner le premier résultat
        els = dump("Résultats audio")
        results = [e for e in els
                   if e.get("tap", {}).get("y", 0) > 170
                   and (e.get("text") or "") not in ("", "Annuler", "Rechercher", "Audio")
                   and "Onglet" not in (e.get("text") or "")]
        results.sort(key=lambda e: e.get("tap", {}).get("y", 0))
        if results:
            tap(results[0], f"Premier résultat: {(results[0].get('text') or '')[:40]}")
            time.sleep(2)

            # Confirmer la sélection (bouton sans label en bas)
            els = dump("Confirmation audio")
            confirm = [e for e in els
                       if e.get("tap", {}).get("y", 0) > 700
                       and not (e.get("text") or "").strip()]
            confirm.sort(key=lambda e: -e.get("tap", {}).get("x", 0))
            if confirm:
                tap(confirm[0], "Confirmer sélection audio")
                time.sleep(2)

            # "C'est fait"
            els = dump("Config audio")
            done_btn = find(els, contains="fait")
            if done_btn:
                tap(done_btn, "C'est fait")
                time.sleep(2)
        else:
            print("  ⚠ Aucun résultat audio trouvé")
    else:
        print("  ⚠ Bouton Audio non trouvé")

# ── STEP 5: Suivant (éditeur → page finale)
step("5. Suivant (éditeur → page finale)")
els = dump("Avant Suivant éditeur")

suivant = find(els, text="Suivant")
if suivant:
    tap(suivant, "Suivant")
    time.sleep(2)
    # Popups possibles (privacy)
    els = get_elements()
    if dismiss_popup(els):
        time.sleep(1)
        els = get_elements()
        dismiss_popup(els)
else:
    print("  ✗ ÉCHEC: bouton Suivant non trouvé sur l'éditeur!")
    dump("ERREUR éditeur")
    sys.exit(1)

# ── STEP 6: Page finale (caption + partager)
step("6. Page finale atteinte!")
els = dump("PAGE FINALE")

caption_field = find(els, contains="gende")
partager = find(els, text="Partager")

if caption_field and partager:
    print("\n  ✅ SUCCÈS — Page finale atteinte!")
    print("  → Champ légende trouvé")
    print("  → Bouton Partager trouvé")
    print("  → (On ne publie pas, test terminé)")
else:
    print("\n  ⚠ Page finale incomplète")
    if not caption_field:
        print("    ✗ Champ légende non trouvé")
    if not partager:
        print("    ✗ Bouton Partager non trouvé")

print(f"\n{'═'*60}")
print("  Test terminé.")
print(f"{'═'*60}\n")
