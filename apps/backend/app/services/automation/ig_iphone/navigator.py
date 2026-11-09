"""
ig_iphone/navigator.py — Navigation entre les ecrans IG (async).

Gere les transitions : feed, reels, explore, profile, stories, DM.
Detecte l'ecran actuel et navigue vers la cible.

Ported from VPS sync version to async.
"""

import asyncio
import random
from app.services.automation.ig_iphone.selectors import (
    sel, IG_BUNDLE,
    BOTTOM_BAR_Y, TAB_HOME_X, TAB_REELS_X, TAB_DM_X,
    TAB_EXPLORE_X, TAB_PROFILE_X,
    STORY_TAP_PREV_X, STORY_TAP_NEXT_X, STORY_TAP_Y,
)


class IGNavigator:
    """Navigation IG iOS (async)."""

    def __init__(self, driver, log=print):
        self.d = driver
        self.log = log

    # ── Lancement / Fermeture ─────────────────────────────────────────────

    async def open_instagram(self):
        """Lance IG et attend que le feed soit charge."""
        self.log("-> Ouverture Instagram")
        await self.d.ht.launch(IG_BUNDLE)
        await self.d.wait('transition')
        await asyncio.sleep(2)

        # Verifier qu'on est sur le feed (pas sur un ecran de login/popup)
        screen = await self.d.detect_current_screen()
        self.log(f"   ecran detecte: {screen}")

        # Dismiss popups courants (notifications, mise a jour, etc.)
        await self._dismiss_popups()

        return screen

    async def close_instagram(self):
        """Ferme IG."""
        await self.d.ht.kill(IG_BUNDLE)
        self.log("   IG ferme")

    # ── Navigation tabs ───────────────────────────────────────────────────

    async def _tap_tab(self, x_frac, label):
        """Tape sur un tab de la bottom bar."""
        self.log(f"-> Navigation: {label}")
        await self.d.tap_pos(x_frac, BOTTOM_BAR_Y)
        await self.d.wait('transition')
        await asyncio.sleep(1)

    async def go_home(self):
        """Va au feed principal. Double-tap pour remonter en haut."""
        screen = await self.d.detect_current_screen(refresh=True)
        if screen == 'feed':
            # Deja sur le feed → double tap pour remonter en haut
            self.log("   deja sur feed -> tap pour remonter")
            await self._tap_tab(TAB_HOME_X, "Home (reset)")
        else:
            await self._tap_tab(TAB_HOME_X, "Home")
        return await self._verify_screen('feed', fallback='feed')

    async def go_reels(self):
        """Va sur l'onglet Reels."""
        await self._tap_tab(TAB_REELS_X, "Reels")
        return await self._verify_screen('reels', fallback='reels')

    async def go_explore(self):
        """Va sur l'onglet Explorer."""
        await self._tap_tab(TAB_EXPLORE_X, "Explorer")
        await asyncio.sleep(1)
        return True

    async def go_dm(self):
        """Va sur les messages directs."""
        await self._tap_tab(TAB_DM_X, "DM")
        await asyncio.sleep(1)
        return True

    async def go_profile(self):
        """Va sur le profil du compte connecte."""
        await self._tap_tab(TAB_PROFILE_X, "Profil")
        return await self._verify_screen('own_profile', fallback='profile')

    async def go_back(self):
        """Retour arriere via swipe depuis le bord gauche (geste iOS natif)."""
        await self.d.ht._ensure_screen()
        # Swipe from left edge — geste iOS standard pour "retour"
        y = self.d.ht.screen_h * random.uniform(0.35, 0.55)
        await self.d.ht.swipe(
            5, y,                                          # depart = bord gauche
            self.d.ht.screen_w * 0.6, y + random.gauss(0, 5),  # arrivee = milieu
            random.randint(200, 350)
        )
        await self.d.wait('transition')

    # ── Stories ───────────────────────────────────────────────────────────

    async def open_stories(self, index=0):
        """Ouvre la story a l'index donne dans la barre de stories.

        index=0 → premiere story (la plus a gauche).
        """
        self.log(f"-> Ouverture story #{index}")
        el = await self.d.find_element(contains=sel('story_bar'))
        if not el:
            self.log("   ! barre des stories non trouvee")
            return False

        rect = el.get('rect', {})
        bar_x = rect.get('x', 0)
        bar_y = rect.get('y', 0)
        bar_w = rect.get('width', 375)
        bar_h = rect.get('height', 126)

        # La premiere icone (x=0-72) est "Votre story" (creer)
        # Les stories des amis commencent apres, ~76px chacune
        story_w = 76
        own_story_offset = 80   # skip le bouton Votre Story
        x = bar_x + own_story_offset + 38 + (index * story_w)
        y = bar_y + bar_h / 2

        await self.d.ht.tap(x, y)
        await self.d.wait('transition')
        await asyncio.sleep(1)
        return True

    async def story_next(self):
        """Avance a la story suivante (tap cote droit)."""
        await self.d.tap_pos(STORY_TAP_NEXT_X, STORY_TAP_Y)
        await self.d.wait('micro')

    async def story_prev(self):
        """Revient a la story precedente (tap cote gauche)."""
        await self.d.tap_pos(STORY_TAP_PREV_X, STORY_TAP_Y)
        await self.d.wait('micro')

    async def story_close(self):
        """Ferme les stories (swipe down)."""
        await self.d.ht.swipe(
            self.d.ht.screen_w * 0.5,
            self.d.ht.screen_h * 0.3,
            self.d.ht.screen_w * 0.5,
            self.d.ht.screen_h * 0.8,
            400
        )
        await self.d.wait('transition')

    # ── Navigation profil ─────────────────────────────────────────────────

    async def open_profile(self, username):
        """Ouvre le profil d'un utilisateur via deep link."""
        self.log(f"-> Ouverture profil @{username}")
        await self.d.ht.open_url(f"instagram://user?username={username}")
        await self.d.wait('transition')
        await asyncio.sleep(2)
        return True

    async def search_and_open_profile(self, username):
        """Ouvre un profil via Explorer → barre de recherche → tap resultat."""
        self.log(f"-> Recherche @{username} via Explorer")
        await self.go_explore()
        await asyncio.sleep(1)

        # Tap sur la barre de recherche
        search_el = await self.d.find_element(text="Rechercher", clickable=True)
        if not search_el:
            self.log("   ! barre de recherche non trouvee")
            return False
        tap = search_el.get('tap', {})
        await self.d.ht.tap(tap['x'], tap['y'])
        await self.d.wait('transition')
        await asyncio.sleep(1)

        # Taper le username
        await self.d.type_text(username, method="natural")
        await asyncio.sleep(2)

        # Trouver le bon resultat profil (pas les suggestions de recherche)
        results = await self.d.find_elements(contains=username, clickable=True, refresh=True)
        profile_results = []
        for r in results:
            text = (r.get('text', '') or '')
            rect = r.get('rect', {})
            y = rect.get('y', 0)
            h = rect.get('height', 0)
            # Ignorer : barre de recherche (y<100), clavier (y>500), trop petit
            if y < 100 or y > 500 or h < 40:
                continue
            profile_results.append(r)

        best = None
        # Priorite 1 : "compte vérifié" (profil certifie)
        for r in profile_results:
            text = (r.get('text', '') or '').lower()
            if 'vérifié' in text or 'verifie' in text:
                best = r
                break
        # Priorite 2 : contient une virgule (sous-titre = profil, pas suggestion)
        if not best:
            for r in profile_results:
                text = (r.get('text', '') or '')
                if ',' in text:
                    best = r
                    break
        # Priorite 3 : deuxieme resultat (le premier est souvent la suggestion texte)
        if not best and len(profile_results) >= 2:
            best = profile_results[1]
        # Fallback : premier resultat
        if not best and profile_results:
            best = profile_results[0]

        if not best:
            self.log("   ! aucun resultat pour @%s" % username)
            await self.d.tap_element(text="Annuler")
            return False

        tap = best.get('tap', {})
        self.log("   tap resultat '%s'" % (best.get('text', '')[:40]))
        await self.d.ht.tap(tap['x'], tap['y'])
        await self.d.wait('transition')
        await asyncio.sleep(2)
        return True

    # Safe zones for username taps
    _SAFE_TOP_FRAC = 0.135
    _SAFE_BOTTOM_FRAC = 0.86

    @property
    def _safe_top(self):
        return self.d.ht.screen_h * self._SAFE_TOP_FRAC

    @property
    def _safe_bottom(self):
        return self.d.ht.screen_h * self._SAFE_BOTTOM_FRAC

    async def _pick_username_el(self, username, post_y=None):
        """Element cliquable portant ce username, proche du post courant."""
        cands = []
        for e in (await self.d.find_elements(clickable=True, refresh=True) or []):
            txt = (e.get('text') or '').strip()
            if txt != username and ("Publication de " + username) not in txt:
                continue
            y = (e.get('tap') or {}).get('y')
            if y is None:
                continue
            if y < self._safe_top or y > self._safe_bottom:
                continue
            cands.append((e, y))
        if not cands:
            return None
        if post_y is None:
            return cands[0][0]
        cands.sort(key=lambda c: abs(c[1] - post_y))
        return cands[0][0]

    async def visit_from_post(self, username, post_y=None):
        """Ouvre le profil en tapant sur le username DU POST courant."""
        self.log(f"-> Tap @{username} depuis post")
        el = await self._pick_username_el(username, post_y=post_y)
        if el:
            tap = el.get('tap', {})
            self.log("   tap username y=%s" % tap.get('y'))
            await self.d.ht.tap(tap['x'], tap['y'])
            await self.d.wait('transition')
            await asyncio.sleep(2)
            return True
        self.log(f"   ! @{username} non trouve dans la zone du post")
        return False

    async def visit_from_reel(self, username):
        """Ouvre le profil en tapant sur le username d'un reel."""
        self.log(f"-> Tap @{username} depuis reel")
        el = await self.d.find_element(contains="Publication de " + username, clickable=True)
        if el:
            tap = el.get('tap', {})
            await self.d.ht.tap(tap['x'], tap['y'])
            await self.d.wait('transition')
            await asyncio.sleep(2)
            return True
        # Fallback : photo de profil
        el = await self.d.find_element(text=username, clickable=True)
        if el:
            tap = el.get('tap', {})
            await self.d.ht.tap(tap['x'], tap['y'])
            await self.d.wait('transition')
            await asyncio.sleep(2)
            return True
        self.log(f"   ! @{username} non trouve")
        return False

    # ── Popups / interstitiels ────────────────────────────────────────────

    POPUP_MARKERS = [
        "Présentation du partage de story",
        "partage de publications",
        "Activer les notifications",
        "Mise à jour disponible",
    ]

    async def _dismiss_popups(self):
        """Ferme les popups courants (notifications, mises a jour, etc.)."""
        dismiss_texts = [
            "Pas maintenant",
            "Not Now",
            "Plus tard",
            "Ignorer",
            "Annuler",
            "OK",
            "Refuser",
            "Non merci",
            "Continuer",
        ]
        for text in dismiss_texts:
            el = await self.d.find_element(text=text, refresh=True)
            if el:
                tap = el.get('tap', {})
                self.log(f"   popup dismiss: '{text}'")
                await self.d.ht.tap(tap.get('x', 0), tap.get('y', 0))
                await self.d.wait('tap')
                await self.d.refresh_elements()
                break

    # ── Verification ──────────────────────────────────────────────────────

    async def _verify_screen(self, expected, fallback=None, retries=2):
        """Verifie qu'on est bien sur l'ecran attendu."""
        for i in range(retries):
            await asyncio.sleep(0.5)
            screen = await self.d.detect_current_screen()
            if screen == expected:
                return True
            if screen == fallback:
                return True
        self.log(f"   ! ecran attendu '{expected}', detecte '{screen}'")
        return False

    # ── Retour au feed ────────────────────────────────────────────────────

    IG_BUNDLE_ID = "com.burbn.instagram"

    async def _on_feed(self, pause=0.8):
        await asyncio.sleep(pause)
        return await self.d.detect_current_screen(refresh=True) == 'feed'

    async def ensure_feed(self, log=None, allow_restart=True):
        """Ramene l'app sur le feed. Renvoie True si on y est.

        Escalade du plus doux au plus brutal, avec verification apres chaque
        etape. Remplace les recovery locales qui constataient l'echec sans
        jamais escalader.
        """
        log = log or self.log
        if await self.d.detect_current_screen(refresh=True) == 'feed':
            return True

        w = self.d.ht.screen_w
        h = self.d.ht.screen_h

        # 1. Un bouton de fermeture explicite ?
        if await self.d.tap_element(contains='Fermer'):
            log("   [feed] bouton Fermer")
            if await self._on_feed():
                return True

        # 2. Fermeture de feuille modale : swipe vers le bas.
        log("   [feed] swipe de fermeture")
        await self.d.ht.swipe(w * 0.5, h * 0.25, w * 0.5, h * 0.9, 420)
        if await self._on_feed(1.2):
            return True

        # 3. Retour arriere iOS : geste depuis le bord gauche.
        log("   [feed] geste retour depuis le bord")
        await self.d.ht.swipe(w * 0.02, h * 0.5, w * 0.6, h * 0.5, 350)
        if await self._on_feed(1.2):
            return True

        # 4. Onglet Fil principal.
        log("   [feed] onglet Fil principal")
        try:
            await self.go_home()
        except Exception as e:
            log("   [feed] go_home KO: %s" % str(e)[:60])
        if await self._on_feed(1.5):
            return True

        # 5. Dernier recours : relancer l'app.
        if not allow_restart:
            log("   [feed] echec, relance non autorisee")
            return False
        log("   [feed] !! relance de l'app (dernier recours)")
        try:
            await self.d.ht.kill(self.IG_BUNDLE_ID)
            await asyncio.sleep(2)
            await self.d.ht.launch(self.IG_BUNDLE_ID)
            await asyncio.sleep(6)
        except Exception as e:
            log("   [feed] relance KO: %s" % str(e)[:80])
            return False
        ok = await self._on_feed(2.0)
        log("   [feed] apres relance : %s" % ("feed OK" if ok else "toujours hors feed"))
        return ok

    async def where_am_i(self):
        """Retourne l'ecran actuel."""
        return await self.d.detect_current_screen()
