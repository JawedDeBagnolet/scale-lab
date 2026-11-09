"""
ig_iphone/behavior/presets.py — Resolver de presets comportement IG.

Resout un preset depuis la base de donnees (Comportement model).
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
        from app.models.comportement import Comportement
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            # 1. Presets demandes
            if preset_ids:
                stmt = select(Comportement).where(
                    Comportement.id.in_(preset_ids),
                    Comportement.enabled == True,
                )
                result = await db.execute(stmt)
                presets = result.scalars().all()

                if presets:
                    # Tirage pondere
                    chosen = _pick_from_pool(
                        [_preset_to_dict(p) for p in presets],
                        mode="weighted",
                    )
                    if chosen:
                        log("   [igbh] preset liste: %s (%s)" % (
                            chosen.get("name", "?"), chosen.get("id", "?")))
                        return chosen

            # 2. Pool global
            stmt = select(Comportement).where(
                Comportement.plat == platform,
                Comportement.enabled == True,
            )
            result = await db.execute(stmt)
            all_presets = result.scalars().all()

            if all_presets:
                pool = [_preset_to_dict(p) for p in all_presets]

                # Filtre par type de session si dispo
                if session_type:
                    typed = [
                        b for b in pool
                        if not (b.get("params") or {}).get("session_type")
                        or (b.get("params") or {}).get("session_type") == session_type
                    ]
                    if typed:
                        pool = typed

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
    params = behavior.get("params") or {}
    applied = []
    for section in ("intensity", "antipatterns", "duration"):
        d = params.get(section) or {}
        if isinstance(d, dict):
            for k, v in d.items():
                if v is not None:
                    cfg[k] = v
                    applied.append(k)
    # Aussi les params a la racine (flat)
    for k, v in params.items():
        if k not in ("intensity", "antipatterns", "duration") and v is not None:
            cfg[k] = v
            applied.append(k)
    if applied:
        log("   [igbh] applique: %s" % ", ".join(applied[:10]))
    return cfg


def _preset_to_dict(preset) -> dict:
    """Convertit un objet Comportement en dict utilisable."""
    return {
        "id": str(preset.id),
        "name": getattr(preset, "name", ""),
        "params": getattr(preset, "params", {}) or {},
        "pauses": getattr(preset, "pauses", []) or [],
        "durations": getattr(preset, "durations", []) or [],
        "weight": getattr(preset, "weight", 1) or 1,
        "enabled": getattr(preset, "enabled", True),
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
