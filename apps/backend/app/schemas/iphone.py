from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TelemetryData(BaseModel):
    battery_pct: int | None = None
    charging: bool | None = None
    network_quality: str | None = None
    data_used_mb: float | None = None
    current_run: str | None = None
    current_compte: str | None = None
    last_run_at: datetime | None = None
    offline_since: datetime | None = None


class IPhoneBase(BaseModel):
    name: str
    model: str
    ios_version: str
    rack: str | None = None
    market: str | None = None
    status: str | None = "offline"
    jailbreak: bool | None = False
    max_comptes: int | None = 3
    proxy_id: UUID | None = None


class IPhoneCreate(IPhoneBase):
    pass


class IPhoneUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    ios_version: str | None = None
    rack: str | None = None
    market: str | None = None
    status: str | None = None
    jailbreak: bool | None = None
    max_comptes: int | None = None
    proxy_id: UUID | None = None


class TelemetryUpdate(BaseModel):
    battery_pct: int | None = None
    charging: bool | None = None
    network_quality: str | None = None
    data_used_mb: float | None = None
    current_run: str | None = None
    current_compte: str | None = None
    last_run_at: datetime | None = None
    offline_since: datetime | None = None


class IPhoneOut(IPhoneBase):
    id: UUID
    telemetry: dict | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
