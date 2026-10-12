from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.target import TargetBulkCreate, TargetCreate, TargetOut, TargetUpdate
from app.services import targets as service

router = APIRouter()


@router.get("/", response_model=list[TargetOut])
async def list_targets(
    plateforme: str | None = Query(None),
    market: str | None = Query(None),
    niche_id: int | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_targets(
        db, plateforme=plateforme, market=market, niche_id=niche_id, status=status
    )


@router.get("/{target_id}", response_model=TargetOut)
async def get_target(target_id: UUID, db: AsyncSession = Depends(get_db)):
    t = await service.get_target(db, target_id)
    if not t:
        raise HTTPException(404, "target not found")
    return t


@router.post("/", response_model=TargetOut, status_code=201)
async def create_target(data: TargetCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_target(db, data)


@router.post("/bulk", response_model=list[TargetOut], status_code=201)
async def bulk_create(data: TargetBulkCreate, db: AsyncSession = Depends(get_db)):
    return await service.bulk_create(db, data.targets)


@router.patch("/{target_id}", response_model=TargetOut)
async def update_target(
    target_id: UUID, data: TargetUpdate, db: AsyncSession = Depends(get_db)
):
    t = await service.get_target(db, target_id)
    if not t:
        raise HTTPException(404, "target not found")
    return await service.update_target(db, t, data.model_dump(exclude_unset=True))


@router.delete("/{target_id}", status_code=204)
async def delete_target(target_id: UUID, db: AsyncSession = Depends(get_db)):
    t = await service.get_target(db, target_id)
    if not t:
        raise HTTPException(404, "target not found")
    await service.delete_target(db, t)
