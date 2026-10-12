from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scenario import PlageHoraire, Run, Scenario
from app.schemas.scenario import (
    PlageHoraireCreate,
    PlageHoraireUpdate,
    RunCreate,
    RunUpdate,
    ScenarioCreate,
    ScenarioUpdate,
    ScenariosOverview,
)


# --- Scenarios ----------------------------------------------------------------

async def list_scenarios(
    db: AsyncSession,
    *,
    origin: str | None = None,
    plateforme: str | None = None,
    active: bool | None = None,
) -> Sequence[Scenario]:
    q = select(Scenario).order_by(Scenario.name)
    if origin:
        q = q.where(Scenario.origin == origin)
    if plateforme:
        q = q.where(Scenario.plateforme == plateforme)
    if active is not None:
        q = q.where(Scenario.active == active)
    result = await db.execute(q)
    return result.scalars().all()


async def get_scenario(db: AsyncSession, scenario_id: UUID) -> Scenario | None:
    return await db.get(Scenario, scenario_id)


async def create_scenario(db: AsyncSession, data: ScenarioCreate) -> Scenario:
    scenario = Scenario(**data.model_dump())
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def update_scenario(db: AsyncSession, scenario: Scenario, data: ScenarioUpdate) -> Scenario:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(scenario, key, value)
    await db.commit()
    await db.refresh(scenario)
    return scenario


async def delete_scenario(db: AsyncSession, scenario: Scenario) -> None:
    await db.delete(scenario)
    await db.commit()


# --- Runs ---------------------------------------------------------------------

async def list_runs(
    db: AsyncSession,
    *,
    scenario_id: UUID | None = None,
    status: str | None = None,
) -> Sequence[Run]:
    q = select(Run).order_by(Run.created_at.desc())
    if scenario_id:
        q = q.where(Run.scenario_id == scenario_id)
    if status:
        q = q.where(Run.status == status)
    result = await db.execute(q)
    return result.scalars().all()


async def get_run(db: AsyncSession, run_id: UUID) -> Run | None:
    return await db.get(Run, run_id)


async def create_run(db: AsyncSession, data: RunCreate) -> Run:
    run = Run(**data.model_dump())
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def update_run(db: AsyncSession, run: Run, data: RunUpdate) -> Run:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(run, key, value)
    await db.commit()
    await db.refresh(run)
    return run


async def delete_run(db: AsyncSession, run: Run) -> None:
    await db.delete(run)
    await db.commit()


# --- Plages Horaires ----------------------------------------------------------

async def list_plages(db: AsyncSession) -> Sequence[PlageHoraire]:
    result = await db.execute(select(PlageHoraire).order_by(PlageHoraire.name))
    return result.scalars().all()


async def get_plage(db: AsyncSession, plage_id: UUID) -> PlageHoraire | None:
    return await db.get(PlageHoraire, plage_id)


async def create_plage(db: AsyncSession, data: PlageHoraireCreate) -> PlageHoraire:
    plage = PlageHoraire(**data.model_dump())
    db.add(plage)
    await db.commit()
    await db.refresh(plage)
    return plage


async def update_plage(db: AsyncSession, plage: PlageHoraire, data: PlageHoraireUpdate) -> PlageHoraire:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(plage, key, value)
    await db.commit()
    await db.refresh(plage)
    return plage


async def delete_plage(db: AsyncSession, plage: PlageHoraire) -> None:
    await db.delete(plage)
    await db.commit()


# --- Overview -----------------------------------------------------------------

async def get_overview(db: AsyncSession) -> ScenariosOverview:
    total = int((await db.execute(select(func.count(Scenario.id)))).scalar() or 0)
    active = int((await db.execute(
        select(func.count(Scenario.id)).where(Scenario.active.is_(True))
    )).scalar() or 0)
    total_runs = int((await db.execute(select(func.count(Run.id)))).scalar() or 0)
    running = int((await db.execute(
        select(func.count(Run.id)).where(Run.status == "running")
    )).scalar() or 0)
    total_plages = int((await db.execute(select(func.count(PlageHoraire.id)))).scalar() or 0)

    return ScenariosOverview(
        total_scenarios=total,
        active_scenarios=active,
        total_runs=total_runs,
        running_now=running,
        total_plages=total_plages,
    )
