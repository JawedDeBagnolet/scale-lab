from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.referentiel import MarcheOut, NicheOut
from app.services import referentiels as service

router = APIRouter()


@router.get("/niches", response_model=list[NicheOut])
async def list_niches(db: AsyncSession = Depends(get_db)):
    return await service.list_niches(db)


@router.get("/marches", response_model=list[MarcheOut])
async def list_marches(db: AsyncSession = Depends(get_db)):
    return await service.list_marches(db)
