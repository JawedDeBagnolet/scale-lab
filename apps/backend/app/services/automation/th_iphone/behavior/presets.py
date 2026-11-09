"""
th_iphone/behavior/presets.py — Resolver de presets comportement Threads (async).

Charge les presets depuis la DB (modele Comportement) au lieu de l'API worker.
"""

import logging

logger = logging.getLogger("automation.th_presets")


async def resolve_behavior(preset_ids=None, platform="th"):
    """Retourne le preset de comportement depuis la DB, ou None."""
    try:
        from app.db import AsyncSessionLocal
        from app.models.comportement import Comportement
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            if preset_ids:
                # Chercher par IDs
                from uuid import UUID
                ids = [UUID(str(pid)) if not isinstance(pid, UUID) else pid for pid in preset_ids]
                stmt = select(Comportement).where(Comportement.id.in_(ids)).limit(1)
            else:
                stmt = select(Comportement).where(
                    Comportement.plat == platform
                ).limit(1)

            result = await db.execute(stmt)
            preset = result.scalar_one_or_none()
            if preset:
                logger.info("   [thbh] preset: %s", preset.name)
                return {
                    "name": preset.name,
                    "pauses": preset.pauses,
                    "durations": preset.durations,
                    "config_overrides": preset.config_overrides or {},
                }
    except Exception as e:
        logger.warning("   [thbh] preset load error: %s", str(e)[:100])

    return None


def apply_behavior(cfg, behavior, log=print):
    """Applique les overrides du behavior sur la config."""
    overrides = behavior.get("config_overrides", {})
    for k, v in overrides.items():
        if k in cfg:
            cfg[k] = v
            log("   [thbh] override %s = %s" % (k, v))
    return cfg
