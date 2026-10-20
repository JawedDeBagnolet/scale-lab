"""Telegram integration service — pending models + groups, link/unlink + briefs."""

import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.settings import WorkspaceSettings
from app.models.telegram_pending import TelegramPending
from app.models.telegram_pending_group import TelegramPendingGroup

logger = logging.getLogger("telegram")

BOT_HTTP = "http://127.0.0.1:8501"
TG_API = "https://api.telegram.org"


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


# ── Pending groups ──────────────────────────────────────────


async def register_pending_group(
    db: AsyncSession,
    *,
    chat_id: int,
    chat_title: str | None,
) -> dict:
    """Called by the bot when it is added to a group."""
    # Check if already registered
    stmt = select(TelegramPendingGroup).where(
        TelegramPendingGroup.chat_id == chat_id
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.chat_title = chat_title or existing.chat_title
        await db.commit()
        return {"ok": True, "status": "updated"}

    group = TelegramPendingGroup(
        chat_id=chat_id,
        chat_title=chat_title,
    )
    db.add(group)
    await db.commit()
    return {"ok": True, "status": "pending"}


async def list_pending_groups(db: AsyncSession) -> list[dict]:
    """List all pending (unassigned) groups."""
    # Get all group chat_ids already assigned to personas
    all_personas = (await db.execute(select(Persona))).scalars().all()
    assigned_groups = set()
    for p in all_personas:
        tg = p.telegram or {}
        if tg.get("groupe"):
            assigned_groups.add(tg["groupe"])

    stmt = select(TelegramPendingGroup).order_by(
        TelegramPendingGroup.added_at.desc()
    )
    rows = (await db.execute(stmt)).scalars().all()

    return [
        {
            "id": str(r.id),
            "chat_id": r.chat_id,
            "chat_title": r.chat_title,
            "added_at": r.added_at.isoformat(),
        }
        for r in rows
        if r.chat_id not in assigned_groups
    ]


async def assign_group(
    db: AsyncSession,
    *,
    persona_id: uuid.UUID,
    pending_group_id: uuid.UUID,
) -> dict:
    """Assign a pending group to a persona, then call the bot to setup topics."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        return {"ok": False, "error": "persona_not_found"}

    pending = await db.get(TelegramPendingGroup, pending_group_id)
    if not pending:
        return {"ok": False, "error": "group_not_found"}

    # Call the bot HTTP API to create topics
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{BOT_HTTP}/bot/setup_group",
                json={"chat_id": pending.chat_id, "persona_id": str(persona_id)},
            )
            bot_result = resp.json()
    except Exception as e:
        return {"ok": False, "error": f"bot_unreachable: {str(e)[:100]}"}

    if not bot_result.get("ok"):
        return {"ok": False, "error": f"bot_setup_failed: {bot_result.get('error', '?')}"}

    group_data = bot_result.get("group", {})
    topics = group_data.get("topics", {})

    # Update persona.telegram JSONB with group info
    # IMPORTANT: create a NEW dict so SQLAlchemy detects the JSONB change
    tg = dict(persona.telegram or {})
    tg["groupe"] = pending.chat_id
    tg["groupe_title"] = pending.chat_title
    tg["topics"] = topics
    tg["topic"] = topics.get("veille")  # default brief topic
    persona.telegram = tg
    persona.updated_at = datetime.now(UTC)

    # Remove pending group
    await db.execute(
        delete(TelegramPendingGroup).where(
            TelegramPendingGroup.id == pending_group_id
        )
    )

    await db.commit()
    await db.refresh(persona)

    return {"ok": True, "telegram": persona.telegram}


async def unassign_group(db: AsyncSession, *, persona_id: uuid.UUID) -> dict:
    """Remove group assignment from a persona."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        return {"ok": False, "error": "persona_not_found"}

    # IMPORTANT: create a NEW dict so SQLAlchemy detects the JSONB change
    tg = dict(persona.telegram or {})
    tg.pop("groupe", None)
    tg.pop("groupe_title", None)
    tg.pop("topics", None)
    tg.pop("topic", None)
    persona.telegram = tg
    persona.updated_at = datetime.now(UTC)
    await db.commit()

    return {"ok": True}


# ── Briefs / Notifications ────────────────────────────────────────


async def _get_bot_token(db: AsyncSession) -> str | None:
    """Get the Telegram bot token from workspace settings."""
    stmt = select(WorkspaceSettings).limit(1)
    settings = (await db.execute(stmt)).scalar_one_or_none()
    if not settings:
        return None
    return settings.tg_bot_token


async def send_message(
    db: AsyncSession,
    *,
    chat_id: int,
    text: str,
    topic_id: int | None = None,
    parse_mode: str = "HTML",
) -> dict:
    """Send a message via the Telegram Bot API.

    Args:
        chat_id: Telegram chat ID (DM or group)
        text: Message text (supports HTML by default)
        topic_id: Forum topic thread ID (for sending to a specific topic in a group)
        parse_mode: "HTML" or "Markdown"
    """
    token = await _get_bot_token(db)
    if not token:
        return {"ok": False, "error": "bot_token_not_configured"}

    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if topic_id:
        payload["message_thread_id"] = topic_id

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{TG_API}/bot{token}/sendMessage",
                json=payload,
            )
            result = resp.json()
    except Exception as e:
        logger.error("Telegram API error: %s", e)
        return {"ok": False, "error": f"api_error: {str(e)[:100]}"}

    if not result.get("ok"):
        logger.warning("Telegram sendMessage failed: %s", result)
        return {"ok": False, "error": result.get("description", "unknown")}

    return {"ok": True, "message_id": result["result"]["message_id"]}


async def send_brief(
    db: AsyncSession,
    *,
    persona_id: uuid.UUID,
    text: str,
    topic_name: str | None = None,
) -> dict:
    """Send a brief/notification to a persona's Telegram.

    Routing priority:
    1. Group topic (if persona has a group with the matching topic)
    2. Group (general, if no topic match)
    3. DM (if no group is assigned)

    Args:
        persona_id: Target persona
        text: Message text (HTML)
        topic_name: Topic name to route to (e.g. "veille", "alertes", "stats").
                    Falls back to the default topic if not specified.
    """
    persona = await db.get(Persona, persona_id)
    if not persona:
        return {"ok": False, "error": "persona_not_found"}

    tg = persona.telegram or {}
    if not tg.get("chat_id") and not tg.get("groupe"):
        return {"ok": False, "error": "persona_not_linked"}

    # Try group topic first
    if tg.get("groupe"):
        topics = tg.get("topics", {})
        topic_id = None
        if topic_name and topic_name in topics:
            topic_id = topics[topic_name]
        elif tg.get("topic"):
            topic_id = tg["topic"]

        return await send_message(
            db,
            chat_id=tg["groupe"],
            text=text,
            topic_id=topic_id,
        )

    # Fallback: DM
    return await send_message(
        db,
        chat_id=tg["chat_id"],
        text=text,
    )


async def send_brief_all(
    db: AsyncSession,
    *,
    text: str,
    topic_name: str | None = None,
) -> dict:
    """Send a brief to ALL linked personas."""
    stmt = select(Persona).where(Persona.telegram.isnot(None))
    personas = (await db.execute(stmt)).scalars().all()

    results = []
    for p in personas:
        tg = p.telegram or {}
        if not tg.get("chat_id") and not tg.get("groupe"):
            continue
        r = await send_brief(db, persona_id=p.id, text=text, topic_name=topic_name)
        results.append({"persona_id": str(p.id), **r})

    return {"ok": True, "sent": len([r for r in results if r.get("ok")]), "results": results}


async def send_alert(
    db: AsyncSession,
    *,
    module: str,
    event_type: str,
    message: str,
    level: str = "warning",
) -> dict:
    """Send an alert notification to the global alert chat + all personas with alertes topic.

    Called by the log/event system when an alert rule fires.
    """
    # Get the global alert chat from settings
    stmt = select(WorkspaceSettings).limit(1)
    settings = (await db.execute(stmt)).scalar_one_or_none()

    emoji = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(level, "ℹ️")
    html = (
        f"{emoji} <b>Alerte {module}</b>\n"
        f"<code>{event_type}</code>\n\n"
        f"{message}"
    )

    results = []

    # Send to global alert chat if configured
    if settings and settings.tg_chat_id:
        try:
            global_chat_id = int(settings.tg_chat_id)
            r = await send_message(db, chat_id=global_chat_id, text=html)
            results.append({"target": "global", **r})
        except (ValueError, TypeError):
            pass

    # Send to each persona's "alertes" topic
    stmt2 = select(Persona).where(Persona.telegram.isnot(None))
    personas = (await db.execute(stmt2)).scalars().all()

    for p in personas:
        tg = p.telegram or {}
        topics = tg.get("topics", {})
        if tg.get("groupe") and "alertes" in topics:
            r = await send_message(
                db,
                chat_id=tg["groupe"],
                text=html,
                topic_id=topics["alertes"],
            )
            results.append({"target": f"persona:{p.id}", **r})

    return {
        "ok": True,
        "sent": len([r for r in results if r.get("ok")]),
        "results": results,
    }
