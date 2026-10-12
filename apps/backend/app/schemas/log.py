from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EventCreate(BaseModel):
    module: str
    event_type: str
    level: str = "info"
    target: str | None = None
    cause: str | None = None
    code: str | None = None
    message: str
    meta: dict | None = None


class EventOut(BaseModel):
    id: UUID
    timestamp: datetime
    module: str
    event_type: str
    level: str
    target: str | None
    cause: str | None
    code: str | None
    message: str
    meta: dict | None
    model_config = {"from_attributes": True}


class IncidentOut(BaseModel):
    id: UUID
    module: str
    event_type: str
    target: str | None
    status: str
    event_count: int
    first_seen: datetime
    last_seen: datetime
    solutions: list | None
    related_events: list | None
    meta: dict | None
    model_config = {"from_attributes": True}


class IncidentUpdate(BaseModel):
    status: str | None = None  # open, ack, resolved


class AlertRuleCreate(BaseModel):
    module: str
    event_type: str
    threshold_errors: int = 3
    threshold_actions: int = 10
    tg_enabled: bool = True


class AlertRuleOut(BaseModel):
    id: UUID
    module: str
    event_type: str
    threshold_errors: int
    threshold_actions: int
    tg_enabled: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class LogStats(BaseModel):
    """Stats for the Logs module header."""
    total_events: int
    errors_24h: int
    open_incidents: int
    modules: dict[str, int]  # event count per module
