"""
th_iphone/behavior/presets.py — Resolver de presets comportement Threads (async).

Charge les presets depuis la DB (modele Preset, table presets).
"""

import logging

logger = logging.getLogger("automation.th_presets")


async def resolve_behavior(preset_ids=None, platform="th"):
    """Retourne le preset de comportement depuis la DB, ou None."""
    try:
        from app.db import AsyncSessionLocal
        from app.models.comportement import Preset
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            if preset_ids:
                from uuid import UUID
                ids = [UUID(str(pid)) if not isinstance(pid, UUID) else pid for pid in preset_ids]
                stmt = select(Preset).where(Preset.id.in_(ids)).limit(1)
            else:
                stmt = select(Preset).where(
                    Preset.plateforme == platform
                ).limit(1)

            result = await db.execute(stmt)
            preset = result.scalar_one_or_none()
            if preset:
                config = preset.config or {}
                logger.info("   [thbh] preset: %s", preset.name)
                return {
                    "name": preset.name,
                    "config": config,
                    "pauses": config.get("pauses", []),
                    "durations": config.get("durations", []),
                }
    except Exception as e:
        logger.warning("   [thbh] preset load error: %s", str(e)[:100])

    return None


    # Reuse IG preset infrastructure (same DB structure)
from app.services.automation.ig_iphone.behavior.presets import (
    _PRESET_KEY_MAP, apply_behavior as _ig_apply, pick_pause,
)


def apply_behavior(cfg, behavior, log=print):
    """Applique les overrides du behavior sur la config (délègue à IG presets)."""
    result = _ig_apply(cfg, behavior, log=log)
    # Replace log prefix if present
    return result
