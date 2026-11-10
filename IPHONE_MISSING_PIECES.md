# Ce qui manque dans le backend — Gap analysis VPS → FastAPI

Comparaison entre les scripts VPS originaux (`th_iphone/`, `ig_iphone/`) et le
portage FastAPI (`apps/backend/app/services/automation/`). Ce fichier documente
tout ce qui a ete perdu lors du portage et doit etre (re)ajoute.

---

## 1. CRITIQUE — Gestion des popups post-login

### Le probleme

Apres un login IG/Threads reussi, l'app affiche 2-3 popups avant d'arriver au feed :
- "Enregistrer vos informations de connexion ?" → taper "Enregistrer" ou "Plus tard"
- "Veuillez activer les notifications" → taper "Plus tard"
- Popup iOS systeme (notifications) → taper "Ne pas autoriser"

Le backend actuel (`device_session.py`) ne gere PAS ces ecrans. Apres le login,
il verifie une seule fois l'ecran et tombe sur "other" → echec.

### La solution (du VPS original)

Le VPS avait une **boucle de detection** qui tourne jusqu'a 15 iterations :

```python
# Pseudo-code de la boucle VPS (th_iphone/interact/account_login.py)
for step in range(15):
    screen = detect_login_screen(driver)

    if screen == "feed":
        return True  # Connecte !

    elif screen == "save_login":
        # "Enregistrer vos informations de connexion ?"
        # Taper "Enregistrer" dans la moitie basse (y > 600)
        # Sinon fallback "Plus tard"
        tap_button("Enregistrer", min_y=600)
        or tap_button("Plus tard")

    elif screen == "notif_popup":
        # "Veuillez activer les notifications"
        tap_button("Plus tard")

    elif screen == "2fa_notif":
        tap_button("Essayer d'une autre facon")

    elif screen == "2fa_choice":
        tap_button("Application d'authentification")
        tap_button("Continuer")

    elif screen == "2fa_code":
        code = generate_totp(secret)
        type_text(code)
        tap_button("Continuer")

    elif screen == "checkpoint":
        raise LoginRequired("checkpoint")

    elif screen == "login_error":
        raise LoginRequired("wrong_credentials")

    elif screen == "unknown":
        # RECOVERY : attendre, re-detecter, chercher des boutons popup
        await asyncio.sleep(3)
        screen = detect_login_screen(driver)
        if screen == "unknown":
            # Chercher des boutons de dismiss dans la moitie basse
            for label in ["ok", "plus tard", "ne pas autoriser", "autoriser"]:
                el = find_element(label, min_y=400)
                if el:
                    tap(el)
                    break
            # Re-detecter une derniere fois
            screen = detect_login_screen(driver)
            if screen == "unknown":
                raise LoginRequired("unknown_screen")
```

### Ecrans a ajouter a `_SCREEN_MARKERS`

```python
# Dans ig_driver.py, ajouter a _SCREEN_MARKERS :
"save_login":   ["Enregistrer vos informations", "Save your login info",
                 "Enregistrer les informations"],
"notif_popup":  ["Veuillez activer les notifications", "Turn on Notifications",
                 "Activer les notifications"],
"2fa_notif":    ["Vérifiez vos notifications", "Check your notifications"],
"2fa_choice":   ["Choisissez un moyen de confirmer", "Choose a way to confirm"],
"2fa_code":     ["Accédez à votre application", "Code à 6 chiffres",
                 "Enter the 6-digit code"],
"checkpoint":   ["challenge", "suspect", "confirmer votre identité",
                 "Confirm your identity", "We detected unusual activity"],
"login_error":  ["Incorrect", "Réessayer", "Introuvable",
                 "Sorry, your password was incorrect"],
"welcome":      ["Choisissez comment vous inscrire", "Join Instagram"],
```

### Labels de boutons popup a connaitre

Ces labels sont utilises pour dismiss les popups quand l'ecran est "unknown" :

```python
POPUP_DISMISS_LABELS = [
    "OK",
    "Plus tard",           # "Save login?" popup
    "Pas maintenant",      # Generic dismiss
    "Ne pas autoriser",    # iOS notification permission
    "Autoriser",           # iOS permission (si on veut accepter)
    "Fermer",              # Close button
    "Ignorer",             # Skip
    "Enregistrer",         # Save login info
    "Continuer",           # Continue
    "Continuer avec Instagram",  # SSO
    "Essayer d'une autre façon", # 2FA alternative
]
```

**Important :** ne taper ces boutons que si `y > 400` pour eviter de taper
dans un champ de formulaire qui contiendrait le meme texte.

---

## 2. CRITIQUE — Recovery d'ecrans inconnus

### Le probleme

Quand `detect_current_screen()` retourne "other" ou "unknown", le backend abandonne.

### La solution VPS

Le VPS avait un systeme en 3 etapes :

1. **Attendre 3s** — l'ecran est peut-etre en transition
2. **Re-detecter** — souvent l'ecran a change pendant l'attente
3. **Chercher des boutons popup** — scanner l'arbre d'accessibilite pour les labels
   de dismiss (OK, Plus tard, Ne pas autoriser, etc.) avec `y > 400`
4. **Taper le premier match** — et re-detecter
5. **Si toujours "unknown"** — dump l'arbre d'accessibilite dans les logs pour debug → abort

### Implementation suggeree

```python
async def _handle_unknown_screen(self, drv, max_retries=3):
    """Tente de recuperer d'un ecran inconnu en cherchant des popups."""
    for attempt in range(max_retries):
        await asyncio.sleep(3)
        screen = await drv.detect_current_screen()
        if screen != "other":
            return screen

        # Chercher un bouton popup a taper
        elements = await drv.ht.get_elements(clickable_only=True)
        for el in elements:
            label = (el.get("text") or "").lower()
            if el.get("y", 0) > 400:
                for dismiss in ["ok", "plus tard", "pas maintenant",
                                "ne pas autoriser", "fermer", "ignorer"]:
                    if dismiss in label:
                        self.log(f"   [recovery] popup detecte: '{el['text']}', tap")
                        await drv.ht.tap(el["x"], el["y"])
                        await asyncio.sleep(2)
                        break

    # Toujours inconnu — log l'arbre pour debug
    elements = await drv.ht.get_elements()
    self.log(f"   [recovery] ecran inconnu apres {max_retries} essais")
    for el in elements[:20]:
        self.log(f"     {el.get('type','?')} | {el.get('text','')[:50]} | y={el.get('y',0)}")
    return "unknown"
```

---

## 3. IMPORTANT — Helper `ensure_screen()`

### Le probleme

Les scripts VPS avaient une fonction `ensure_screen(target)` qui peut naviguer
depuis n'importe quel ecran vers un ecran cible. Le backend n'a pas ca.

### La solution VPS (th_iphone/driver.py)

```python
async def ensure_screen(self, target, max_retries=3):
    """Navigue vers l'ecran cible avec recovery."""
    for attempt in range(max_retries):
        screen = await self.detect_current_screen()
        if screen == target:
            return True

        # D'abord essayer de dismiss un popup
        dismissed = await self._dismiss_popup()
        if dismissed:
            continue

        # Navigation contextuelle
        if screen == "post_detail":
            await self.tap_element("Retour")
        elif screen == "other_profile":
            await self.tap_element("Retour")
        elif screen == "create":
            await self.tap_element("Annuler")
        else:
            # Navigation par onglets
            tab_map = {"feed": 0.1, "search": 0.3, "compose": 0.5,
                       "activity": 0.7, "profile": 0.9}
            if target in tab_map:
                await self.ht.tap(self.ht.screen_w * tab_map[target], 780)

        await asyncio.sleep(1.5)

    return False
```

### `_dismiss_popup()`

```python
async def _dismiss_popup(self):
    """Cherche et tape des boutons de dismiss courants."""
    dismiss_labels = ["Ne pas autoriser", "Plus tard", "Pas maintenant",
                      "Fermer", "Ignorer", "OK"]
    for label in dismiss_labels:
        el = await self.find_element(label)
        if el and el.get("y", 0) > 300:
            await self.ht.tap(el["x"], el["y"])
            await asyncio.sleep(1)
            return True
    return False
```

### `safe_action()`

```python
async def safe_action(self, action_fn, expected_screen, description="action"):
    """Execute une action et verifie le resultat."""
    try:
        await action_fn()
    except Exception as e:
        self.log(f"   [safe] {description} echoue: {e}")
        return False

    await asyncio.sleep(1)
    screen = await self.detect_current_screen()
    if screen == expected_screen:
        return True

    self.log(f"   [safe] apres {description}: attendu {expected_screen}, got {screen}")
    return await self.ensure_screen(expected_screen)
```

---

## 4. IMPORTANT — Anti-patterns comportementaux

### Le probleme

Le backend n'a aucun module `behavior/`. Les sessions de feed sont mecaniques :
scroll → like → scroll → like. Un humain est plus imprevisible.

### Les 9 patterns du VPS (th_iphone/behavior/patterns.py)

Chaque pattern est une fonction async qui prend un driver et un log.
Ils sont appeles aleatoirement pendant les sessions de feed.

```python
# 1. Remonter pour relire un post
async def scroll_back(drv, log):
    log("   [behavior] scroll back to re-read")
    await drv.scroll_up()
    await asyncio.sleep(random.uniform(2, 5))
    await drv.scroll_down()

# 2. Pause longue (distraction)
async def pause_distraction(drv, log):
    pause = random.uniform(8, 20)
    log(f"   [behavior] distraction pause {pause:.0f}s")
    await asyncio.sleep(pause)

# 3. Hesitation avant action
async def hesitate_before_action(drv, log):
    pause = random.uniform(0.5, 2.0)
    await asyncio.sleep(pause)

# 4. Lecture lente de la legende
async def slow_read_caption(drv, log, caption_length):
    read_time = min(caption_length / 250 * 60, 12)  # ~250 mots/min, max 12s
    read_time *= random.uniform(0.8, 1.3)
    await asyncio.sleep(read_time)

# 5. Parcourir les reponses lentement
async def browse_replies_slow(drv, log):
    log("   [behavior] browsing replies slowly")
    await drv.tap_element("Voir les commentaires")
    await asyncio.sleep(random.uniform(1.5, 3))
    for _ in range(random.randint(1, 4)):
        await drv.scroll_down()
        await asyncio.sleep(random.uniform(2, 5))
    await drv.tap_element("Retour")

# 6. Scroll imprecis (trop ou pas assez, puis correction)
async def imprecise_scroll(drv, log):
    overshoot = random.choice([-0.15, 0.15])  # fraction d'ecran
    await drv.ht.swipe(...)  # scroll avec overshoot
    await asyncio.sleep(random.uniform(0.3, 0.8))
    await drv.ht.swipe(...)  # correction

# 7. Double-tap rate puis reussi
async def double_tap_miss(drv, log, x, y):
    offset_x = random.uniform(-15, 15)
    offset_y = random.uniform(-15, 15)
    await drv.ht.tap(x + offset_x, y + offset_y)  # rate
    await asyncio.sleep(random.uniform(0.08, 0.15))
    await drv.ht.tap(x, y)  # reussi

# 8. Peek rapide sur un profil (curiosite)
async def random_profile_peek(drv, log, username_el):
    log(f"   [behavior] quick peek at {username_el.get('text', '?')}")
    await drv.ht.tap(username_el["x"], username_el["y"])
    await asyncio.sleep(random.uniform(2, 5))
    if random.random() < 0.3:
        await drv.scroll_down()
        await asyncio.sleep(random.uniform(1, 3))
    await drv.tap_element("Retour")

# 9. Corrections de frappe
async def typing_corrections(drv, log, text):
    # Taper une partie du texte
    cut = random.randint(3, min(len(text), 10))
    await drv.ht.type_text(text[:cut])
    await asyncio.sleep(random.uniform(0.3, 0.8))
    # Supprimer 1-5 caracteres
    delete_count = random.randint(1, min(5, cut))
    for _ in range(delete_count):
        await drv.ht.press_key("delete")
        await asyncio.sleep(random.uniform(0.05, 0.15))
    await asyncio.sleep(random.uniform(0.2, 0.5))
    # Retaper correctement
    await drv.ht.type_text(text[cut - delete_count:])
```

### Comment les integrer

Creer `apps/backend/app/services/automation/behavior/` avec :
- `__init__.py`
- `patterns.py` — les 9 fonctions ci-dessus
- `presets.py` — resolution des presets depuis l'API

Les appeler depuis `ig_runner.py` et `th_runner.py` pendant les sessions de feed :
```python
if random.random() < 0.15:
    pattern = random.choice([scroll_back, pause_distraction, imprecise_scroll, ...])
    await pattern(drv, log)
```

---

## 5. UTILE — Typage realiste

### Le probleme

`human_touch.py` choisit un intervalle unique pour toute la chaine de caracteres :
```python
interval = random.randint(30, 80)  # fixe pour tout le texte
await self._call("type_text", {"text": text, "interval": interval})
```

Un vrai humain tape a des vitesses variables : rapide sur les lettres courantes,
plus lent sur les chiffres/symboles, avec des hesitations.

### La solution

Taper caractere par caractere avec variation :

```python
async def type_text_realistic(self, text, *, method="normal"):
    """Saisie caractere par caractere avec vitesse variable."""
    for i, char in enumerate(text):
        # Intervalle de base selon le type de caractere
        if char.isalpha():
            base = random.randint(25, 65)
        elif char.isdigit():
            base = random.randint(60, 120)
        else:  # symboles
            base = random.randint(80, 150)

        # Hesitation occasionnelle (5% de chance)
        if random.random() < 0.05 and i > 0:
            await asyncio.sleep(random.uniform(0.2, 0.8))

        # Methode lente pour les mots de passe
        if method == "slow":
            base = int(base * 1.5)

        await self._call("type_text", {"text": char, "interval": base})
        await asyncio.sleep(base / 1000)
```

---

## 6. UTILE — Corrections backend necessaires

### A. `perform_action` → `tap_screen`

Dans `human_touch.py` ligne 168 :
```python
# AVANT (bug) :
await self._call("perform_action", {"action": "tap", "x": ..., "y": ..., "duration": ...})

# APRES (correct) :
await self._call("tap_screen", {"x": round(x, 1), "y": round(y, 1)})
```

Note : `tap_screen` dans ios-mcp ne prend PAS de `duration`. La duree du tap
est geree internement par HIDManager (began → 50ms → moved → 50ms → ended).

### B. `terminate_app` → `kill_app`

Dans `human_touch.py` ligne 274 :
```python
# AVANT :
await self._call("terminate_app", {"bundle_id": bundle})

# APRES :
await self._call("kill_app", {"bundle_id": bundle})
```

### C. Docstring de human_touch.py

Mettre a jour les lignes 7-16 avec les vrais noms d'outils MCP :
```python
"""
The MCP server on the iPhone exposes:
    POST /mcp — JSON-RPC via tools/call with methods:
        - tap_screen: single touch at {x, y}
        - swipe_screen: swipe from/to with duration/steps
        - drag_and_drop: precise multi-point drag
        - type_text: keyboard input
        - launch_app / kill_app: app lifecycle
        - get_ui_elements: accessibility tree
        - get_screen_info: screen dimensions
        - screenshot: capture screen
"""
```

---

## 7. Resume des priorites

| Prio | Quoi | Impact | Effort |
|------|------|--------|--------|
| **P0** | Boucle post-login avec gestion popups | Debloque le E2E | 1-2h |
| **P0** | Ajouter les screen markers post-login | Necessaire pour P0 | 15min |
| **P0** | Corriger `perform_action` → `tap_screen` | Les taps ne marchent pas sans | 5min |
| **P0** | Corriger `terminate_app` → `kill_app` | Le kill d'app ne marche pas | 2min |
| **P1** | Recovery d'ecrans inconnus | Robustesse | 30min |
| **P1** | Helper `ensure_screen()` | Robustesse navigation | 1h |
| **P2** | Module behavior/patterns.py | Anti-detection | 1-2h |
| **P2** | Typage realiste (per-character) | Anti-detection | 30min |
| **P3** | `safe_action()` wrapper | Fiabilite | 30min |
