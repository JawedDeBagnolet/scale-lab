from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.log import (
    AlertRuleCreate,
    AlertRuleOut,
    EventCreate,
    EventOut,
    IncidentOut,
    IncidentUpdate,
    LogStats,
)
from app.services import logs as service

router = APIRouter()


# --- Events -------------------------------------------------------------------

@router.get("/events", response_model=list[EventOut])
async def list_events(
    module: str | None = Query(None),
    level: str | None = Query(None),
    target: str | None = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_events(
        db, module=module, level=level, target=target, limit=limit, offset=offset
    )


@router.post("/events", response_model=EventOut, status_code=201)
async def create_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_event(db, data)


@router.get("/stats", response_model=LogStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await service.get_stats(db)


# --- Incidents ----------------------------------------------------------------

@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    module: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_incidents(db, module=module, status=status, limit=limit)


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
async def update_incident(
    incident_id: UUID, data: IncidentUpdate, db: AsyncSession = Depends(get_db)
):
    inc = await service.get_incident(db, incident_id)
    if not inc:
        raise HTTPException(404, "incident not found")
    return await service.update_incident(db, inc, data.model_dump(exclude_unset=True))


# --- Alert rules --------------------------------------------------------------

@router.get("/rules", response_model=list[AlertRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)):
    return await service.list_alert_rules(db)


@router.post("/rules", response_model=AlertRuleOut, status_code=201)
async def create_rule(data: AlertRuleCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_alert_rule(db, data)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)):
    from app.models.log import AlertRule

    r = await db.get(AlertRule, rule_id)
    if not r:
        raise HTTPException(404, "rule not found")
    await service.delete_alert_rule(db, r)
