from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.statistique import DailyStatBulkCreate, DailyStatOut, StatsOverview
from app.services import statistiques as service

router = APIRouter()


@router.get("", response_model=list[DailyStatOut])
async def list_stats(
    compte_id: UUID = Query(...),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    rows = await service.list_stats(db, compte_id, date_from=date_from, date_to=date_to)
    return [DailyStatOut.from_model(r) for r in rows]


@router.get("/overview", response_model=StatsOverview)
async def get_overview(
    compte_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_overview(db, compte_id)


@router.post("/bulk", response_model=list[DailyStatOut], status_code=201)
async def bulk_create(data: DailyStatBulkCreate, db: AsyncSession = Depends(get_db)):
    rows = await service.bulk_create_stats(db, data.stats)
    return [DailyStatOut.from_model(r) for r in rows]
