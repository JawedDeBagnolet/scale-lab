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


    # Mapping preset keys → session config keys
    # Preset uses short names (like, save), sessions use _pct suffix (like_pct, save_pct)
_PRESET_KEY_MAP = {
    # Probabilities (from "p" section)
    "like":             "like_pct",
    "save":             "save_pct",
    "follow":           "follow_pct",
    "story":            "story_view_pct",
    "comments":         "comment_read_pct",
    "comment":          "comment_read_pct",
    "likeComment":      "like_comment_pct",
    "commentAuthor":    "visit_commenter_pct",
    "openPost":         "open_post_pct",
    "scrollback":       "scroll_back_pct",
    "target":           "visit_profile_pct",
    "repost":           "repost_pct",
    "notInterested":    "not_interested_pct",
    "interested":       "interested_pct",
    "skipFast":         "skip_fast_pct",
    "goBack":           "go_back_pct",
    "pauseLong":        "pause_long_pct",
    "watchFull":        "watch_full_pct",
    # Durations (from "durations" section or root)
    "min":              "duration_min",
    "max":              "duration_max",
    "durationMin":      "duration_min",
    "durationMax":      "duration_max",
    "watchMin":         "watch_min",
    "watchMax":         "watch_max",
    "watchFullMax":     "watch_full_max",
    "pauseLongMin":     "pause_long_min",
    "pauseLongMax":     "pause_long_max",
}


def apply_behavior(cfg: dict, behavior: dict | None, log=print) -> dict:
    """Aplatit les params du preset dans cfg (le preset ecrase).

    Structure preset config:
      p: {like: 25, save: 0, ...}          → probas 0-100, converties en 0-1
      pauses: [{min, max, prob, scope}, ...]  → liste de pauses pondérées
      durations: [{min, max, weight}, ...]    → durée de session pondérée (minutes)
    """
    if not behavior:
        return cfg
    config = behavior.get("config") or {}
    applied = []

    DICT_SECTIONS = ("p", "probabilities", "intensity", "antipatterns")
    for section_key in DICT_SECTIONS:
        section = config.get(section_key)
        if isinstance(section, dict):
            for k, v in section.items():
                if v is not None:
                    if section_key == "p" and isinstance(v, (int, float)) and v > 1:
                        v = v / 100.0
                    mapped = _PRESET_KEY_MAP.get(k, k)
                    cfg[mapped] = v
                    applied.append(mapped)

    # Pauses : liste d'objets [{min, max, prob, label, scope}, ...]
    # Stockées dans cfg pour sélection pondérée par la session
    pauses = config.get("pauses")
    if isinstance(pauses, list) and pauses:
        cfg["_pauses"] = pauses
        applied.append("_pauses(%d)" % len(pauses))

    # Durations : liste d'objets [{min, max, weight}, ...]
    # Sélection pondérée → duration_min / duration_max (en minutes)
    durations = config.get("durations")
    if isinstance(durations, list) and durations:
        chosen = _weighted_pick(durations, key="weight")
        if chosen:
            cfg["duration_min"] = chosen.get("min", cfg.get("duration_min", 3))
            cfg["duration_max"] = chosen.get("max", cfg.get("duration_max", 8))
            applied.append("duration(%d-%dmin)" % (cfg["duration_min"], cfg["duration_max"]))

    # Flat keys at root (icon, weight, etc.)
    SKIP_KEYS = {"p", "probabilities", "pauses", "durations", "intensity", "antipatterns", "icon", "weight"}
    for k, v in config.items():
        if k not in SKIP_KEYS and v is not None:
            mapped = _PRESET_KEY_MAP.get(k, k)
            cfg[mapped] = v
            applied.append(mapped)

    if applied:
        log("   [igbh] applique: %s" % ", ".join(applied[:12]))

    return cfg


def pick_pause(cfg: dict) -> float:
    """Sélectionne une pause pondérée depuis le preset, retourne la durée en secondes.

    Utilise cfg["_pauses"] si disponible, sinon retourne un fallback.
    """
    pauses = cfg.get("_pauses")
    if not pauses:
        # Fallback : pause aléatoire simple
        return random.uniform(2.0, 8.0)

    chosen = _weighted_pick(pauses, key="prob")
    if not chosen:
        return random.uniform(2.0, 8.0)

    mn = float(chosen.get("min", 2))
    mx = float(chosen.get("max", 8))
    return random.uniform(mn, mx)


def _weighted_pick(items: list[dict], key: str = "weight") -> dict | None:
    """Sélection pondérée dans une liste de dicts."""
    if not items:
        return None
    weights = [max(0.0, float(item.get(key, 1) or 0)) for item in items]
    total = sum(weights)
    if total <= 0:
        return random.choice(items)
    r = random.uniform(0, total)
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if r <= acc:
            return item
    return items[-1]
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
