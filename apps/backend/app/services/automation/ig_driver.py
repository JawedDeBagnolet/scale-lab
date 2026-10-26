"""Async IGDriver — high-level Instagram UI driver.

Ported from VPS ig_iphone/driver.py (IGDriver). Wraps HumanTouch +
ScrollEngine to provide element finding, post detection, feed parsing,
screen detection and high-level IG navigation.

The driver works with the MCP accessibility tree returned by get_ui_elements.
Each element has: type, text, x, y, width, height, clickable, value, traits.
"""

import asyncio
import json
import logging
import math
import random
import re
import time
import unicodedata
from typing import Any, Callable

from app.services.automation.human_touch import HumanTouch, BOTTOM_BAR_Y
from app.services.automation.scroll_engine import ScrollEngine

logger = logging.getLogger("automation.ig_driver")

# ── Constants ────────────────────────────────────────────────────────────────

IG_BUNDLE = "com.burbn.instagram"

# Bottom navigation bar labels (FR locale)
_NAV_HOME = "Accueil"
_NAV_SEARCH = "Rechercher"
_NAV_REELS = "Reels"
_NAV_SHOP = "Boutique"
_NAV_PROFILE = "Profil"

# Screen detection markers
_SCREEN_MARKERS = {
    "feed":        ["Accueil", "Instagram"],
    "reels":       ["Reels"],
    "own_profile": ["Modifier le profil", "Modifier profil"],
    "post_view":   ["Ajouter un commentaire"],
    "explore":     ["Rechercher"],
    "story":       ["Votre story", "story"],
    "login":       ["Connexion", "Se connecter", "Log In"],
}

# Post markers in accessibility tree
_POST_VIDEO_RE = re.compile(r"(?:Vidéo|Video) (?:de|by) (.+)", re.IGNORECASE)
_POST_PHOTO_RE = re.compile(r"(?:Photo|Image) (?:de|by) (.+)", re.IGNORECASE)
_LIKE_COUNT_RE = re.compile(r"(\d[\d\s,.]*)\s*(?:J'aime|like|mention)", re.IGNORECASE)
_COMMENT_COUNT_RE = re.compile(
    r"(?:Afficher|voir|View)\s+(?:les\s+)?(\d[\d\s,.]*)\s*comment", re.IGNORECASE
)

# Hold points for zero-velocity lift (prevents iOS inertia)
HOLD_POINTS = 4


class IGDriver:
    """Async high-level Instagram UI driver.

    Provides:
        - Element finding with Unicode normalization
        - Post detection and centering
        - Screen detection (feed, reels, profile, etc.)
        - Calibrated scrolling via ScrollEngine
        - Feed interaction helpers
    """

    def __init__(
        self,
        mcp_port: int = 8190,
        *,
        host: str = "127.0.0.1",
        log: Callable = logger.info,
    ):
        self.ht = HumanTouch(mcp_port, host=host, log=log)
        self.scroll = ScrollEngine(self.ht, log=log)
        self.log = log

        # Element cache
        self._elements_cache: list[dict] = []
        self._cache_age: float = 0

    # ── Element access ───────────────────────────────────────────────────

    async def refresh_elements(
        self,
        *,
        clickable_only: bool = False,
        max_elements: int = 150,
        max_age: float = 0,
    ) -> list[dict]:
        """Refresh the UI elements cache from MCP.

        Args:
            clickable_only: only return clickable elements
            max_elements: cap on elements returned
            max_age: skip refresh if cache is younger than this (seconds)
        """
        now = time.monotonic()
        if max_age > 0 and (now - self._cache_age) < max_age:
            return self._elements_cache

        self._elements_cache = await self.ht.get_elements(
            clickable_only=clickable_only,
            max_elements=max_elements,
        )
        self._cache_age = now
        return self._elements_cache

    @property
    def elements(self) -> list[dict]:
        """Current cached elements (call refresh_elements first)."""
        return self._elements_cache

    # ── Element finding ──────────────────────────────────────────────────

    def find_elements(
        self,
        text: str | None = None,
        *,
        contains: bool = False,
        clickable: bool = False,
        element_type: str | None = None,
    ) -> list[dict]:
        """Find elements in the cache matching criteria.

        Uses Unicode NFKD normalization for accent-insensitive matching.
        """
        results = []
        if text:
            needle = _normalize(text).lower()

        for el in self._elements_cache:
            # Filter by clickable
            if clickable and not el.get("clickable"):
                continue
            # Filter by type
            if element_type and el.get("type") != element_type:
                continue
            # Filter by text
            if text:
                el_text = _normalize(el.get("text") or "").lower()
                if contains:
                    if needle not in el_text:
                        continue
                else:
                    if el_text != needle:
                        continue
            results.append(el)

        return results

    def find_element(
        self,
        text: str,
        *,
        contains: bool = False,
        clickable: bool = False,
    ) -> dict | None:
        """Find first matching element or None."""
        matches = self.find_elements(
            text, contains=contains, clickable=clickable
        )
        return matches[0] if matches else None

    async def tap_element(
        self,
        text: str,
        *,
        contains: bool = False,
        refresh: bool = True,
    ) -> bool:
        """Find and tap an element by text. Returns True if found and tapped."""
        if refresh:
            await self.refresh_elements()

        el = self.find_element(text, contains=contains, clickable=True)
        if not el:
            # Try without clickable filter
            el = self.find_element(text, contains=contains)

        if not el:
            self.log(f"   [ig] élément '{text}' introuvable")
            return False

        x = el.get("x", 0)
        y = el.get("y", 0)
        w = el.get("width", 0)
        h = el.get("height", 0)

        bounds = (w, h) if w > 0 and h > 0 else None
        await self.ht.tap(x, y, bounds=bounds)
        return True

    async def wait_for_element(
        self,
        text: str,
        *,
        contains: bool = False,
        timeout: float = 10,
        interval: float = 1.0,
    ) -> dict | None:
        """Wait for an element to appear. Returns it or None on timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await self.refresh_elements()
            el = self.find_element(text, contains=contains)
            if el:
                return el
            await asyncio.sleep(interval)
        return None

    # ── Screen detection ─────────────────────────────────────────────────

    async def detect_current_screen(self, *, refresh: bool = True) -> str:
        """Detect the current visible screen.

        Returns one of: 'feed', 'reels', 'own_profile', 'post_view',
        'explore', 'story', 'login', 'profile', 'other'
        """
        if refresh:
            await self.refresh_elements()

        texts_lower = set()
        for el in self._elements_cache:
            t = (el.get("text") or "").strip()
            if t:
                texts_lower.add(t.lower())

        # Check each screen type's markers
        for screen, markers in _SCREEN_MARKERS.items():
            hits = sum(
                1 for m in markers if m.lower() in texts_lower
            )
            if hits >= 1:
                # For own_profile, require "Modifier" marker
                if screen == "own_profile":
                    return screen
                # For feed, also check we're NOT in a sub-screen
                if screen == "feed":
                    # If "Ajouter un commentaire" is present, it's post_view
                    if any("commentaire" in t for t in texts_lower):
                        continue
                    return screen
                return screen

        # Check if we see a non-self profile
        for el in self._elements_cache:
            t = el.get("text") or ""
            if re.search(r"\d+\s*(publications?|posts?)", t, re.IGNORECASE):
                return "profile"

        return "other"

    # ── Post detection ───────────────────────────────────────────────────

    async def detect_visible_posts(
        self, *, refresh: bool = True
    ) -> list[dict]:
        """Detect posts visible on screen from the accessibility tree.

        Returns a list of post dicts with:
            username, type (video/photo), y, like_count, comment_count,
            share_element
        """
        if refresh:
            await self.refresh_elements()

        raw_posts = []
        for el in self._elements_cache:
            text = el.get("text") or ""
            y = el.get("y", 0)

            # Video marker
            m = _POST_VIDEO_RE.match(text)
            if m:
                raw_posts.append({
                    "username": m.group(1).strip(),
                    "type": "video",
                    "y": y,
                    "el": el,
                })
                continue

            # Photo marker
            m = _POST_PHOTO_RE.match(text)
            if m:
                raw_posts.append({
                    "username": m.group(1).strip(),
                    "type": "photo",
                    "y": y,
                    "el": el,
                })
                continue

        # Merge duplicate entries (header + media markers for same post)
        posts = self._merge_post_entries(raw_posts)

        # Enrich with like/comment counts
        for post in posts:
            post["like_count"] = self._extract_like_count(post["y"])
            post["comment_count"] = self._extract_comment_count(post["y"])

        return posts

    def _merge_post_entries(self, raw: list[dict]) -> list[dict]:
        """Merge duplicate post entries that are close in Y position."""
        if not raw:
            return []

        # Sort by Y
        raw.sort(key=lambda p: p["y"])
        merged = [raw[0]]

        for post in raw[1:]:
            prev = merged[-1]
            # Same user within 100px → same post
            if (
                post["username"] == prev["username"]
                and abs(post["y"] - prev["y"]) < 100
            ):
                # Keep the one with the media type
                if post["type"] != prev["type"]:
                    prev["type"] = post["type"]
                continue
            merged.append(post)

        # Clean up
        for p in merged:
            p.pop("el", None)

        return merged

    def _extract_like_count(self, post_y: float) -> int | None:
        """Extract like count from elements near a post's Y position."""
        for el in self._elements_cache:
            text = el.get("text") or ""
            el_y = el.get("y", 0)
            # Look within 200px below the post marker
            if 0 < (el_y - post_y) < 200:
                m = _LIKE_COUNT_RE.search(text)
                if m:
                    return _parse_count(m.group(1))
        return None

    def _extract_comment_count(self, post_y: float) -> int | None:
        """Extract comment count from elements near a post's Y position."""
        for el in self._elements_cache:
            text = el.get("text") or ""
            el_y = el.get("y", 0)
            if 0 < (el_y - post_y) < 250:
                m = _COMMENT_COUNT_RE.search(text)
                if m:
                    return _parse_count(m.group(1))
        return None

    # ── Post centering ───────────────────────────────────────────────────

    async def center_post(
        self,
        post: dict,
        *,
        target_y: float | None = None,
        attempts: int = 6,
        tolerance: float = 30,
    ) -> bool:
        """Center a post vertically on screen.

        Uses iterative drag gestures with zero-velocity hold points
        at the end to prevent iOS inertia scroll.

        Args:
            post: post dict from detect_visible_posts (needs 'username')
            target_y: desired Y center (default: screen center)
            attempts: max correction attempts
            tolerance: pixel tolerance for "centered"

        Returns True if successfully centered.
        """
        await self.ht._ensure_screen()
        if target_y is None:
            target_y = self.ht.screen_h * 0.42  # slightly above center

        for attempt in range(attempts):
            await self.refresh_elements()
            posts = await self.detect_visible_posts(refresh=False)

            # Find our target post
            target = None
            for p in posts:
                if p["username"] == post["username"]:
                    target = p
                    break

            if not target:
                self.log(f"   [ig] post de {post['username']} disparu après scroll")
                return False

            delta = target["y"] - target_y
            if abs(delta) < tolerance:
                return True

            # Precise drag to center
            x = self.ht.screen_w * random.uniform(0.35, 0.65)
            start_y = self.ht.screen_h * 0.5
            end_y = start_y - delta * 0.8  # slight undershoot

            # Build points with hold at end
            points = self.ht._build_swipe_points(
                x, start_y, x, end_y,
                random.randint(25, 40),
            )
            await self.ht.drag(
                points,
                hold_duration=80,
                move_duration=random.randint(600, 1000),
            )

            await asyncio.sleep(0.4)

        return False

    # ── Scrolling ────────────────────────────────────────────────────────

    async def scroll_down(self):
        """Scroll feed down one "page"."""
        await self.ht.scroll_down()

    async def scroll_up(self):
        """Scroll feed up one "page"."""
        await self.ht.scroll_up()

    async def scroll_to_y(
        self,
        target_y: float,
        *,
        probe_element: str | None = None,
        max_scrolls: int = 20,
    ) -> bool:
        """Scroll until a known element reaches target_y.

        Uses ScrollEngine for calibrated scrolling with feedback.
        """
        for _ in range(max_scrolls):
            await self.refresh_elements()

            if probe_element:
                el = self.find_element(probe_element, contains=True)
                if not el:
                    return False
                current_y = el.get("y", 0)
            else:
                return False

            delta = current_y - target_y
            if abs(delta) < 20:
                return True

            old_y = current_y
            await self.scroll.scroll_by(delta)
            await asyncio.sleep(0.5)

            # Re-probe to feed ScrollEngine
            await self.refresh_elements()
            el = self.find_element(probe_element, contains=True)
            if el:
                new_y = el.get("y", 0)
                actual = old_y - new_y
                if abs(actual) > 3:
                    self.scroll.observe(delta, actual)

        return False

    # ── Navigation ───────────────────────────────────────────────────────

    async def go_home(self) -> bool:
        """Navigate to the feed/home tab."""
        return await self.tap_element(_NAV_HOME)

    async def go_search(self) -> bool:
        """Navigate to the search/explore tab."""
        return await self.tap_element(_NAV_SEARCH)

    async def go_reels(self) -> bool:
        """Navigate to the reels tab."""
        return await self.tap_element(_NAV_REELS)

    async def go_profile(self) -> bool:
        """Navigate to own profile tab."""
        return await self.tap_element(_NAV_PROFILE)

    async def open_post(self, post: dict) -> bool:
        """Tap on a post to open its detail view."""
        username = post.get("username", "")
        text = f"Photo de {username}"
        if post.get("type") == "video":
            text = f"Vidéo de {username}"
        return await self.tap_element(text, contains=True)

    # ── Feed interaction helpers ─────────────────────────────────────────

    async def like_post(self) -> bool:
        """Double-tap to like the centered post."""
        await self.ht._ensure_screen()
        cx = self.ht.screen_w / 2
        cy = self.ht.screen_h * 0.4
        # Double tap
        await self.ht.tap(cx, cy)
        await asyncio.sleep(random.uniform(0.08, 0.15))
        await self.ht.tap(cx, cy)
        return True

    async def tap_like_button(self) -> bool:
        """Tap the like (heart) button."""
        return await self.tap_element("J'aime", contains=True)

    async def tap_comment_button(self) -> bool:
        """Tap the comment button."""
        return await self.tap_element("Commenter", contains=True)

    async def tap_share_button(self) -> bool:
        """Tap the share button."""
        return await self.tap_element("Partager", contains=True)

    async def tap_save_button(self) -> bool:
        """Tap the save/bookmark button."""
        return await self.tap_element("Enregistrer", contains=True)

    async def type_comment(self, text: str) -> bool:
        """Type a comment in the comment field."""
        # Tap comment field
        tapped = await self.tap_element(
            "Ajouter un commentaire", contains=True
        )
        if not tapped:
            return False
        await asyncio.sleep(0.5)
        await self.ht.type_text(text)
        return True

    async def submit_comment(self) -> bool:
        """Submit the typed comment."""
        return await self.tap_element("Publier")

    async def follow_user(self) -> bool:
        """Tap the follow button."""
        return await self.tap_element("Suivre")

    # ── Profile actions ──────────────────────────────────────────────────

    async def get_profile_stats(self) -> dict | None:
        """Extract profile stats from own profile screen.

        Returns dict with posts, followers, following counts or None.
        """
        await self.refresh_elements()
        screen = await self.detect_current_screen(refresh=False)
        if screen not in ("own_profile", "profile"):
            return None

        stats = {}
        for el in self._elements_cache:
            text = (el.get("text") or "").strip()
            # Look for patterns like "123 publications"
            m = re.match(
                r"(\d[\d\s,.]*)\s*(publications?|posts?|abonnés|followers|abonnements|following|suivi)",
                text,
                re.IGNORECASE,
            )
            if m:
                count = _parse_count(m.group(1))
                label = m.group(2).lower()
                if "publication" in label or "post" in label:
                    stats["posts"] = count
                elif "abonné" in label or "follower" in label:
                    stats["followers"] = count
                elif "abonnement" in label or "following" in label or "suivi" in label:
                    stats["following"] = count

        return stats if stats else None

    # ── Story helpers ────────────────────────────────────────────────────

    async def open_story(self, username: str | None = None) -> bool:
        """Open a story (own story if username is None)."""
        if username:
            return await self.tap_element(username, contains=True)
        return await self.tap_element("Votre story", contains=True)

    async def next_story(self):
        """Tap right side to advance story."""
        await self.ht._ensure_screen()
        await self.ht.tap(
            self.ht.screen_w * 0.85,
            self.ht.screen_h * 0.45,
        )

    async def prev_story(self):
        """Tap left side to go back in story."""
        await self.ht._ensure_screen()
        await self.ht.tap(
            self.ht.screen_w * 0.15,
            self.ht.screen_h * 0.45,
        )

    async def close_story(self):
        """Swipe down to close story."""
        await self.ht._ensure_screen()
        await self.ht.swipe(
            self.ht.screen_w * 0.5,
            self.ht.screen_h * 0.3,
            self.ht.screen_w * 0.5,
            self.ht.screen_h * 0.9,
            duration=500,
        )

    # ── Timing ───────────────────────────────────────────────────────────

    async def wait(self, min_s: float = 0.5, max_s: float = 2.0):
        """Human-like pause."""
        await self.ht.wait(min_s, max_s)

    async def reading_pause(self, text_length: int = 100):
        """Simulate reading time based on text length."""
        # ~250 words/minute, ~5 chars/word → ~1250 chars/minute
        seconds = max(0.8, min(8.0, text_length / 1250 * 60))
        jitter = random.uniform(0.8, 1.3)
        await asyncio.sleep(seconds * jitter)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Unicode NFKD normalization for accent-insensitive matching."""
    return unicodedata.normalize("NFKD", text)


def _parse_count(raw: str) -> int:
    """Parse a human-formatted count (1 234, 1,234, 1.2k, etc.)."""
    s = raw.strip().replace(" ", "").replace("\xa0", "")
    s = s.replace(" ", "").replace(",", "").replace(".", "")
    try:
        return int(s)
    except ValueError:
        return 0
