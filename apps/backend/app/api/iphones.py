from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.iphone import IPhoneCreate, IPhoneOut, IPhoneUpdate, TelemetryUpdate
from app.services import iphones as service

router = APIRouter()


@router.get("/", response_model=list[IPhoneOut])
async def list_iphones(
    status: str | None = Query(None),
    market: str | None = Query(None),
    rack: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_iphones(db, status=status, market=market, rack=rack)


@router.get("/{iphone_id}", response_model=IPhoneOut)
async def get_iphone(iphone_id: UUID, db: AsyncSession = Depends(get_db)):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    return iphone


@router.post("/", response_model=IPhoneOut, status_code=201)
async def create_iphone(data: IPhoneCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_iphone(db, data)


@router.patch("/{iphone_id}", response_model=IPhoneOut)
async def update_iphone(
    iphone_id: UUID, data: IPhoneUpdate, db: AsyncSession = Depends(get_db)
):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    return await service.update_iphone(db, iphone, data.model_dump(exclude_unset=True))


@router.patch("/{iphone_id}/telemetry", response_model=IPhoneOut)
async def update_telemetry(
    iphone_id: UUID, data: TelemetryUpdate, db: AsyncSession = Depends(get_db)
):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    return await service.update_telemetry(db, iphone, data)


@router.delete("/{iphone_id}", status_code=204)
async def delete_iphone(iphone_id: UUID, db: AsyncSession = Depends(get_db)):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    await service.delete_iphone(db, iphone)
