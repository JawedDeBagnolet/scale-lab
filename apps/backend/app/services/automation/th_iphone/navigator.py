"""
th_iphone/navigator.py — Navigation entre les ecrans Threads (async).

Gere les transitions : feed, search, create, activity, profile.
Detecte l'ecran actuel et navigue vers la cible.
"""

import asyncio
import random

from .selectors import (
    sel, TH_BUNDLE,
    BOTTOM_BAR_Y, TAB_HOME_X, TAB_MESSAGES_X, TAB_CREATE_X,
    TAB_ACTIVITY_X, TAB_PROFILE_X,
)


class THNavigator:
    """Navigation Threads iOS (async)."""

    def __init__(self, driver, log=print):
        self.d = driver
        self.log = log

    # ── Lancement / Fermeture ─────────────────────────────────────────────

    async def open_threads(self):
        """Lance Threads et attend que le feed soit charge."""
        self.log("-> Ouverture Threads")
        await self.d.ht.launch_app(TH_BUNDLE)
        await self.d.wait('transition')
        await asyncio.sleep(2)

        screen = await self.d.detect_current_screen()
        self.log("   ecran detecte: %s" % screen)

        await self._dismiss_popups()
        return screen

    async def close_threads(self):
        """Ferme Threads."""
        await self.d.ht.terminate_app(TH_BUNDLE)
        self.log("   Threads ferme")

    # ── Navigation tabs ───────────────────────────────────────────────────

    async def _tap_tab(self, x_frac, label):
        """Tape sur un tab de la bottom bar."""
        self.log("-> Navigation: %s" % label)
        await self.d.tap_pos(x_frac, BOTTOM_BAR_Y)
        await self.d.wait('transition')
        await asyncio.sleep(1)

    async def go_home(self):
        """Va au feed principal."""
        screen = await self.d.detect_current_screen(refresh=True)
        if screen == 'feed':
            await self.d.tap_pos(TAB_HOME_X, BOTTOM_BAR_Y)
            await self.d.wait('tap')
            await asyncio.sleep(0.3)
            await self.d.tap_pos(TAB_HOME_X, BOTTOM_BAR_Y)
        else:
            await self._tap_tab(TAB_HOME_X, sel("tab_home"))
        await self.d.wait('transition')

    async def go_search(self):
        """Va a l'ecran de recherche."""
        await self.d.tap_element(contains=sel("rechercher"), refresh=True)
        await self.d.wait('transition')

    async def go_create(self):
        """Va a l'ecran de creation."""
        await self._tap_tab(TAB_CREATE_X, sel("tab_create"))

    async def go_activity(self):
        """Va a l'ecran d'activite."""
        await self._tap_tab(TAB_ACTIVITY_X, sel("tab_activity"))

    async def go_profile(self):
        """Va au profil."""
        await self._tap_tab(TAB_PROFILE_X, sel("tab_profile"))

    async def go_messages(self):
        """Va aux messages."""
        await self._tap_tab(TAB_MESSAGES_X, sel("tab_messages"))

    # ── Navigation retour ─────────────────────────────────────────────────

    async def go_back(self):
        """Revient en arriere."""
        if await self.d.tap_element(contains=sel("retour")):
            await self.d.wait('transition')
            return True
        if await self.d.tap_element(contains=sel("fermer")):
            await self.d.wait('transition')
            return True
        return False

    # ── Popups ────────────────────────────────────────────────────────────

    POPUP_MARKERS = [
        "Ajoutez cette publication",
        "Ne manquez aucune",
        "Activer les notifications",
        "Partagez ce thread",
    ]

    async def _dismiss_popups(self, max_tries=5):
        """Ferme les popups courants (notifications, mise a jour, etc.)."""
        for _ in range(max_tries):
            dismissed = False

            if await self.d.tap_element(contains="Ne pas autoriser"):
                self.log("   popup notifications dismissee")
                await self.d.wait('transition')
                await asyncio.sleep(1)
                dismissed = True
                continue

            if await self.d.tap_element(text="Plus tard"):
                self.log("   popup dismissee (Plus tard)")
                await self.d.wait('transition')
                await asyncio.sleep(1)
                dismissed = True
                continue

            if await self.d.tap_element(text="Terminé"):
                self.log("   popup dismissee (Termine)")
                await self.d.wait("transition")
                await asyncio.sleep(1)
                dismissed = True
                continue

            if await self.d.tap_element(contains="Pas maintenant"):
                self.log("   popup dismissee (Pas maintenant)")
                await self.d.wait('transition')
                await asyncio.sleep(1)
                dismissed = True
                continue

            els = await self.d.get_elements(refresh=True)
            texts = [e.get("text", "") for e in els]
            if any("Ne manquez aucune" in t or "Activer les notifications" in t for t in texts):
                for e in els:
                    t = e.get("text", "")
                    y = e.get("rect", {}).get("y", 0)
                    if t == "Fermer" and y > 300:
                        await self.d.ht.tap(e["tap"]["x"], e["tap"]["y"])
                        self.log("   popup notifications Threads dismissee")
                        await self.d.wait('transition')
                        await asyncio.sleep(1)
                        dismissed = True
                        break

            if not dismissed:
                break

    # ── Recherche de profil ───────────────────────────────────────────────

    async def search_user(self, username):
        """Recherche un utilisateur et va sur son profil."""
        self.log("-> Recherche @%s" % username)

        await self.d.tap_element(contains="Rechercher", refresh=True)
        await self.d.wait('transition')
        await asyncio.sleep(1)

        search_bar = await self.d.find_element(contains="Rechercher sur Threads", refresh=True)
        if search_bar and search_bar.get("tap"):
            await self.d.ht.tap(search_bar["tap"]["x"], search_bar["tap"]["y"])
            await self.d.wait('tap')
            await asyncio.sleep(0.5)

        await self.d.type_text(username)
        await asyncio.sleep(2)

        result = await self.d.find_element(contains=username, clickable=True, refresh=True)
        if result and result.get("tap"):
            await self.d.ht.tap(result["tap"]["x"], result["tap"]["y"])
            await self.d.wait('transition')
            await asyncio.sleep(2)
            self.log("   profil @%s ouvert" % username)
            return True

        self.log("   @%s non trouve" % username)
        return False

    # ── Visite profil ─────────────────────────────────────────────────────

    async def visit_profile_from_post(self, post):
        """Visite le profil de l'auteur d'un post."""
        if post.get("tap"):
            self.log("-> Visite profil @%s" % post.get("username", "?"))
            await self.d.ht.tap(post["tap"]["x"], post["tap"]["y"])
            await self.d.wait('transition')
            await asyncio.sleep(2)
            return True
        return False
