from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.persona import PersonaCreate, PersonaOut, PersonaUpdate
from app.services import personas as service

router = APIRouter()


@router.get("", response_model=list[PersonaOut])
async def list_personas(db: AsyncSession = Depends(get_db)):
    return await service.list_personas(db)


@router.get("/{persona_id}", response_model=PersonaOut)
async def get_persona(persona_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_persona(db, persona_id)
    if not p:
        raise HTTPException(404, "persona not found")
    return p


@router.post("", response_model=PersonaOut, status_code=201)
async def create_persona(data: PersonaCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_persona(db, data)


@router.patch("/{persona_id}", response_model=PersonaOut)
async def update_persona(persona_id: UUID, data: PersonaUpdate, db: AsyncSession = Depends(get_db)):
    p = await service.get_persona(db, persona_id)
    if not p:
        raise HTTPException(404, "persona not found")
    return await service.update_persona(db, p, data)


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(persona_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_persona(db, persona_id)
    if not p:
        raise HTTPException(404, "persona not found")
    await service.delete_persona(db, p)
