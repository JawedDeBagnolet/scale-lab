from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProxyBase(BaseModel):
    pool: str
    type: str
    iphone_id: UUID | None = None
    ip: str
    country: str
    latency_ms: int | None = None
    status: str | None = "online"
    blacklists: list[str] | None = []
    availability_7d: float | None = 1.0


class ProxyCreate(ProxyBase):
    pass


class ProxyUpdate(BaseModel):
    pool: str | None = None
    type: str | None = None
    iphone_id: UUID | None = None
    ip: str | None = None
    country: str | None = None
    latency_ms: int | None = None
    status: str | None = None
    blacklists: list[str] | None = None
    availability_7d: float | None = None


class ProxyOut(ProxyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
