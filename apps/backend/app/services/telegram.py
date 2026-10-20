"""Telegram integration service — pending models + link/unlink."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.telegram_pending import TelegramPending


async def register_pending(
    db: AsyncSession,
    *,
    persona_id: uuid.UUID,
    tg_user_id: int,
    tg_username: str | None,
    tg_first_name: str | None,
    tg_lang: str | None = None,
) -> dict:
    """Called by the bot when a model clicks /start with a deep link.

    If the same tg_user_id + persona_id already exists, update the row.
    If the persona already has this tg_user_id linked, skip (already linked).
    """
    # Check if persona exists
    persona = await db.get(Persona, persona_id)
    if not persona:
        return {"ok": False, "error": "persona_not_found"}

    # Check if already linked to this persona
    tg = persona.telegram or {}
    if tg.get("chat_id") == tg_user_id:
        return {"ok": True, "status": "already_linked"}

    # Upsert pending row
    stmt = select(TelegramPending).where(
        TelegramPending.persona_id == persona_id,
        TelegramPending.tg_user_id == tg_user_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.tg_username = tg_username
        existing.tg_first_name = tg_first_name
        existing.tg_lang = tg_lang or existing.tg_lang
    else:
        pending = TelegramPending(
            persona_id=persona_id,
            tg_user_id=tg_user_id,
            tg_username=tg_username,
            tg_first_name=tg_first_name,
            tg_lang=tg_lang,
        )
        db.add(pending)

    await db.commit()
    return {"ok": True, "status": "pending"}


async def list_pending(db: AsyncSession) -> list[dict]:
    """List all pending model registrations."""
    stmt = select(TelegramPending).order_by(TelegramPending.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "persona_id": str(r.persona_id),
            "tg_user_id": r.tg_user_id,
            "tg_username": r.tg_username,
            "tg_first_name": r.tg_first_name,
            "tg_lang": r.tg_lang,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


async def list_pending_for_persona(db: AsyncSession, persona_id: uuid.UUID) -> list[dict]:
    """List pending registrations for a specific persona."""
    stmt = (
        select(TelegramPending)
        .where(TelegramPending.persona_id == persona_id)
        .order_by(TelegramPending.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "persona_id": str(r.persona_id),
            "tg_user_id": r.tg_user_id,
            "tg_username": r.tg_username,
            "tg_first_name": r.tg_first_name,
            "tg_lang": r.tg_lang,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


async def link_model(
    db: AsyncSession,
    *,
    persona_id: uuid.UUID,
    pending_id: uuid.UUID,
) -> dict:
    """Link a pending model to a persona (stores in persona.telegram JSONB)."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        return {"ok": False, "error": "persona_not_found"}

    pending = await db.get(TelegramPending, pending_id)
    if not pending:
        return {"ok": False, "error": "pending_not_found"}

    if pending.persona_id != persona_id:
        return {"ok": False, "error": "pending_persona_mismatch"}

    # Write to persona.telegram JSONB
    persona.telegram = {
        "bot": "ScaleCrewBot",
        "username": pending.tg_username,
        "chat_id": pending.tg_user_id,
        "langue": pending.tg_lang or "fr",
        "groupe": (persona.telegram or {}).get("groupe"),
        "topic": (persona.telegram or {}).get("topic"),
    }
    persona.updated_at = datetime.now(UTC)

    # Delete the pending row (and any other pending rows for this persona)
    await db.execute(
        delete(TelegramPending).where(TelegramPending.persona_id == persona_id)
    )

    await db.commit()
    await db.refresh(persona)

    return {"ok": True, "telegram": persona.telegram}


async def unlink_model(db: AsyncSession, *, persona_id: uuid.UUID) -> dict:
    """Remove Telegram link from a persona."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        return {"ok": False, "error": "persona_not_found"}

    persona.telegram = None
    persona.updated_at = datetime.now(UTC)
    await db.commit()

    return {"ok": True}


async def get_telegram_status(db: AsyncSession, persona_id: uuid.UUID) -> dict:
    """Get the Telegram status for a persona (linked + pending)."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        return {"ok": False, "error": "persona_not_found"}

    pending = await list_pending_for_persona(db, persona_id)
    tg = persona.telegram or {}

    return {
        "ok": True,
        "linked": tg if tg.get("chat_id") else None,
        "pending": pending,
    }
