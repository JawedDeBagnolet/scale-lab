from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TargetBase(BaseModel):
    handle: str
    plateforme: str
    market: str | None = None
    niche_id: int | None = None
    status: str | None = "ok"
    source: str | None = "manual"


class TargetCreate(TargetBase):
    pass


class TargetUpdate(BaseModel):
    handle: str | None = None
    plateforme: str | None = None
    market: str | None = None
    niche_id: int | None = None
    status: str | None = None
    source: str | None = None


class TargetOut(TargetBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TargetBulkCreate(BaseModel):
    """Import en masse : une liste de targets."""

    targets: list[TargetCreate]
