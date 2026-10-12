from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PresetBase(BaseModel):
    name: str
    plateforme: str
    session_type: str
    description: str | None = None
    is_default: bool = False
    config: dict = {}


class PresetCreate(PresetBase):
    pass


class PresetUpdate(BaseModel):
    name: str | None = None
    plateforme: str | None = None
    session_type: str | None = None
    description: str | None = None
    is_default: bool | None = None
    config: dict | None = None


class PresetOut(PresetBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
