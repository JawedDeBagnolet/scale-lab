from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Fan ----------------------------------------------------------------------

class FanBase(BaseModel):
    pseudo: str = Field(min_length=1, max_length=100)
    creator_id: UUID
    compte_id: UUID | None = None
    platform_origin: str = Field(max_length=10)
    joined_at: datetime
    total_spent: int = 0
    last_activity: datetime | None = None
    notes: str | None = None


class FanCreate(FanBase):
    pass


class FanUpdate(BaseModel):
    pseudo: str | None = Field(default=None, min_length=1, max_length=100)
    creator_id: UUID | None = None
    compte_id: UUID | None = None
    platform_origin: str | None = Field(default=None, max_length=10)
    joined_at: datetime | None = None
    total_spent: int | None = None
    last_activity: datetime | None = None
    notes: str | None = None


class FanOut(FanBase):
    id: UUID
    pseudo: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Transaction --------------------------------------------------------------

class TransactionBase(BaseModel):
    fan_id: UUID
    creator_id: UUID
    transaction_type: str = Field(max_length=10)  # sub / ppv / tip
    amount: int
    script_id: UUID | None = None
    compte_id: UUID | None = None
    timestamp: datetime


class TransactionCreate(TransactionBase):
    pass


class TransactionOut(TransactionBase):
    id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Script -------------------------------------------------------------------

class ScriptBase(BaseModel):
    script_group_id: UUID | None = None
    folder: str | None = Field(default=None, max_length=100)
    active: bool = True
    priority: bool = False
    steps: list[dict] | None = None
    stats: dict | None = None


class ScriptCreate(ScriptBase):
    pass


class ScriptUpdate(BaseModel):
    script_group_id: UUID | None = None
    folder: str | None = Field(default=None, max_length=100)
    active: bool | None = None
    priority: bool | None = None
    steps: list[dict] | None = None
    stats: dict | None = None


class ScriptOut(ScriptBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- CRM Overview ------------------------------------------------------------

class CrmOverview(BaseModel):
    total_fans: int
    total_revenue: int
    avg_ltv: float
    top_script: str | None
