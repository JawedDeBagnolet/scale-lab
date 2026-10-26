"""Automation stack — async iPhone UI automation via MCP.

Ported from the VPS standalone scripts (iphone_device.py, human_touch.py,
ig_iphone/, th_iphone/) into the FastAPI backend as async services.

Architecture:
    DeviceSession   — async context manager: lock device, switch container, ensure login
    HumanTouch      — async MCP wrapper: tap, swipe, type with realistic motion
    ScrollEngine    — calibrated scrolling with feedback loop
    IGDriver        — async IG driver: element finding, post detection, feed parsing
    THDriver        — async Threads driver
    ig_runner       — dispatches IG task types (feed, post, story, reels…)
    th_runner       — dispatches TH task types (feed, post, reply…)

Wired into the execution engine via engine.py._execute_iphone_action().
"""

from app.services.automation.device_session import (  # noqa: F401
    BUNDLE_INSTAGRAM,
    BUNDLE_THREADS,
    DeviceLocked,
    DeviceSession,
    DeviceUnavailable,
    LoginRequired,
)
from app.services.automation.ig_runner import run_ig_task  # noqa: F401
from app.services.automation.th_runner import run_th_task  # noqa: F401
