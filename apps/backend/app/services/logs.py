from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import AlertRule, Event, Incident
from app.schemas.log import AlertRuleCreate, EventCreate, LogStats
from app.ws import manager as ws_manager


# --- Events -------------------------------------------------------------------

async def list_events(
    db: AsyncSession,
    *,
    module: str | None = None,
    level: str | None = None,
    target: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Event]:
    q = select(Event).order_by(Event.timestamp.desc()).limit(limit).offset(offset)
    if module:
        q = q.where(Event.module == module)
    if level:
        q = q.where(Event.level == level)
    if target:
        q = q.where(Event.target.ilike(f"%{target}%"))
    result = await db.execute(q)
    return result.scalars().all()


async def _broadcast_event(event: Event) -> None:
    """Send a log event to all connected WebSocket clients."""
    if ws_manager.count == 0:
        return
    await ws_manager.broadcast({
        "type": "log_event",
        "id": str(event.id),
        "timestamp": event.timestamp.isoformat(),
        "module": event.module,
        "event_type": event.event_type,
        "level": event.level,
        "target": event.target,
        "cause": event.cause,
        "code": event.code,
        "message": event.message,
        "meta": event.meta,
    })


async def create_event(db: AsyncSession, data: EventCreate) -> Event:
    e = Event(**data.model_dump())
    db.add(e)
    await db.commit()
    await db.refresh(e)
    await _broadcast_event(e)
    # Check alert rules
    if e.level in ("warning", "error", "critical"):
        await _evaluate_alert_rules(db, e)
    return e


async def _evaluate_alert_rules(db: AsyncSession, event: Event) -> None:
    """Check if any alert rule matches this event and fire Telegram notification."""
    import logging
    log = logging.getLogger("logs.alerts")

    try:
        # Find matching rules
        stmt = select(AlertRule).where(
            AlertRule.module == event.module,
            AlertRule.tg_enabled.is_(True),
        )
        rules = (await db.execute(stmt)).scalars().all()

        if not rules:
            return

        now = datetime.now(UTC)
        window = now - timedelta(hours=1)

        for rule in rules:
            # Check if event_type matches (empty = match all for module)
            if rule.event_type and rule.event_type != event.event_type:
                continue

            # Count recent errors for this module+type in the last hour
            count_stmt = select(func.count(Event.id)).where(
                Event.module == event.module,
                Event.level.in_(["warning", "error", "critical"]),
                Event.timestamp >= window,
            )
            if rule.event_type:
                count_stmt = count_stmt.where(Event.event_type == rule.event_type)

            recent_count = await db.scalar(count_stmt) or 0

            # Fire if threshold is reached
            if recent_count >= rule.threshold_errors:
                from app.services.telegram import send_alert
                await send_alert(
                    db,
                    module=event.module,
                    event_type=event.event_type,
                    message=(
                        f"{event.message}\n\n"
                        f"<i>{recent_count} erreur(s) en 1h"
                        f"{' — ' + event.target if event.target else ''}</i>"
                    ),
                    level=event.level,
                )
                log.info(
                    "Alert fired: module=%s type=%s count=%d threshold=%d",
                    event.module, event.event_type, recent_count, rule.threshold_errors,
                )
    except Exception:
        log.exception("Failed to evaluate alert rules")


async def emit_event(
    *,
    module: str,
    event_type: str,
    message: str,
    level: str = "info",
    target: str | None = None,
    cause: str | None = None,
    code: str | None = None,
    meta: dict | None = None,
) -> None:
    """Fire-and-forget: persist an event and broadcast it via WebSocket.

    Use this from background services (engine, USB monitor) that don't have
    an active request-scoped DB session.
    """
    from app.db import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            e = Event(
                module=module,
                event_type=event_type,
                level=level,
                target=target,
                cause=cause,
                code=code,
                message=message,
                meta=meta,
            )
            db.add(e)
            await db.commit()
            await db.refresh(e)
            await _broadcast_event(e)
            # Check alert rules for warnings/errors
            if level in ("warning", "error", "critical"):
                await _evaluate_alert_rules(db, e)
    except Exception:
        # Never crash a background service because of a log write failure
        import logging
        logging.getLogger("logs").exception("Failed to emit event")


async def get_stats(db: AsyncSession) -> LogStats:
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)

    total = await db.scalar(select(func.count(Event.id)))
    errors = await db.scalar(
        select(func.count(Event.id)).where(
            Event.level.in_(["error", "critical"]),
            Event.timestamp >= day_ago,
        )
    )
    open_incidents = await db.scalar(
        select(func.count(Incident.id)).where(Incident.status == "open")
    )

    # Events per module (top modules)
    q = select(Event.module, func.count(Event.id)).group_by(Event.module)
    result = await db.execute(q)
    modules = {row[0]: row[1] for row in result.all()}

    return LogStats(
        total_events=total or 0,
        errors_24h=errors or 0,
        open_incidents=open_incidents or 0,
        modules=modules,
    )


# --- Incidents ----------------------------------------------------------------

async def list_incidents(
    db: AsyncSession,
    *,
    module: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> Sequence[Incident]:
    q = select(Incident).order_by(Incident.last_seen.desc()).limit(limit)
    if module:
        q = q.where(Incident.module == module)
    if status:
        q = q.where(Incident.status == status)
    result = await db.execute(q)
    return result.scalars().all()


async def get_incident(db: AsyncSession, incident_id: UUID) -> Incident | None:
    return await db.get(Incident, incident_id)


async def update_incident(db: AsyncSession, incident: Incident, data: dict) -> Incident:
    for k, v in data.items():
        if v is not None:
            setattr(incident, k, v)
    await db.commit()
    await db.refresh(incident)
    return incident


# --- Alert rules --------------------------------------------------------------

async def list_alert_rules(db: AsyncSession) -> Sequence[AlertRule]:
    result = await db.execute(select(AlertRule).order_by(AlertRule.module))
    return result.scalars().all()


async def create_alert_rule(db: AsyncSession, data: AlertRuleCreate) -> AlertRule:
    r = AlertRule(**data.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


async def delete_alert_rule(db: AsyncSession, rule: AlertRule) -> None:
    await db.delete(rule)
    await db.commit()
