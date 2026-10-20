"""OnlyChat ↔ CRM bidirectional sync.

Pulls fans, transactions, and scripts from OnlyChat's MCP API
and upserts them into the local CRM tables.  Each record gets an
`oc_external_id` so subsequent syncs update rather than duplicate.

Sync flow:
  1. Fetch OC creators → match to local Personas via prs_id
  2. For each matched persona: pull fans, transactions, scripts
  3. Upsert into local tables with oc_external_id
  4. Update last-sync timestamp on WorkspaceSettings
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import Fan, Script, Transaction
from app.models.persona import Persona
from app.models.settings import WorkspaceSettings
from app.services import oc_client

logger = logging.getLogger("oc_sync")


async def _get_api_key(db: AsyncSession) -> str | None:
    stmt = select(WorkspaceSettings).limit(1)
    settings = (await db.execute(stmt)).scalar_one_or_none()
    return settings.oc_api_key if settings else None


async def _persona_map(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Build a mapping of OC creator_id → local persona UUID."""
    stmt = select(Persona).where(Persona.prs_id.isnot(None))
    personas = (await db.execute(stmt)).scalars().all()
    return {p.prs_id: p.id for p in personas if p.prs_id}


# ── Fan sync ─────────────────────────────────────────────────────


async def sync_fans(
    db: AsyncSession,
    api_key: str,
    oc_creator_id: str,
    local_persona_id: uuid.UUID,
) -> dict:
    """Pull fans from OC for one creator and upsert locally."""
    oc_fans = await oc_client.list_fans(api_key, oc_creator_id, limit=500)

    created = 0
    updated = 0

    for f in oc_fans:
        ext_id = str(f.get("id", ""))
        if not ext_id:
            continue

        # Check if already synced
        stmt = select(Fan).where(Fan.oc_external_id == ext_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        pseudo = f.get("username") or f.get("name") or f.get("display_name") or ext_id
        total = int(f.get("total_spent", 0) or 0)
        last_act = None
        if f.get("last_activity"):
            try:
                last_act = datetime.fromisoformat(str(f["last_activity"]).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        joined = datetime.now(UTC)
        if f.get("joined_at") or f.get("created_at"):
            raw = f.get("joined_at") or f.get("created_at")
            try:
                joined = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        if existing:
            existing.pseudo = pseudo
            existing.total_spent = total
            existing.last_activity = last_act
            existing.updated_at = datetime.now(UTC)
            updated += 1
        else:
            fan = Fan(
                oc_external_id=ext_id,
                pseudo=pseudo,
                creator_id=local_persona_id,
                platform_origin="of",
                joined_at=joined,
                total_spent=total,
                last_activity=last_act,
            )
            db.add(fan)
            created += 1

    await db.commit()
    return {"created": created, "updated": updated, "total_oc": len(oc_fans)}


# ── Transaction sync ─────────────────────────────────────────────


async def sync_transactions(
    db: AsyncSession,
    api_key: str,
    oc_creator_id: str,
    local_persona_id: uuid.UUID,
) -> dict:
    """Pull transactions from OC and upsert locally."""
    oc_txs = await oc_client.list_transactions(api_key, oc_creator_id, limit=200)

    # Build fan mapping: oc_fan_id → local Fan.id
    stmt = select(Fan).where(Fan.creator_id == local_persona_id, Fan.oc_external_id.isnot(None))
    local_fans = (await db.execute(stmt)).scalars().all()
    fan_map = {f.oc_external_id: f.id for f in local_fans}

    created = 0
    skipped = 0

    for tx in oc_txs:
        ext_id = str(tx.get("id", ""))
        if not ext_id:
            continue

        # Skip if already synced
        stmt2 = select(Transaction.id).where(Transaction.oc_external_id == ext_id)
        exists = (await db.execute(stmt2)).scalar_one_or_none()
        if exists:
            skipped += 1
            continue

        # Map fan
        oc_fan_id = str(tx.get("fan_id", ""))
        local_fan_id = fan_map.get(oc_fan_id)
        if not local_fan_id:
            # Create a stub fan
            local_fan_id = uuid.uuid4()
            stub = Fan(
                id=local_fan_id,
                oc_external_id=oc_fan_id if oc_fan_id else None,
                pseudo=tx.get("fan_name") or oc_fan_id or "?",
                creator_id=local_persona_id,
                platform_origin="of",
                joined_at=datetime.now(UTC),
            )
            db.add(stub)
            if oc_fan_id:
                fan_map[oc_fan_id] = local_fan_id

        ts = datetime.now(UTC)
        if tx.get("timestamp") or tx.get("created_at"):
            raw = tx.get("timestamp") or tx.get("created_at")
            try:
                ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        t = Transaction(
            oc_external_id=ext_id,
            fan_id=local_fan_id,
            creator_id=local_persona_id,
            transaction_type=tx.get("type", "tip")[:10],
            amount=int(tx.get("amount", 0) or 0),
            timestamp=ts,
        )
        db.add(t)
        created += 1

    await db.commit()
    return {"created": created, "skipped": skipped, "total_oc": len(oc_txs)}


# ── Script sync ──────────────────────────────────────────────────


async def sync_scripts(
    db: AsyncSession,
    api_key: str,
    oc_creator_id: str,
) -> dict:
    """Pull scripts from OC and upsert locally."""
    oc_scripts = await oc_client.list_scripts(api_key, oc_creator_id)

    created = 0
    updated = 0

    for s in oc_scripts:
        ext_id = str(s.get("id", ""))
        if not ext_id:
            continue

        stmt = select(Script).where(Script.oc_external_id == ext_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        steps = s.get("steps") or s.get("messages") or []
        folder = s.get("folder") or s.get("category") or "OC"
        active = s.get("active", True)
        if isinstance(active, str):
            active = active.lower() in ("true", "1", "yes")

        if existing:
            existing.steps = steps
            existing.folder = folder
            existing.active = bool(active)
            existing.updated_at = datetime.now(UTC)
            updated += 1
        else:
            script = Script(
                oc_external_id=ext_id,
                folder=folder,
                active=bool(active),
                steps=steps,
                stats=s.get("stats") or {},
            )
            db.add(script)
            created += 1

    await db.commit()
    return {"created": created, "updated": updated, "total_oc": len(oc_scripts)}


# ── Full sync ────────────────────────────────────────────────────


async def run_full_sync(db: AsyncSession) -> dict:
    """Run a full OC → local sync for all matched personas.

    Returns a summary of what was synced.
    """
    api_key = await _get_api_key(db)
    if not api_key:
        return {"ok": False, "error": "no_oc_api_key"}

    # Get OC creators
    oc_creators = await oc_client.list_creators(api_key)
    if not oc_creators:
        return {"ok": False, "error": "no_creators_found"}

    # Build persona map
    pmap = await _persona_map(db)

    results = []
    for creator in oc_creators:
        oc_id = str(creator.get("id", ""))
        oc_name = creator.get("name") or creator.get("display_name") or oc_id
        local_pid = pmap.get(oc_id)

        if not local_pid:
            logger.info("OC creator %s (%s) not matched to any persona", oc_id, oc_name)
            results.append({"creator": oc_name, "status": "unmatched"})
            continue

        logger.info("Syncing OC creator %s → persona %s", oc_name, local_pid)

        fans = await sync_fans(db, api_key, oc_id, local_pid)
        txs = await sync_transactions(db, api_key, oc_id, local_pid)
        scripts = await sync_scripts(db, api_key, oc_id)

        results.append({
            "creator": oc_name,
            "persona_id": str(local_pid),
            "fans": fans,
            "transactions": txs,
            "scripts": scripts,
        })

    # Update last sync timestamp
    stmt = select(WorkspaceSettings).limit(1)
    settings = (await db.execute(stmt)).scalar_one_or_none()
    if settings:
        settings.oc_last_sync = datetime.now(UTC)
        await db.commit()

    return {"ok": True, "synced": len([r for r in results if "fans" in r]), "results": results}
