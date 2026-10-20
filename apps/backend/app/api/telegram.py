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


class BotGroupAddedRequest(BaseModel):
    chat_id: int
    chat_title: str | None = None


class AssignGroupRequest(BaseModel):
    pending_group_id: str


class SendBriefRequest(BaseModel):
    text: str
    topic: str | None = None


class SendAlertRequest(BaseModel):
    module: str
    event_type: str
    message: str
    level: str = "warning"


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


# ── Group management ────────────────────────────────────────


@router.post("/bot/group_added")
async def bot_group_added(body: BotGroupAddedRequest, db: AsyncSession = Depends(get_db)):
    """Bot calls this when it is added to a Telegram group."""
    result = await tg_svc.register_pending_group(
        db,
        chat_id=body.chat_id,
        chat_title=body.chat_title,
    )
    if not result["ok"]:
        raise HTTPException(400, result.get("error", "unknown"))
    return result


@router.get("/groups/pending")
async def list_pending_groups(db: AsyncSession = Depends(get_db)):
    """List all pending (unassigned) Telegram groups."""
    rows = await tg_svc.list_pending_groups(db)
    return {"data": rows, "count": len(rows)}


@router.post("/groups/assign/{persona_id}")
async def assign_group(
    persona_id: uuid.UUID,
    body: AssignGroupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Assign a pending group to a persona — triggers bot topic setup."""
    try:
        gid = uuid.UUID(body.pending_group_id)
    except ValueError:
        raise HTTPException(400, "pending_group_id invalide")

    result = await tg_svc.assign_group(
        db, persona_id=persona_id, pending_group_id=gid
    )
    if not result["ok"]:
        code = 404 if "not_found" in result["error"] else 400
        raise HTTPException(code, result["error"])
    return result


@router.delete("/groups/{persona_id}")
async def unassign_group(persona_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Remove group assignment from a persona."""
    result = await tg_svc.unassign_group(db, persona_id=persona_id)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


# ── Briefs / Notifications ────────────────────────────────────


@router.post("/brief/{persona_id}")
async def send_brief(
    persona_id: uuid.UUID,
    body: SendBriefRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a brief to a specific persona via Telegram."""
    result = await tg_svc.send_brief(
        db,
        persona_id=persona_id,
        text=body.text,
        topic_name=body.topic,
    )
    if not result["ok"]:
        code = 404 if "not_found" in result.get("error", "") else 400
        raise HTTPException(code, result["error"])
    return result


@router.post("/brief")
async def send_brief_all(
    body: SendBriefRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a brief to ALL linked personas."""
    result = await tg_svc.send_brief_all(
        db,
        text=body.text,
        topic_name=body.topic,
    )
    return result


@router.post("/alert")
async def send_alert(
    body: SendAlertRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send an alert notification via Telegram."""
    result = await tg_svc.send_alert(
        db,
        module=body.module,
        event_type=body.event_type,
        message=body.message,
        level=body.level,
    )
    return result
