"""Story planner — loop generation algorithm.

Generates a publication schedule from collections of story templates.
Each template × media = one variant (publishable unit).

Key concepts:
- Variant: a (template_id, media_id, media_index) tuple — one publishable story
- Loop: an ordered sequence of variants, shuffled per-account
- Depth: how many days of unique content the loop provides
- Anti-repetition: minimum days before reusing a media
- Conflict resolution: when a media appears in multiple templates,
  probability-weighted selection (1/N where N = number of templates sharing it)
"""

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class Variant:
    """One publishable story = template + specific media."""
    template_id: str
    media_id: str
    media_index: int  # position within the template's media list
    collection_id: str
    story_type: str
    moments: list[str] = field(default_factory=list)


@dataclass
class LoopSlot:
    """One slot in the generated schedule."""
    day: int  # day offset from start (0 = first day)
    moment: str  # matin, midi, aprem, etc.
    variant: Variant
    minute: int = 0  # minute offset within the moment window


@dataclass
class LoopResult:
    """Result of loop generation."""
    slots: list[LoopSlot]
    depth_days: int  # how many days of unique content
    total_variants: int  # total variant count
    unique_medias: int  # unique media count
    loop_length: int  # variants before cycle
    warnings: list[str] = field(default_factory=list)


def _seed_for_account(account_id: str, cycle: int = 0) -> int:
    """Deterministic seed from account ID + cycle number."""
    h = hashlib.sha256(f"{account_id}:{cycle}".encode()).hexdigest()
    return int(h[:8], 16)


def expand_variants(
    collections: list[dict],
    templates: list[dict],
) -> list[Variant]:
    """Expand collections into individual variants (template × media).

    A template with 5 medias produces 5 variants.
    A template with no media produces 1 variant (solid color background).
    """
    variants = []
    tpl_map = {t["id"]: t for t in templates}

    for coll in collections:
        coll_id = coll["id"]
        story_type = coll.get("type") or coll.get("story_type", "lifestyle")

        # Get template IDs from collection
        tpl_ids = set()
        by_p = coll.get("by_persona") or coll.get("byP") or {}
        if by_p:
            for pid, pdata in by_p.items():
                for tid in (pdata.get("tpls") or []):
                    tpl_ids.add(tid)
        for tid in (coll.get("template_ids") or coll.get("tpls") or []):
            tpl_ids.add(tid)

        for tid in tpl_ids:
            tpl = tpl_map.get(tid)
            if not tpl:
                continue

            media_ids = tpl.get("media_ids") or tpl.get("media") or []
            moments = tpl.get("moments") or []

            if not media_ids:
                # No media = solid color variant
                variants.append(Variant(
                    template_id=tid,
                    media_id="__solid__",
                    media_index=-1,
                    collection_id=coll_id,
                    story_type=story_type,
                    moments=moments,
                ))
            else:
                for i, mid in enumerate(media_ids):
                    variants.append(Variant(
                        template_id=tid,
                        media_id=mid,
                        media_index=i,
                        collection_id=coll_id,
                        story_type=story_type,
                        moments=moments,
                    ))

    return variants


def resolve_conflicts(variants: list[Variant]) -> list[Variant]:
    """When a media appears in multiple templates, assign it to one.

    Uses probability weighted by pool size:
    - Template A has 15 medias, Template B has 3 medias
    - Media X is in both → P(A gets X) = 15/(15+3), P(B gets X) = 3/(15+3)
    - Smaller pool templates are more likely to keep their shared medias

    Returns deduplicated variants (each media appears at most once).
    """
    # Group variants by media_id
    by_media: dict[str, list[Variant]] = defaultdict(list)
    for v in variants:
        by_media[v.media_id].append(v)

    # Count total medias per template (for weighting)
    tpl_media_count: dict[str, int] = defaultdict(int)
    for v in variants:
        tpl_media_count[v.template_id] += 1

    resolved = []
    rng = random.Random(42)  # fixed seed for reproducibility

    for media_id, media_variants in by_media.items():
        if media_id == "__solid__":
            # Solid color variants are never shared
            resolved.extend(media_variants)
            continue

        if len(media_variants) == 1:
            resolved.append(media_variants[0])
            continue

        # Conflict: same media in multiple templates
        # Weight inversely by pool size (smaller pool = higher chance to keep)
        weights = []
        for v in media_variants:
            pool_size = tpl_media_count[v.template_id]
            weights.append(1.0 / max(1, pool_size))

        # Normalize
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        # Pick winner
        winner = rng.choices(media_variants, weights=weights, k=1)[0]
        resolved.append(winner)

    return resolved


def generate_loop(
    variants: list[Variant],
    account_id: str,
    rules: list[dict],
    anti_repetition_days: int = 3,
    cycle: int = 0,
) -> LoopResult:
    """Generate a full publication loop for one account.

    Args:
        variants: expanded and conflict-resolved variants
        account_id: for deterministic shuffle
        rules: planner rules [{type, freqMode, n, moments}]
        anti_repetition_days: min days before reusing a media
        cycle: cycle number (incremented on re-shuffle)

    Returns:
        LoopResult with the full schedule
    """
    if not variants:
        return LoopResult(
            slots=[], depth_days=0, total_variants=0,
            unique_medias=0, loop_length=0,
            warnings=["Aucune variante disponible"],
        )

    seed = _seed_for_account(account_id, cycle)
    rng = random.Random(seed)

    # Group variants by story type
    by_type: dict[str, list[Variant]] = defaultdict(list)
    for v in variants:
        by_type[v.story_type].append(v)

    # Shuffle each type's variants independently
    for type_variants in by_type.values():
        rng.shuffle(type_variants)

    # Calculate daily needs from rules
    # Rule format: {type, freqMode, n, moments}
    # freqMode: 'week' = n times per week, 'every' = every n days
    daily_needs: list[dict] = []
    for rule in rules:
        story_type = rule.get("type", "lifestyle")
        freq_mode = rule.get("freqMode", "week")
        n = max(1, rule.get("n", 1))
        moments = rule.get("moments") or ["matin"]

        if freq_mode == "week":
            # n times per week → distribute across 7 days
            for i in range(n):
                day = int(i * 7 / n) % 7
                daily_needs.append({
                    "day_mod": day,
                    "type": story_type,
                    "moments": moments,
                    "period": 7,
                })
        else:
            # Every n days
            daily_needs.append({
                "day_mod": 0,
                "type": story_type,
                "moments": moments,
                "period": n,
            })

    if not daily_needs:
        return LoopResult(
            slots=[], depth_days=0, total_variants=len(variants),
            unique_medias=len(set(v.media_id for v in variants)),
            loop_length=0,
            warnings=["Aucune règle de publication"],
        )

    # Calculate how many variants we consume per week
    variants_per_week = sum(
        7 // need["period"] for need in daily_needs
    )
    if variants_per_week == 0:
        variants_per_week = 1

    # Unique medias
    unique_medias = set(v.media_id for v in variants if v.media_id != "__solid__")

    # Depth = total variants / variants per day (rounded)
    variants_per_day = max(1, variants_per_week / 7)
    depth_days = int(len(variants) / variants_per_day)

    # Generate slots
    slots: list[LoopSlot] = []
    type_cursors: dict[str, int] = defaultdict(int)  # cursor per type
    used_recently: list[str] = []  # media IDs used in last N days
    warnings = []

    # Moment time windows (minutes from midnight)
    MOMENT_WINDOWS = {
        "matin": (420, 600), "midi": (690, 810), "aprem": (840, 1020),
        "finap": (1020, 1170), "diner": (1170, 1260),
        "soiree": (1260, 1410), "nuit": (1410, 1620),
    }

    for day in range(depth_days):
        day_medias = []

        for need in daily_needs:
            # Check if this need fires today
            if day % need["period"] != need["day_mod"] % need["period"]:
                continue

            story_type = need["type"]
            type_pool = by_type.get(story_type, [])
            if not type_pool:
                continue

            # Find next variant that isn't in the anti-repetition window
            cursor = type_cursors[story_type]
            found = False
            for attempt in range(len(type_pool)):
                idx = (cursor + attempt) % len(type_pool)
                v = type_pool[idx]

                if v.media_id in used_recently and v.media_id != "__solid__":
                    continue

                if v.media_id in day_medias and v.media_id != "__solid__":
                    continue

                # Pick moment
                available_moments = need["moments"]
                moment = rng.choice(available_moments) if available_moments else "matin"
                window = MOMENT_WINDOWS.get(moment, (420, 600))
                minute = rng.randint(window[0], window[1])

                slots.append(LoopSlot(
                    day=day,
                    moment=moment,
                    variant=v,
                    minute=minute,
                ))

                day_medias.append(v.media_id)
                type_cursors[story_type] = (idx + 1) % len(type_pool)
                found = True
                break

            if not found:
                warnings.append(f"Jour {day}: pas assez de variantes {story_type} (anti-répétition)")

        # Update anti-repetition window
        used_recently.extend(day_medias)
        # Keep only the last N days worth
        max_recent = anti_repetition_days * max(1, len(daily_needs))
        if len(used_recently) > max_recent:
            used_recently = used_recently[-max_recent:]

    # Sort slots by day then minute
    slots.sort(key=lambda s: (s.day, s.minute))

    return LoopResult(
        slots=slots,
        depth_days=depth_days,
        total_variants=len(variants),
        unique_medias=len(unique_medias),
        loop_length=len(variants),
        warnings=warnings,
    )


def generate_highlight_sequence(
    collection: dict,
    templates: list[dict],
) -> list[Variant]:
    """Generate a highlight sequence with unique medias per slide.

    The order is defined by the collection's variant structure.
    Each slide picks a media not used by previous slides.
    """
    tpl_map = {t["id"]: t for t in templates}
    sequence = []
    used_medias = set()

    # Get variants from collection
    by_p = collection.get("by_persona") or collection.get("byP") or {}
    for pid, pdata in by_p.items():
        for var_group in (pdata.get("vars") or []):
            for tid in (var_group.get("tpls") or []):
                tpl = tpl_map.get(tid)
                if not tpl:
                    continue

                media_ids = tpl.get("media_ids") or tpl.get("media") or []
                # Pick first media not already used
                picked = None
                for i, mid in enumerate(media_ids):
                    if mid not in used_medias:
                        picked = Variant(
                            template_id=tid,
                            media_id=mid,
                            media_index=i,
                            collection_id=collection["id"],
                            story_type="highlight",
                            moments=[],
                        )
                        used_medias.add(mid)
                        break

                if not picked and media_ids:
                    # All medias used, pick first anyway
                    picked = Variant(
                        template_id=tid,
                        media_id=media_ids[0],
                        media_index=0,
                        collection_id=collection["id"],
                        story_type="highlight",
                        moments=[],
                    )

                if picked:
                    sequence.append(picked)

    return sequence


def estimate_depth(
    collections: list[dict],
    templates: list[dict],
    rules: list[dict],
) -> dict:
    """Quick depth estimation without generating the full loop.

    Returns:
        {
            total_variants: int,
            unique_medias: int,
            variants_per_day: float,
            depth_days: int,
            by_type: {type: {variants: int, medias: int}}
        }
    """
    variants = expand_variants(collections, templates)
    resolved = resolve_conflicts(variants)

    # Group by type
    by_type: dict[str, list[Variant]] = defaultdict(list)
    for v in resolved:
        by_type[v.story_type].append(v)

    # Calculate daily consumption from rules
    variants_per_week = 0
    for rule in rules:
        freq_mode = rule.get("freqMode", "week")
        n = max(1, rule.get("n", 1))
        if freq_mode == "week":
            variants_per_week += n
        else:
            variants_per_week += 7 / n

    variants_per_day = max(0.1, variants_per_week / 7)
    unique_medias = len(set(v.media_id for v in resolved if v.media_id != "__solid__"))

    type_stats = {}
    for stype, tvars in by_type.items():
        type_medias = set(v.media_id for v in tvars if v.media_id != "__solid__")
        type_stats[stype] = {
            "variants": len(tvars),
            "medias": len(type_medias),
        }

    return {
        "total_variants": len(resolved),
        "unique_medias": unique_medias,
        "variants_per_day": round(variants_per_day, 1),
        "depth_days": int(len(resolved) / variants_per_day),
        "by_type": type_stats,
    }
