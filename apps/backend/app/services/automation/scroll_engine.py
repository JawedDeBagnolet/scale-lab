"""Async ScrollEngine — calibrated scrolling with feedback loop.

Ported from VPS scroll_engine.py. Wraps HumanTouch to provide
pixel-precise scrolling with continuous ratio calibration.

The engine learns the ratio between requested scroll distance and
actual screen displacement by observing element position changes
before and after each scroll, then adjusts future scrolls accordingly.
"""

import asyncio
import logging
import random
from typing import Callable

from app.services.automation.human_touch import HumanTouch

logger = logging.getLogger("automation.scroll")

# Default scroll ratio (requested px → actual px)
_DEFAULT_RATIO = 1.0
# Bounds on the learned ratio
_MIN_RATIO = 0.3
_MAX_RATIO = 3.0
# Smoothing factor for ratio updates (EMA)
_ALPHA = 0.3


class ScrollEngine:
    """Calibrated scroll with feedback loop.

    Usage:
        se = ScrollEngine(ht)
        # scroll ~400px down
        await se.scroll_by(400)
        # observe what actually happened (from element tracking)
        se.observe(requested=400, actual=320)
        # next scroll auto-compensates
        await se.scroll_by(400)  # will overshoot slightly to hit 400 real px
    """

    def __init__(
        self,
        ht: HumanTouch,
        *,
        log: Callable = logger.info,
    ):
        self.ht = ht
        self.log = log
        self._ratio = _DEFAULT_RATIO
        self._observations = 0

    @property
    def ratio(self) -> float:
        """Current calibration ratio (requested / actual)."""
        return self._ratio

    def observe(self, requested: float, actual: float):
        """Feed back an observation to refine the scroll ratio.

        Called after a scroll with the requested delta and the
        measured actual delta (from element position tracking).
        """
        if abs(actual) < 5:
            return  # ignore near-zero observations (noise)

        observed_ratio = requested / actual if actual != 0 else _DEFAULT_RATIO
        observed_ratio = max(_MIN_RATIO, min(_MAX_RATIO, observed_ratio))

        if self._observations == 0:
            # First observation → adopt directly
            self._ratio = observed_ratio
        else:
            # Exponential moving average
            self._ratio = _ALPHA * observed_ratio + (1 - _ALPHA) * self._ratio

        self._observations += 1
        self.log(
            f"   [scroll] observe {requested:.0f}/{actual:.0f} "
            f"→ ratio={self._ratio:.3f} (n={self._observations})"
        )

    async def scroll_by(
        self,
        delta: float,
        *,
        duration: int | None = None,
        steps: int | None = None,
    ):
        """Scroll by `delta` pixels (positive = down, negative = up).

        The actual swipe distance is adjusted by the learned ratio
        to compensate for iOS scroll physics.
        """
        await self.ht._ensure_screen()

        # Apply calibration ratio
        adjusted = delta * self._ratio

        screen_h = self.ht.screen_h
        screen_w = self.ht.screen_w

        # Pick config based on direction
        if delta > 0:
            cfg = self.ht.SCROLL_DOWN
            # Start high, end low (finger moves up)
            start_y = screen_h * random.uniform(0.65, 0.78)
            end_y = start_y - abs(adjusted)
            # Clamp to screen bounds
            end_y = max(screen_h * 0.08, end_y)
        else:
            cfg = self.ht.SCROLL_UP
            # Start low, end high (finger moves down)
            start_y = screen_h * random.uniform(0.25, 0.38)
            end_y = start_y + abs(adjusted)
            # Clamp to screen bounds
            end_y = min(screen_h * 0.92, end_y)

        # Lateral position with slight drift
        x = screen_w * random.uniform(0.3, 0.7)
        drift = random.uniform(cfg["drift_min"], cfg["drift_max"])
        end_x = x + (screen_w * drift * random.choice([-1, 1]))

        if duration is None:
            duration = random.randint(cfg["dur_min"], cfg["dur_max"])
        if steps is None:
            steps = random.randint(cfg["pts_min"], cfg["pts_max"])

        await self.ht.swipe(
            x, start_y, end_x, end_y,
            duration=duration,
            steps=steps,
        )

    async def wait_settled(
        self,
        probe_fn: Callable,
        *,
        max_wait: float = 2.0,
        interval: float = 0.3,
        threshold: float = 3.0,
    ) -> bool:
        """Wait until the screen settles (no more scroll momentum).

        Args:
            probe_fn: async callable returning a y-coordinate to track
                      (e.g., position of a known element). Returns None
                      if the element is not found.
            max_wait: maximum seconds to wait
            interval: polling interval
            threshold: pixel threshold for "settled"

        Returns True if settled, False if timed out.
        """
        prev_y = await probe_fn()
        if prev_y is None:
            return True  # nothing to track

        elapsed = 0.0
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            curr_y = await probe_fn()
            if curr_y is None:
                return True  # element gone → treat as settled
            if abs(curr_y - prev_y) < threshold:
                return True  # stable
            prev_y = curr_y

        return False  # timed out

    def reset(self):
        """Reset calibration to defaults."""
        self._ratio = _DEFAULT_RATIO
        self._observations = 0
