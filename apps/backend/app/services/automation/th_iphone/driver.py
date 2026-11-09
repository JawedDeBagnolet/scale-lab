"""
th_iphone/driver.py — Driver Threads iPhone (async).

Wraps HumanTouch + ScrollEngine avec des methodes haut-niveau pour Threads :
- Recherche d'elements par label/texte
- Tap sur element par nom semantique
- Detection du type de post visible
- Parsing des compteurs (likes, replies, reposts)
"""

import asyncio
import json
import random
import re
import time

from .selectors import sel, TH_BUNDLE, BOTTOM_BAR_Y, SCREEN_W, SCREEN_H


def _norm(s):
    """Normalise les apostrophes/guillemets iOS."""
    return s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')


class THDriver:
    """Interface de pilotage Threads iOS (async)."""

    def __init__(self, ht, scroller, lang="fr", log=print):
        from .selectors import set_lang
        set_lang(lang)
        self.ht = ht
        self.scroller = scroller
        self.log = log
        self._elements_cache = None
        self._cache_age = 0

    # ── Elements ──────────────────────────────────────────────────────────

    async def get_elements(self, refresh=False, clickable_only=False, max_elements=80):
        """Recupere les elements UI visibles."""
        now = time.time()
        if not refresh and self._elements_cache and (now - self._cache_age) < 4:
            return self._elements_cache

        try:
            r = await self.ht._call("get_ui_elements", {
                "clickable_only": clickable_only,
                "max_elements": max_elements,
            })
            if isinstance(r, dict) and "content" in r:
                raw = r["content"][0]["text"]
                data = json.loads(raw)
            elif isinstance(r, str):
                data = json.loads(r)
            else:
                data = r
            self._elements_cache = data.get("elements", [])
            self._cache_age = now
            return self._elements_cache
        except Exception as e:
            self.log("   [th] get_elements error: %s" % e)
            return []

    async def find_element(self, text=None, contains=None, clickable=None, refresh=False):
        """Trouve un element par texte exact ou contenu."""
        els = await self.get_elements(refresh=refresh)
        for e in els:
            label = _norm(e.get("text", ""))
            if text and label == text:
                return e
            if contains and contains.lower() in label.lower():
                if clickable is None or e.get("clickable") == clickable:
                    return e
        return None

    async def find_elements(self, contains=None, clickable=None, refresh=False):
        """Trouve tous les elements contenant un texte."""
        els = await self.get_elements(refresh=refresh)
        results = []
        for e in els:
            label = _norm(e.get("text", ""))
            if contains and contains.lower() in label.lower():
                if clickable is None or e.get("clickable") == clickable:
                    results.append(e)
        return results

    async def tap_element(self, text=None, contains=None, refresh=True):
        """Tape sur un element trouve par texte."""
        el = await self.find_element(text=text, contains=contains, clickable=True, refresh=refresh)
        if el and el.get("tap"):
            await self.ht.tap(el["tap"]["x"], el["tap"]["y"])
            return True
        return False

    # ── Positions ─────────────────────────────────────────────────────────

    async def tap_pos(self, x_frac, y_frac):
        """Tape a une position relative (fractions 0-1)."""
        x = int(x_frac * SCREEN_W)
        y = int(y_frac * SCREEN_H)
        await self.ht.tap(x, y)

    # ── Scroll (via ScrollEngine) ────────────────────────────────────────

    async def scroll_down(self, intensity="normal"):
        """Scroll vers le bas via ScrollEngine."""
        distances = {"light": (250, 380), "normal": (380, 520), "strong": (500, 650)}
        d = distances.get(intensity, distances["normal"])
        await self.scroller.scroll_by(random.uniform(*d), compensate=False)

    async def scroll_up(self, intensity="light"):
        """Scroll vers le haut via ScrollEngine."""
        distances = {"light": (100, 200), "normal": (200, 350)}
        d = distances.get(intensity, distances["light"])
        await self.scroller.scroll_by(-random.uniform(*d), compensate=False)

    # ── Waits ─────────────────────────────────────────────────────────────

    async def wait(self, context="tap"):
        """Attente contextuelle."""
        waits = {
            "tap": (0.3, 0.8),
            "scroll": (0.5, 1.5),
            "transition": (1.5, 3.0),
            "read_short": (1.0, 2.5),
            "read_long": (2.5, 6.0),
        }
        mn, mx = waits.get(context, (0.5, 1.5))
        await asyncio.sleep(random.uniform(mn, mx))

    # ── Text input ────────────────────────────────────────────────────────

    async def type_text(self, text, method="normal"):
        """Saisie de texte."""
        if method == "slow":
            for ch in text:
                await self.ht._call("type_text", {"text": ch, "delay_ms": random.randint(30, 80)})
                await asyncio.sleep(random.uniform(0.05, 0.15))
        else:
            await self.ht._call("input_text", {"text": text})

    # ── Screen detection ──────────────────────────────────────────────────

    async def detect_current_screen(self, refresh=True):
        """Detecte l'ecran actuel de Threads."""
        els = await self.get_elements(refresh=refresh)
        labels = [_norm(e.get("text", "")) for e in els]
        all_text = " ".join(labels).lower()

        key_markers = []
        for marker in ["menu latéral", "statistiques", "retour", "champ de texte", "nouveau thread", "rechercher sur threads"]:
            if marker in all_text:
                key_markers.append(marker)
        if key_markers:
            self.log("   [detect] markers: %s" % ", ".join(key_markers))
        else:
            self.log("   [detect] aucun marker (%d elements, first: %s)" % (len(els), (labels[0][:30] if labels else "vide")))

        if "retour" in all_text and ("thread" in all_text or "ajoutez votre" in all_text or "vues" in all_text or "menu d'actions" in all_text):
            return "post_detail"
        if "champ de texte" in all_text or "nouveau thread" in all_text:
            return "create"
        if "statistiques" in all_text:
            return "profile"
        if "passer sur instagram" in all_text or "options de profil" in all_text:
            return "other_profile"
        if "menu latéral" in all_text:
            return "feed"
        if "créer une publication" in all_text and "options de publication" in all_text:
            return "feed"
        if "rechercher sur threads" in all_text:
            return "search"
        if "tout" in all_text and ("mentions" in all_text or "vérifiées" in all_text):
            return "activity"
        if "nouveau message" in all_text or "conversations" in all_text:
            return "messages"

        return "unknown"

    # ── Helper / Recovery ─────────────────────────────────────────────────

    async def ensure_screen(self, target, max_retries=3):
        """S'assure qu'on est sur l'ecran cible. Si non, tente de naviguer."""
        from .selectors import (
            TAB_HOME_X, TAB_PROFILE_X, TAB_CREATE_X,
            TAB_ACTIVITY_X, TAB_MESSAGES_X, BOTTOM_BAR_Y,
        )

        routes = {
            "feed": TAB_HOME_X,
            "profile": TAB_PROFILE_X,
            "activity": TAB_ACTIVITY_X,
            "messages": TAB_MESSAGES_X,
        }

        for attempt in range(max_retries):
            screen = await self.detect_current_screen(refresh=True)
            if screen == target:
                return True

            self.log("   [helper] ecran=%s, cible=%s (tentative %d)" % (screen, target, attempt + 1))

            await self._dismiss_popup()

            if screen == "post_detail" and target != "post_detail":
                if await self.tap_element(contains="Retour"):
                    await self.wait('transition')
                    await asyncio.sleep(1)
                    continue

            if screen == "other_profile" and target not in ("other_profile", "profile"):
                if await self.tap_element(contains="Retour"):
                    await self.wait('transition')
                    await asyncio.sleep(1)
                    continue

            if screen == "create" and target != "create":
                if await self.tap_element(contains="Annuler"):
                    await self.wait('transition')
                    await asyncio.sleep(1)
                    continue

            if await self.tap_element(contains="Retour") or await self.tap_element(contains="Fermer"):
                await self.wait('transition')
                await asyncio.sleep(1)
                screen = await self.detect_current_screen(refresh=True)
                if screen == target:
                    return True

            if target == "create":
                await self.tap_pos(TAB_CREATE_X, BOTTOM_BAR_Y)
            elif target in routes:
                await self.tap_pos(routes[target], BOTTOM_BAR_Y)
            else:
                await self.tap_pos(TAB_HOME_X, BOTTOM_BAR_Y)

            await self.wait('transition')
            await asyncio.sleep(1)

        screen = await self.detect_current_screen(refresh=True)
        if screen == target:
            return True

        self.log("   [helper] ECHEC navigation vers %s (ecran actuel: %s)" % (target, screen))
        return False

    async def _dismiss_popup(self):
        """Tente de fermer un popup courant."""
        popup_labels = ["Ne pas autoriser", "Plus tard", "Pas maintenant", "Fermer", "Ignorer", "OK"]
        for label in popup_labels:
            el = await self.find_element(contains=label, clickable=True, refresh=False)
            if el and el.get("tap"):
                y = el["tap"]["y"]
                if y > 300:
                    await self.ht.tap(el["tap"]["x"], el["tap"]["y"])
                    self.log("   [helper] popup fermee: %s" % label)
                    await self.wait('tap')
                    await asyncio.sleep(0.5)
                    return True
        return False

    async def safe_action(self, action_coro, expected_screen=None, description="action"):
        """Execute une action async et verifie qu'on est toujours au bon endroit."""
        try:
            result = await action_coro
            if expected_screen:
                await asyncio.sleep(1)
                screen = await self.detect_current_screen(refresh=True)
                if screen != expected_screen:
                    self.log("   [helper] apres %s: ecran=%s (attendu=%s), recovery..." % (description, screen, expected_screen))
                    await self.ensure_screen(expected_screen)
            return result
        except Exception as e:
            self.log("   [helper] erreur %s: %s" % (description, str(e)[:100]))
            if expected_screen:
                await self.ensure_screen(expected_screen)
            return None

    # ── Post parsing ──────────────────────────────────────────────────────

    async def parse_visible_posts(self, refresh=True):
        """Parse les posts visibles sur le feed."""
        els = await self.get_elements(refresh=refresh)
        posts = []
        current_post = None

        for e in els:
            text = _norm(e.get("text", ""))

            if "Il y a" in text and e.get("clickable"):
                if current_post:
                    posts.append(current_post)
                username = text.split(" Il y a")[0].strip()
                header_y = e.get("tap", {}).get("y", 0)
                if header_y < 50 or header_y > 750:
                    current_post = None
                    continue
                current_post = {
                    "username": username,
                    "time_text": text,
                    "caption": "",
                    "likes": 0,
                    "replies": 0,
                    "reposts": 0,
                    "tap": e.get("tap", {}),
                    "actions": {},
                }
                continue

            if not current_post:
                continue

            if len(text) > 20 and "personnes ont" not in text and "Options" not in text:
                current_post["caption"] = text

            if "personnes ont aimé" in text:
                m = re.search(r"(\d+)\s*personnes", text)
                if m:
                    current_post["likes"] = int(m.group(1))
                current_post["actions"]["like"] = e.get("tap", {})

            if "personnes ont répondu" in text:
                m = re.search(r"(\d+)\s*personnes", text)
                if m:
                    current_post["replies"] = int(m.group(1))
                current_post["actions"]["reply"] = e.get("tap", {})

            if "personnes ont republié" in text:
                m = re.search(r"(\d+)\s*personnes", text)
                if m:
                    current_post["reposts"] = int(m.group(1))
                current_post["actions"]["repost"] = e.get("tap", {})

            if "personnes ont partagé" in text:
                current_post["actions"]["share"] = e.get("tap", {})

        if current_post:
            posts.append(current_post)

        return posts
