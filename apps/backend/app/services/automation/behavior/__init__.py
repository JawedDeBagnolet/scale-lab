"""Behavioral anti-patterns for realistic automation.

These patterns are inserted randomly during feed sessions, publishing,
and other long-running tasks to make automation indistinguishable from
real human usage.

Usage:
    from app.services.automation.behavior import maybe_pattern, pick_pattern

    # Random chance of running a pattern during a feed session
    await maybe_pattern(drv, log, probability=0.15)

    # Pick and run a specific category
    await pick_pattern(drv, log, category="scroll")
"""

from app.services.automation.behavior.patterns import (
    PATTERNS,
    IG_PATTERNS,
    maybe_pattern,
    pick_pattern,
)

__all__ = ["PATTERNS", "IG_PATTERNS", "maybe_pattern", "pick_pattern"]
