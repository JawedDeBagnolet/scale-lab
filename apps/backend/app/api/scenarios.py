from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.scenario import (
    PlageHoraireCreate,
    PlageHoraireOut,
    PlageHoraireUpdate,
    RunCreate,
    RunOut,
    RunUpdate,
    ScenarioCreate,
    ScenarioOut,
    ScenarioUpdate,
    ScenariosOverview,
)
from app.services import scenarios as service

router = APIRouter()


# --- Overview -----------------------------------------------------------------

@router.get("/overview", response_model=ScenariosOverview)
async def get_overview(db: AsyncSession = Depends(get_db)):
    return await service.get_overview(db)


# --- Scenarios ----------------------------------------------------------------

@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(
    origin: str | None = Query(None),
    plateforme: str | None = Query(None),
    active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_scenarios(db, origin=origin, plateforme=plateforme, active=active)


@router.get("/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(scenario_id: UUID, db: AsyncSession = Depends(get_db)):
    s = await service.get_scenario(db, scenario_id)
    if not s:
        raise HTTPException(404, "scenario not found")
    return s


@router.post("", response_model=ScenarioOut, status_code=201)
async def create_scenario(data: ScenarioCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_scenario(db, data)


@router.patch("/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(scenario_id: UUID, data: ScenarioUpdate, db: AsyncSession = Depends(get_db)):
    s = await service.get_scenario(db, scenario_id)
    if not s:
        raise HTTPException(404, "scenario not found")
    return await service.update_scenario(db, s, data)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: UUID, db: AsyncSession = Depends(get_db)):
    s = await service.get_scenario(db, scenario_id)
    if not s:
        raise HTTPException(404, "scenario not found")
    await service.delete_scenario(db, s)


# --- Runs ---------------------------------------------------------------------

@router.get("/runs/list", response_model=list[RunOut])
async def list_runs(
    scenario_id: UUID | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_runs(db, scenario_id=scenario_id, status=status)


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    r = await service.get_run(db, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return r


@router.post("/runs", response_model=RunOut, status_code=201)
async def create_run(data: RunCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_run(db, data)


@router.patch("/runs/{run_id}", response_model=RunOut)
async def update_run(run_id: UUID, data: RunUpdate, db: AsyncSession = Depends(get_db)):
    r = await service.get_run(db, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return await service.update_run(db, r, data)


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run_id: UUID, db: AsyncSession = Depends(get_db)):
    r = await service.get_run(db, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    await service.delete_run(db, r)


# --- Plages Horaires ----------------------------------------------------------

@router.get("/plages", response_model=list[PlageHoraireOut])
async def list_plages(db: AsyncSession = Depends(get_db)):
    return await service.list_plages(db)


@router.post("/plages", response_model=PlageHoraireOut, status_code=201)
async def create_plage(data: PlageHoraireCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_plage(db, data)


@router.patch("/plages/{plage_id}", response_model=PlageHoraireOut)
async def update_plage(plage_id: UUID, data: PlageHoraireUpdate, db: AsyncSession = Depends(get_db)):
    p = await service.get_plage(db, plage_id)
    if not p:
        raise HTTPException(404, "plage horaire not found")
    return await service.update_plage(db, p, data)


@router.delete("/plages/{plage_id}", status_code=204)
async def delete_plage(plage_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_plage(db, plage_id)
    if not p:
        raise HTTPException(404, "plage horaire not found")
    await service.delete_plage(db, p)
