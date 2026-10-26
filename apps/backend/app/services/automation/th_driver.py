"""Async THDriver — high-level Threads UI driver.

Ported from VPS th_iphone/driver.py (THDriver). Wraps HumanTouch +
ScrollEngine to provide element finding, feed interaction, and
high-level Threads navigation.

Threads has a simpler UI than Instagram — fewer screens, no stories,
no reels, simpler post structure.
"""

import asyncio
import json
import logging
import random
import re
import time
import unicodedata
from typing import Callable

from app.services.automation.human_touch import HumanTouch
from app.services.automation.scroll_engine import ScrollEngine

logger = logging.getLogger("automation.th_driver")

# ── Constants ────────────────────────────────────────────────────────────────

TH_BUNDLE = "com.burbn.barcelona"

# Bottom navigation bar labels (Threads)
_NAV_HOME = "Home"
_NAV_SEARCH = "Search"
_NAV_POST = "New thread"
_NAV_ACTIVITY = "Activity"
_NAV_PROFILE = "Profile"

# Screen detection markers
_SCREEN_MARKERS = {
    "feed":       ["Home", "Threads"],
    "search":     ["Search"],
    "compose":    ["New thread", "Start a thread"],
    "activity":   ["Activity"],
    "profile":    ["Edit profile"],
    "post_view":  ["Reply"],
    "login":      ["Log in", "Connexion"],
}


class THDriver:
    """Async high-level Threads UI driver.

    Provides:
        - Element finding with Unicode normalization
        - Screen detection (feed, search, compose, profile, etc.)
        - Feed interaction (like, reply, repost)
        - Navigation helpers
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
        """Refresh the UI elements cache from MCP."""
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
        return self._elements_cache

    # ── Element finding ──────────────────────────────────────────────────

    def find_elements(
        self,
        text: str | None = None,
        *,
        contains: bool = False,
        clickable: bool = False,
    ) -> list[dict]:
        """Find elements in cache matching criteria."""
        results = []
        if text:
            needle = _normalize(text).lower()

        for el in self._elements_cache:
            if clickable and not el.get("clickable"):
                continue
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
        matches = self.find_elements(text, contains=contains, clickable=clickable)
        return matches[0] if matches else None

    async def tap_element(
        self,
        text: str,
        *,
        contains: bool = False,
        refresh: bool = True,
    ) -> bool:
        """Find and tap an element by text."""
        if refresh:
            await self.refresh_elements()

        el = self.find_element(text, contains=contains, clickable=True)
        if not el:
            el = self.find_element(text, contains=contains)
        if not el:
            self.log(f"   [th] élément '{text}' introuvable")
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
        """Wait for an element to appear."""
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

        Returns: 'feed', 'search', 'compose', 'activity',
                 'profile', 'post_view', 'login', 'other'
        """
        if refresh:
            await self.refresh_elements()

        texts_lower = set()
        for el in self._elements_cache:
            t = (el.get("text") or "").strip()
            if t:
                texts_lower.add(t.lower())

        for screen, markers in _SCREEN_MARKERS.items():
            hits = sum(1 for m in markers if m.lower() in texts_lower)
            if hits >= 1:
                return screen

        return "other"

    # ── Navigation ───────────────────────────────────────────────────────

    async def go_home(self) -> bool:
        return await self.tap_element(_NAV_HOME)

    async def go_search(self) -> bool:
        return await self.tap_element(_NAV_SEARCH)

    async def go_compose(self) -> bool:
        return await self.tap_element(_NAV_POST)

    async def go_activity(self) -> bool:
        return await self.tap_element(_NAV_ACTIVITY)

    async def go_profile(self) -> bool:
        return await self.tap_element(_NAV_PROFILE)

    # ── Feed interaction ─────────────────────────────────────────────────

    async def scroll_down(self):
        """Scroll feed down."""
        await self.ht.scroll_down()

    async def scroll_up(self):
        """Scroll feed up."""
        await self.ht.scroll_up()

    async def like_post(self) -> bool:
        """Double-tap to like the centered post."""
        await self.ht._ensure_screen()
        cx = self.ht.screen_w / 2
        cy = self.ht.screen_h * 0.4
        await self.ht.tap(cx, cy)
        await asyncio.sleep(random.uniform(0.08, 0.15))
        await self.ht.tap(cx, cy)
        return True

    async def tap_like_button(self) -> bool:
        return await self.tap_element("Like", contains=True)

    async def tap_reply_button(self) -> bool:
        return await self.tap_element("Reply", contains=True)

    async def tap_repost_button(self) -> bool:
        return await self.tap_element("Repost", contains=True)

    async def tap_share_button(self) -> bool:
        return await self.tap_element("Share", contains=True)

    # ── Compose ──────────────────────────────────────────────────────────

    async def compose_thread(self, text: str) -> bool:
        """Open compose and type a thread.

        Does NOT submit — call submit_thread() after.
        """
        ok = await self.go_compose()
        if not ok:
            return False
        await asyncio.sleep(1.0)

        # Tap the text input area
        await self.tap_element("Start a thread", contains=True, refresh=True)
        await asyncio.sleep(0.5)

        await self.ht.type_text(text)
        return True

    async def submit_thread(self) -> bool:
        """Submit the composed thread."""
        return await self.tap_element("Post")

    async def compose_reply(self, text: str) -> bool:
        """Type a reply in the reply sheet.

        Assumes reply sheet is already open (tap_reply_button called).
        """
        # Tap reply field
        await self.tap_element("Reply", contains=True, refresh=True)
        await asyncio.sleep(0.5)
        await self.ht.type_text(text)
        return True

    # ── Profile ──────────────────────────────────────────────────────────

    async def get_profile_stats(self) -> dict | None:
        """Extract profile stats (followers)."""
        await self.refresh_elements()
        screen = await self.detect_current_screen(refresh=False)
        if screen != "profile":
            return None

        stats = {}
        for el in self._elements_cache:
            text = (el.get("text") or "").strip()
            m = re.match(
                r"(\d[\d\s,.]*)\s*(followers?|following|abonnés|abonnements)",
                text,
                re.IGNORECASE,
            )
            if m:
                count = _parse_count(m.group(1))
                label = m.group(2).lower()
                if "follower" in label or "abonné" in label:
                    stats["followers"] = count
                elif "following" in label or "abonnement" in label:
                    stats["following"] = count

        return stats if stats else None

    # ── Timing ───────────────────────────────────────────────────────────

    async def wait(self, min_s: float = 0.5, max_s: float = 2.0):
        await self.ht.wait(min_s, max_s)

    async def reading_pause(self, text_length: int = 100):
        seconds = max(0.8, min(8.0, text_length / 1250 * 60))
        jitter = random.uniform(0.8, 1.3)
        await asyncio.sleep(seconds * jitter)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text)


def _parse_count(raw: str) -> int:
    s = raw.strip().replace(" ", "").replace("\xa0", "")
    s = s.replace(" ", "").replace(",", "").replace(".", "")
    try:
        return int(s)
    except ValueError:
        return 0
