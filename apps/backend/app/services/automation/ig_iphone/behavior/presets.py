"""
ig_iphone/behavior/presets.py — Resolver de presets comportement IG.

Resout un preset depuis la base de donnees (Preset model, table presets).
Si aucun preset configure, la session utilise ses DEFAULT_CONFIG.

Ported from VPS — adapted to async + DB instead of worker API.
"""

import random
from typing import Any

_rnd = random.Random()


async def resolve_behavior(
    preset_ids: list[str] | None = None,
    platform: str = "ig",
    session_type: str | None = None,
    log=print,
) -> dict | None:
    """Retourne le preset de comportement a appliquer, ou None.

    Ordre :
      1. preset_ids list — tirage pondere parmi les presets demandes
      2. pool global depuis la DB (weighted ou uniform)
      3. None (la session utilise ses defaults)
    """
    try:
        from app.db import AsyncSessionLocal
        from app.models.comportement import Preset
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            # 1. Presets demandes par ID
            if preset_ids:
                stmt = select(Preset).where(
                    Preset.id.in_(preset_ids),
                )
                result = await db.execute(stmt)
                presets = result.scalars().all()

                if presets:
                    chosen = _pick_from_pool(
                        [_preset_to_dict(p) for p in presets],
                        mode="weighted",
                    )
                    if chosen:
                        log("   [igbh] preset liste: %s (%s)" % (
                            chosen.get("name", "?"), chosen.get("id", "?")))
                        return chosen

            # 2. Pool global pour la plateforme
            stmt = select(Preset).where(
                Preset.plateforme == platform,
            )
            if session_type:
                stmt = stmt.where(Preset.session_type == session_type)
            result = await db.execute(stmt)
            all_presets = result.scalars().all()

            if all_presets:
                pool = [_preset_to_dict(p) for p in all_presets]
                chosen = _pick_from_pool(pool, mode="weighted")
                if chosen:
                    log("   [igbh] preset pool: %s (%s)" % (
                        chosen.get("name", "?"), chosen.get("id", "?")))
                    return chosen

    except Exception as e:
        log("   [igbh] erreur DB: %s" % str(e)[:80])

    # 3. Rien — la session utilise ses defaults
    log("   [igbh] aucun preset -> defaults")
    return None


def apply_behavior(cfg: dict, behavior: dict | None, log=print) -> dict:
    """Aplatit les params du preset dans cfg (le preset ecrase)."""
    if not behavior:
        return cfg
    config = behavior.get("config") or {}
    applied = []

    # Le champ config est un JSONB libre — on itere ses cles
    # Structure attendue: {probabilities: {like: 0.7, ...}, pauses: {...}, durations: {...}, ...}
    for section_key in ("probabilities", "pauses", "durations", "intensity", "antipatterns"):
        section = config.get(section_key)
        if isinstance(section, dict):
            for k, v in section.items():
                if v is not None:
                    cfg[k] = v
                    applied.append(k)

    # Aussi les params a la racine (flat keys)
    for k, v in config.items():
        if k not in ("probabilities", "pauses", "durations", "intensity", "antipatterns") and v is not None:
            cfg[k] = v
            applied.append(k)

    if applied:
        log("   [igbh] applique: %s" % ", ".join(applied[:10]))
    return cfg


def _preset_to_dict(preset) -> dict:
    """Convertit un objet Preset en dict utilisable."""
    config = getattr(preset, "config", {}) or {}
    return {
        "id": str(preset.id),
        "name": getattr(preset, "name", ""),
        "config": config,
        "pauses": config.get("pauses", []),
        "durations": config.get("durations", []),
        "weight": config.get("weight", 1),
        "session_type": getattr(preset, "session_type", ""),
        "is_default": getattr(preset, "is_default", False),
    }


def _pick_from_pool(pool: list[dict], mode: str = "uniform") -> dict | None:
    if not pool:
        return None
    if mode == "weighted":
        weights = [max(0.0, float(b.get("weight", 1) or 0)) for b in pool]
        tot = sum(weights)
        if tot <= 0:
            return _rnd.choice(pool)
        r = _rnd.uniform(0, tot)
        acc = 0.0
        for b, w in zip(pool, weights):
            acc += w
            if r <= acc:
                return b
        return pool[-1]
    else:
        return _rnd.choice(pool)
