from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Domain -------------------------------------------------------------------

class DomainBase(BaseModel):
    host: str
    max_active_links: int = 500
    alert_threshold: int = 450


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    host: str | None = None
    max_active_links: int | None = None
    alert_threshold: int | None = None


class DomainOut(DomainBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- TrackedLink --------------------------------------------------------------

class TrackedLinkBase(BaseModel):
    domain_id: UUID | None = None
    slug: str
    link_type: str = "direct"
    destination: str
    plateforme: str
    persona_id: UUID | None = None
    compte_id: UUID | None = None
    active: bool = True
    group_name: str | None = None


class TrackedLinkCreate(TrackedLinkBase):
    pass


class TrackedLinkUpdate(BaseModel):
    domain_id: UUID | None = None
    slug: str | None = None
    link_type: str | None = None
    destination: str | None = None
    plateforme: str | None = None
    persona_id: UUID | None = None
    compte_id: UUID | None = None
    active: bool | None = None
    group_name: str | None = None


class TrackedLinkOut(TrackedLinkBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- ClickEvent ---------------------------------------------------------------

class ClickEventBase(BaseModel):
    country: str
    city: str
    device: str
    browser: str
    referrer: str | None = None


class ClickEventCreate(ClickEventBase):
    pass


class ClickEventOut(ClickEventBase):
    id: UUID
    link_id: UUID
    clicked_at: datetime
    model_config = {"from_attributes": True}


# --- LinkStats ----------------------------------------------------------------

class LinkStats(BaseModel):
    clicks_total: int
    clicks_7d: int
    clicks_today: int
    unique_countries: int
