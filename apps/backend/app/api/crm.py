from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.crm import (
    CrmOverview,
    FanCreate,
    FanOut,
    FanUpdate,
    ScriptCreate,
    ScriptOut,
    ScriptUpdate,
    TransactionCreate,
    TransactionOut,
)
from app.services import crm as service

router = APIRouter()


# --- Overview -----------------------------------------------------------------

@router.get("/overview", response_model=CrmOverview)
async def get_overview(db: AsyncSession = Depends(get_db)):
    return await service.get_overview(db)


# --- Fans ---------------------------------------------------------------------

@router.get("/fans", response_model=list[FanOut])
async def list_fans(
    creator_id: UUID | None = Query(None),
    platform_origin: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_fans(db, creator_id=creator_id, platform_origin=platform_origin)


@router.get("/fans/{fan_id}", response_model=FanOut)
async def get_fan(fan_id: UUID, db: AsyncSession = Depends(get_db)):
    f = await service.get_fan(db, fan_id)
    if not f:
        raise HTTPException(404, "fan not found")
    return f


@router.post("/fans", response_model=FanOut, status_code=201)
async def create_fan(data: FanCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_fan(db, data)


@router.patch("/fans/{fan_id}", response_model=FanOut)
async def update_fan(fan_id: UUID, data: FanUpdate, db: AsyncSession = Depends(get_db)):
    f = await service.get_fan(db, fan_id)
    if not f:
        raise HTTPException(404, "fan not found")
    return await service.update_fan(db, f, data)


# --- Transactions -------------------------------------------------------------

@router.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(
    fan_id: UUID | None = Query(None),
    creator_id: UUID | None = Query(None),
    type: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_transactions(
        db,
        fan_id=fan_id,
        creator_id=creator_id,
        transaction_type=type,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/transactions", response_model=TransactionOut, status_code=201)
async def create_transaction(data: TransactionCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_transaction(db, data)


# --- Scripts ------------------------------------------------------------------

@router.get("/scripts", response_model=list[ScriptOut])
async def list_scripts(
    active: bool | None = Query(None),
    folder: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_scripts(db, active=active, folder=folder)


@router.get("/scripts/{script_id}", response_model=ScriptOut)
async def get_script(script_id: UUID, db: AsyncSession = Depends(get_db)):
    s = await service.get_script(db, script_id)
    if not s:
        raise HTTPException(404, "script not found")
    return s


@router.post("/scripts", response_model=ScriptOut, status_code=201)
async def create_script(data: ScriptCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_script(db, data)


@router.patch("/scripts/{script_id}", response_model=ScriptOut)
async def update_script(
    script_id: UUID, data: ScriptUpdate, db: AsyncSession = Depends(get_db),
):
    s = await service.get_script(db, script_id)
    if not s:
        raise HTTPException(404, "script not found")
    return await service.update_script(db, s, data)


@router.delete("/scripts/{script_id}", status_code=204)
async def delete_script(script_id: UUID, db: AsyncSession = Depends(get_db)):
    s = await service.get_script(db, script_id)
    if not s:
        raise HTTPException(404, "script not found")
    await service.delete_script(db, s)
