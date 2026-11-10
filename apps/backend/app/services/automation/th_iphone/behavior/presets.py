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


    # Import shared key mapping from IG presets (same DB structure)
from app.services.automation.ig_iphone.behavior.presets import _PRESET_KEY_MAP


def apply_behavior(cfg, behavior, log=print):
    """Applique les overrides du behavior sur la config."""
    if not behavior:
        return cfg
    config = behavior.get("config", {})
    applied = []
    SECTION_KEYS = ("p", "probabilities", "pauses", "durations", "intensity", "antipatterns")
    for section_key in SECTION_KEYS:
        section = config.get(section_key)
        if isinstance(section, dict):
            for k, v in section.items():
                if v is not None:
                    if section_key == "p" and isinstance(v, (int, float)) and v > 1:
                        v = v / 100.0
                    mapped = _PRESET_KEY_MAP.get(k, k)
                    cfg[mapped] = v
                    applied.append(mapped)
    for k, v in config.items():
        if k not in SECTION_KEYS and v is not None:
            mapped = _PRESET_KEY_MAP.get(k, k)
            cfg[mapped] = v
            applied.append(mapped)
    if applied:
        log("   [thbh] override: %s" % ", ".join(applied[:10]))
    return cfg
