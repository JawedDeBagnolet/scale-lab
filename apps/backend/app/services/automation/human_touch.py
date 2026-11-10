"""Async HumanTouch — realistic touch simulation via MCP JSON-RPC.

Ported from VPS human_touch.py. Wraps the on-device MCP accessibility
server with realistic touch, swipe, type and scroll actions.

The MCP server on the iPhone (ios-mcp fork, port 8090) exposes:
    POST /mcp — JSON-RPC with tools/call method:
        - tap_screen {x, y}: single touch at coordinates
        - tap_element {text, match?}: tap element by accessibility text
        - swipe_screen {fromX, fromY, toX, toY, duration, steps}: swipe
        - drag_and_drop {points, hold_duration, move_duration, steps}: multi-point gesture
        - long_press {x, y, duration}: long press
        - get_ui_elements {clickable_only?, max_elements?}: accessibility tree
        - get_screen_info: screen dimensions
        - type_text {text, interval?}: keyboard input (character by character)
        - input_text {text}: replace focused field text
        - launch_app {bundle_id}: open app
        - kill_app {bundle_id}: terminate app
        - screenshot: PNG base64 capture
        - ocr_screen: text recognition
        - run_command {command}: shell command on iPhone

All methods are called via dispatch.mcp_call() which handles the
HTTP transport and timeout management.
"""

import asyncio
import json
import logging
import math
import random
import time
from typing import Any, Callable

from app.services.dispatch import mcp_call

logger = logging.getLogger("automation.touch")

# ── Screen constants (iPhone X / 11 / 12 / 13 / 14 / 15) ────────────────────
DEFAULT_SCREEN_W = 375
DEFAULT_SCREEN_H = 812
BOTTOM_BAR_Y = 780  # safe zone above home indicator


class HumanTouch:
    """Async MCP wrapper with realistic touch simulation.

    Provides tap, swipe, type and scroll with human-like timing,
    gaussian position variance, and natural gesture curves.
    """

    # Scroll config — calibrated for IG feed (posts ~500-600px tall)
    SCROLL_DOWN = {
        "dist_min": 0.40, "dist_max": 0.85,    # fraction of screen height
        "dur_min":  600,  "dur_max": 1800,      # ms
        "drift_min": 0.05, "drift_max": 0.25,   # lateral drift fraction
        "pts_min":  35,   "pts_max": 80,         # touch points in gesture
    }
    SCROLL_UP = {
        "dist_min": 0.25, "dist_max": 0.60,
        "dur_min":  600,  "dur_max": 1200,
        "drift_min": 0.02, "drift_max": 0.12,
        "pts_min":  30,   "pts_max": 55,
    }

    def __init__(
        self,
        mcp_port: int = 8190,
        *,
        host: str = "127.0.0.1",
        log: Callable = logger.info,
    ):
        self.mcp_port = mcp_port
        self.host = host
        self.log = log
        self.screen_w = DEFAULT_SCREEN_W
        self.screen_h = DEFAULT_SCREEN_H
        self._screen_checked = False

    # ── RealTouchInject (RTI) — enrichissement force/radius/motion ──────
    RTI_PORT = 8195

    async def _rti_call(self, endpoint: str, data: dict | None = None):
        """Call RealTouchInject HTTP API via MCP run_command + curl on-device.

        RTI runs on port 8195 on the iPhone. Since it's not tunneled,
        we reach it by running curl on the device through ios-mcp's run_command.
        Non-critical: failures are silently ignored (RTI tap enrichment is automatic).
        """
        try:
            import json as _json
            if data:
                payload = _json.dumps(data).replace("'", "'\\''")
                cmd = (
                    f"curl -s --max-time 3 -X POST http://127.0.0.1:{self.RTI_PORT}{endpoint} "
                    f"-H 'Content-Type: application/json' -d '{payload}'"
                )
            else:
                cmd = f"curl -s --max-time 3 http://127.0.0.1:{self.RTI_PORT}{endpoint}"
            await self._call("run_command", {"command": cmd}, timeout=5)
        except Exception:
            pass  # RTI enrichment is automatic for taps, this is best-effort

    async def signal_scroll(self, duration_ms: int):
        """Signal RTI that a scroll is starting so it uses progressive force profile."""
        await self._rti_call("/scroll", {"duration_ms": duration_ms})

    async def change_posture(self, posture_id: int | None = None):
        """Change RTI simulated posture (0=assis, 1=dos, 2=côté, 3=debout, 4=bureau).

        If posture_id is None, picks a random one.
        """
        data = {"id": posture_id} if posture_id is not None else {}
        await self._rti_call("/posture", data)

    async def rti_health(self) -> dict | None:
        """Check RTI health. Returns parsed JSON or None."""
        try:
            import json as _json
            cmd = f"curl -s --max-time 3 http://127.0.0.1:{self.RTI_PORT}/health"
            result = await self._call("run_command", {"command": cmd}, timeout=5)
            if result:
                content = result.get("content", [])
                if content and isinstance(content, list):
                    return _json.loads(content[0].get("text", "{}"))
        except Exception:
            pass
        return None

    # ── Low-level MCP call ───────────────────────────────────────────────

    async def _call(
        self,
        method: str,
        arguments: dict | None = None,
        *,
        timeout: float = 30,
    ) -> dict | None:
        """Call an MCP tool method via JSON-RPC.

        The MCP server uses the format:
            {"method": "tools/call", "params": {"name": "<method>", "arguments": {...}}}
        """
        result = await mcp_call(
            self.mcp_port,
            method,
            params=arguments or {},
            timeout=timeout,
            host=self.host,
        )
        return result

    async def _ensure_screen(self):
        """Ensure screen dimensions are known."""
        if self._screen_checked:
            return
        # Try to get screen info from MCP
        result = await self._call("get_screen_info", timeout=5)
        if result:
            try:
                content = result.get("content", [{}])
                if content and isinstance(content, list):
                    data = json.loads(content[0].get("text", "{}"))
                    if data.get("width"):
                        self.screen_w = data["width"]
                    if data.get("height"):
                        self.screen_h = data["height"]
            except Exception:
                pass
        self._screen_checked = True

    # ── Element reading ──────────────────────────────────────────────────

    async def get_elements(
        self,
        clickable_only: bool = False,
        max_elements: int = 150,
    ) -> list[dict]:
        """Get the UI accessibility tree from MCP."""
        result = await self._call("get_ui_elements", {
            "clickable_only": clickable_only,
            "max_elements": max_elements,
        })
        if not result:
            return []
        try:
            content = result.get("content", [])
            if content and isinstance(content, list):
                raw = content[0].get("text", "")
                data = json.loads(raw)
                return data.get("elements", [])
        except Exception:
            pass
        return []

    # ── Tap ──────────────────────────────────────────────────────────────

    async def tap(
        self,
        x: float,
        y: float,
        *,
        bounds: tuple[float, float] | None = None,
        duration: int | None = None,
    ):
        """Tap at (x, y) with optional gaussian jitter within bounds.

        Args:
            x, y: center coordinates
            bounds: (width, height) of the element — tap is scattered
                    within with gaussian distribution
            duration: tap hold duration in ms (default: realistic random)
        """
        if bounds:
            w, h = bounds
            # Gaussian scatter within element bounds (sigma = 1/4 of extent)
            x += random.gauss(0, w / 4)
            y += random.gauss(0, h / 4)
            # Clamp to element bounds
            x = max(x - w / 2, min(x + w / 2, x))
            y = max(y - h / 2, min(y + h / 2, y))

        if duration is None:
            duration = random.randint(50, 120)

        await self._call("tap_screen", {
            "x": round(x, 1),
            "y": round(y, 1),
        })

    async def tap_pos(self, x_frac: float, y_frac: float):
        """Tap at a relative screen position (fractions 0-1)."""
        await self._ensure_screen()
        await self.tap(self.screen_w * x_frac, self.screen_h * y_frac)

    # ── Swipe / Scroll ───────────────────────────────────────────────────

    async def swipe(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        *,
        duration: int = 800,
        steps: int = 40,
    ):
        """Swipe from start to end with realistic curve."""
        points = self._build_swipe_points(
            start_x, start_y, end_x, end_y, steps
        )
        await self._call("drag_and_drop", {
            "points": points,
            "hold_duration": 80,
            "move_duration": duration,
            "steps": steps,
        })

    async def scroll_down(self, config: dict | None = None):
        """Scroll down with realistic parameters."""
        await self._ensure_screen()
        cfg = config or self.SCROLL_DOWN
        dist = random.uniform(cfg["dist_min"], cfg["dist_max"])
        dur = random.randint(cfg["dur_min"], cfg["dur_max"])
        drift = random.uniform(cfg["drift_min"], cfg["drift_max"])
        pts = random.randint(cfg["pts_min"], cfg["pts_max"])

        # Signal RTI: switch to scroll force profile (progressive ramp)
        await self.signal_scroll(dur)

        x = self.screen_w * random.uniform(0.3, 0.7)
        start_y = self.screen_h * random.uniform(0.65, 0.80)
        end_y = start_y - (self.screen_h * dist)
        end_x = x + (self.screen_w * drift * random.choice([-1, 1]))

        await self.swipe(x, start_y, end_x, end_y, duration=dur, steps=pts)

    async def scroll_up(self, config: dict | None = None):
        """Scroll up with realistic parameters."""
        await self._ensure_screen()
        cfg = config or self.SCROLL_UP
        dist = random.uniform(cfg["dist_min"], cfg["dist_max"])
        dur = random.randint(cfg["dur_min"], cfg["dur_max"])
        drift = random.uniform(cfg["drift_min"], cfg["drift_max"])
        pts = random.randint(cfg["pts_min"], cfg["pts_max"])

        # Signal RTI: switch to scroll force profile (progressive ramp)
        await self.signal_scroll(dur)

        x = self.screen_w * random.uniform(0.3, 0.7)
        start_y = self.screen_h * random.uniform(0.25, 0.40)
        end_y = start_y + (self.screen_h * dist)
        end_x = x + (self.screen_w * drift * random.choice([-1, 1]))

        await self.swipe(x, start_y, end_x, end_y, duration=dur, steps=pts)

    # ── Drag (precise) ───────────────────────────────────────────────────

    async def drag(
        self,
        points: list[dict],
        *,
        hold_duration: int = 90,
        move_duration: int = 1200,
        steps: int | None = None,
    ):
        """Execute a precise drag gesture along given points."""
        if steps is None:
            steps = len(points)
        await self._call("drag_and_drop", {
            "points": points,
            "hold_duration": hold_duration,
            "move_duration": move_duration,
            "steps": steps,
        })

    # ── Type ─────────────────────────────────────────────────────────────

    async def type_text(self, text: str, *, interval: int | None = None, realistic: bool = True):
        """Type text via the keyboard with realistic inter-key timing.

        If realistic=True (default), types character by character with
        variable speed: fast on letters, slower on digits/symbols,
        with occasional hesitations.
        If realistic=False, sends the whole text at once (faster).
        """
        if not realistic:
            if interval is None:
                interval = random.randint(30, 80)
            await self._call("type_text", {"text": text, "interval": interval})
            return

        # Realistic mode: character by character with variable timing
        for i, char in enumerate(text):
            # Base interval depends on character type
            if char.isalpha():
                base = random.randint(35, 75)
            elif char.isdigit():
                base = random.randint(70, 130)
            else:  # symbols, dots, underscores
                base = random.randint(90, 160)

            # Occasional hesitation (5% chance, not on first char)
            if random.random() < 0.05 and i > 0:
                await asyncio.sleep(random.uniform(0.2, 0.8))

            # Occasional speed burst (10% chance for 2-4 chars)
            if random.random() < 0.10:
                base = max(20, base - random.randint(15, 30))

            await self._call("type_text", {"text": char, "interval": base})
            await asyncio.sleep(base / 1000)

    # ── App lifecycle ────────────────────────────────────────────────────

    async def launch_app(self, bundle: str):
        """Launch an app by bundle ID."""
        await self._call("launch_app", {"bundle_id": bundle})

    async def terminate_app(self, bundle: str):
        """Terminate an app by bundle ID."""
        await self._call("kill_app", {"bundle_id": bundle})

    # ── Internal helpers ─────────────────────────────────────────────────

    def _build_swipe_points(
        self,
        sx: float,
        sy: float,
        ex: float,
        ey: float,
        n_pts: int,
    ) -> list[dict]:
        """Build a realistic curved swipe trajectory."""
        points = []
        # Slight arc — random perpendicular offset
        arc = random.gauss(0, 8)
        dx = ex - sx
        dy = ey - sy
        length = math.sqrt(dx * dx + dy * dy) or 1
        # Perpendicular unit vector
        px = -dy / length
        py = dx / length

        for i in range(n_pts):
            t = i / max(n_pts - 1, 1)
            # Ease-out curve (fast start, slow end)
            t_ease = t * (2 - t)
            # Arc peaks at t=0.5
            arc_factor = 4 * t * (1 - t) * arc

            x = sx + dx * t_ease + px * arc_factor + random.gauss(0, 0.5)
            y = sy + dy * t_ease + py * arc_factor + random.gauss(0, 0.5)
            points.append({"x": round(x, 1), "y": round(y, 1)})

        # Hold points at end (zero velocity → no iOS inertia)
        if points:
            last = points[-1]
            for _ in range(4):
                points.append({"x": last["x"], "y": last["y"]})

        return points

    # ── Convenience ──────────────────────────────────────────────────────

    async def wait(self, min_s: float = 0.5, max_s: float = 2.0):
        """Human-like pause between actions."""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def short_pause(self):
        """Brief pause (200-600ms)."""
        await asyncio.sleep(random.uniform(0.2, 0.6))

    async def long_pause(self):
        """Longer pause (1-3s) — simulates reading or thinking."""
        await asyncio.sleep(random.uniform(1.0, 3.0))
