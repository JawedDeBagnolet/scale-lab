"""Telegram integration endpoints.

Two groups:
- /api/telegram/bot/*  — called by the bot (same VPS, same auth token)
- /api/telegram/*      — called by the frontend (through the gateway)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services import telegram as tg_svc

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────

class BotStartRequest(BaseModel):
    persona_id: str
    tg_user_id: int
    tg_username: str | None = None
    tg_first_name: str | None = None
    tg_lang: str | None = None


class LinkRequest(BaseModel):
    pending_id: str


# ── Bot-facing routes (called from localhost by the bot) ─

@router.post("/bot/start")
async def bot_start(body: BotStartRequest, db: AsyncSession = Depends(get_db)):
    """Bot calls this when a model clicks /start with a deep link persona_id."""
    try:
        pid = uuid.UUID(body.persona_id)
    except ValueError:
        raise HTTPException(400, "persona_id invalide")

    result = await tg_svc.register_pending(
        db,
        persona_id=pid,
        tg_user_id=body.tg_user_id,
        tg_username=body.tg_username,
        tg_first_name=body.tg_first_name,
        tg_lang=body.tg_lang,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


# ── Frontend-facing routes ───────────────────────────────

@router.get("/pending")
async def list_pending(db: AsyncSession = Depends(get_db)):
    """List all pending Telegram registrations."""
    rows = await tg_svc.list_pending(db)
    return {"data": rows, "count": len(rows)}


@router.get("/pending/{persona_id}")
async def list_pending_for_persona(persona_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List pending registrations for a specific persona."""
    rows = await tg_svc.list_pending_for_persona(db, persona_id)
    return {"data": rows, "count": len(rows)}


@router.get("/status/{persona_id}")
async def telegram_status(persona_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get Telegram status for a persona (linked info + pending list)."""
    result = await tg_svc.get_telegram_status(db, persona_id)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.post("/link/{persona_id}")
async def link_model(
    persona_id: uuid.UUID,
    body: LinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Link a pending model to a persona."""
    try:
        pending_id = uuid.UUID(body.pending_id)
    except ValueError:
        raise HTTPException(400, "pending_id invalide")

    result = await tg_svc.link_model(db, persona_id=persona_id, pending_id=pending_id)
    if not result["ok"]:
        code = 404 if "not_found" in result["error"] else 400
        raise HTTPException(code, result["error"])
    return result


@router.delete("/link/{persona_id}")
async def unlink_model(persona_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Remove Telegram link from a persona."""
    result = await tg_svc.unlink_model(db, persona_id=persona_id)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result
