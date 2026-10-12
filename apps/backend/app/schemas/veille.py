from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


# --- VeilleSource -----------------------------------------------------------

class VeilleSourceBase(BaseModel):
    handle: str
    plateforme: str
    niche_id: int | None = None
    active: bool = True


class VeilleSourceCreate(VeilleSourceBase):
    pass


class VeilleSourceUpdate(BaseModel):
    handle: str | None = None
    plateforme: str | None = None
    niche_id: int | None = None
    active: bool | None = None


class VeilleSourceOut(VeilleSourceBase):
    id: UUID
    last_checked: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Inspiration ------------------------------------------------------------

class InspirationBase(BaseModel):
    source_id: UUID
    url: str
    media_type: str
    caption: str | None = None
    engagement: int = 0
    status: str = "new"


class InspirationUpdate(BaseModel):
    status: str | None = None
    caption: str | None = None
    engagement: int | None = None


class InspirationOut(InspirationBase):
    id: UUID
    saved_at: datetime
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Favorite ---------------------------------------------------------------

class FavoriteBase(BaseModel):
    inspiration_id: UUID
    album_id: UUID | None = None
    notes: str | None = None


class FavoriteCreate(FavoriteBase):
    pass


class FavoriteOut(FavoriteBase):
    id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Snipe ------------------------------------------------------------------

class SnipeBase(BaseModel):
    inspiration_id: UUID
    target_persona_id: UUID | None = None
    priority: str = "medium"
    status: str = "pending"
    due_date: date | None = None


class SnipeCreate(SnipeBase):
    pass


class SnipeUpdate(BaseModel):
    target_persona_id: UUID | None = None
    priority: str | None = None
    status: str | None = None
    due_date: date | None = None


class SnipeOut(SnipeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Album ------------------------------------------------------------------

class AlbumBase(BaseModel):
    name: str
    description: str | None = None
    persona_id: UUID | None = None


class AlbumCreate(AlbumBase):
    pass


class AlbumUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    persona_id: UUID | None = None


class AlbumOut(AlbumBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Overview ---------------------------------------------------------------

class VeilleOverview(BaseModel):
    total_sources: int
    new_inspirations: int
    pending_snipes: int
    total_albums: int
