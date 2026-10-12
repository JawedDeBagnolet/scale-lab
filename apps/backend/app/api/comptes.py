from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.compte import CompteCreate, CompteOut, CompteUpdate
from app.services import comptes as service

router = APIRouter()


@router.get("", response_model=list[CompteOut])
async def list_comptes(
    persona_id: UUID | None = Query(None),
    plateforme: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_comptes(db, persona_id=persona_id, plateforme=plateforme)


@router.get("/{compte_id}", response_model=CompteOut)
async def get_compte(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    return c


@router.post("", response_model=CompteOut, status_code=201)
async def create_compte(data: CompteCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await service.create_compte(db, data)
    except service.PersonaNotFound:
        raise HTTPException(400, "persona not found")


@router.patch("/{compte_id}", response_model=CompteOut)
async def update_compte(compte_id: UUID, data: CompteUpdate, db: AsyncSession = Depends(get_db)):
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    try:
        return await service.update_compte(db, c, data)
    except service.PersonaNotFound:
        raise HTTPException(400, "persona not found")


@router.delete("/{compte_id}", status_code=204)
async def delete_compte(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    await service.delete_compte(db, c)
