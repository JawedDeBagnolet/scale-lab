from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Scenario -----------------------------------------------------------------

class ScenarioBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    origin: str = Field(max_length=20)  # spontane, login, creation
    couple: str | None = Field(default=None, max_length=100)
    plateforme: str | None = Field(default=None, max_length=10)
    slots: list[dict] | None = None
    steps: list[dict] | None = None
    loop: bool = False
    active: bool = True
    description: str | None = None


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    origin: str | None = Field(default=None, max_length=20)
    couple: str | None = Field(default=None, max_length=100)
    plateforme: str | None = Field(default=None, max_length=10)
    slots: list[dict] | None = None
    steps: list[dict] | None = None
    loop: bool | None = None
    active: bool | None = None
    description: str | None = None


class ScenarioOut(ScenarioBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Run ----------------------------------------------------------------------

class RunBase(BaseModel):
    scenario_id: UUID
    comptes: list | None = None
    current_step: int = 0
    status: str = Field(default="pending", max_length=20)


class RunCreate(RunBase):
    pass


class RunUpdate(BaseModel):
    current_step: int | None = None
    status: str | None = Field(default=None, max_length=20)
    blocked_accounts: list | None = None
    journal: list[dict] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RunOut(RunBase):
    id: UUID
    blocked_accounts: list | None
    journal: list[dict] | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Plage Horaire ------------------------------------------------------------

class PlageHoraireBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    days: list | None = None  # [0..6]
    ranges: list[dict] | None = None  # [{start, end}]


class PlageHoraireCreate(PlageHoraireBase):
    pass


class PlageHoraireUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    days: list | None = None
    ranges: list[dict] | None = None


class PlageHoraireOut(PlageHoraireBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Overview -----------------------------------------------------------------

class ScenariosOverview(BaseModel):
    total_scenarios: int
    active_scenarios: int
    total_runs: int
    running_now: int
    total_plages: int
