from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.comportement import PresetCreate, PresetOut, PresetUpdate
from app.services import comportements as service

router = APIRouter()


@router.get("/", response_model=list[PresetOut])
async def list_presets(
    plateforme: str | None = Query(None),
    session_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_presets(
        db, plateforme=plateforme, session_type=session_type
    )


@router.get("/{preset_id}", response_model=PresetOut)
async def get_preset(preset_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_preset(db, preset_id)
    if not p:
        raise HTTPException(404, "preset not found")
    return p


@router.post("/", response_model=PresetOut, status_code=201)
async def create_preset(data: PresetCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_preset(db, data)


@router.patch("/{preset_id}", response_model=PresetOut)
async def update_preset(
    preset_id: UUID, data: PresetUpdate, db: AsyncSession = Depends(get_db)
):
    p = await service.get_preset(db, preset_id)
    if not p:
        raise HTTPException(404, "preset not found")
    return await service.update_preset(db, p, data.model_dump(exclude_unset=True))


@router.delete("/{preset_id}", status_code=204)
async def delete_preset(preset_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_preset(db, preset_id)
    if not p:
        raise HTTPException(404, "preset not found")
    await service.delete_preset(db, p)
