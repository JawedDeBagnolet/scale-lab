from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Collection ---------------------------------------------------------------

class CollectionBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    collection_type: str = Field(max_length=20)  # assembled, variable
    persona_id: UUID | None = None
    plateforme: str | None = Field(default=None, max_length=10)
    post_type: str | None = Field(default=None, max_length=20)
    captions: list | None = None
    media_ids: list | None = None


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    collection_type: str | None = Field(default=None, max_length=20)
    persona_id: UUID | None = None
    plateforme: str | None = Field(default=None, max_length=10)
    post_type: str | None = Field(default=None, max_length=20)
    captions: list | None = None
    media_ids: list | None = None


class CollectionOut(CollectionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Media --------------------------------------------------------------------

class MediaBase(BaseModel):
    persona_id: UUID | None = None
    media_type: str = Field(max_length=10)  # image, video, audio
    url: str
    duration: int | None = None
    tags: list | None = None
    folder: str | None = Field(default=None, max_length=100)
    used: bool = False


class MediaCreate(MediaBase):
    pass


class MediaUpdate(BaseModel):
    persona_id: UUID | None = None
    media_type: str | None = Field(default=None, max_length=10)
    url: str | None = None
    duration: int | None = None
    tags: list | None = None
    folder: str | None = Field(default=None, max_length=100)
    used: bool | None = None


class MediaOut(MediaBase):
    id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Template -----------------------------------------------------------------

class TemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    persona_id: UUID | None = None
    plateforme: str | None = Field(default=None, max_length=10)
    template_type: str = Field(default="post", max_length=20)
    layers: list[dict] | None = None
    variables: dict | None = None
    collection_id: UUID | None = None


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    persona_id: UUID | None = None
    plateforme: str | None = Field(default=None, max_length=10)
    template_type: str | None = Field(default=None, max_length=20)
    layers: list[dict] | None = None
    variables: dict | None = None
    collection_id: UUID | None = None


class TemplateOut(TemplateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Campagne -----------------------------------------------------------------

class CampagneBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    icon: str | None = Field(default=None, max_length=50)
    persona_id: UUID | None = None
    plateforme: str | None = Field(default=None, max_length=10)
    status: str = Field(default="draft", max_length=20)
    scenarios: list | None = None
    waves: list[dict] | None = None
    planning: dict | None = None


class CampagneCreate(CampagneBase):
    pass


class CampagneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    icon: str | None = Field(default=None, max_length=50)
    persona_id: UUID | None = None
    plateforme: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None, max_length=20)
    scenarios: list | None = None
    waves: list[dict] | None = None
    planning: dict | None = None


class CampagneOut(CampagneBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Publication --------------------------------------------------------------

class PublicationBase(BaseModel):
    compte_id: UUID
    campagne_id: UUID | None = None
    media_id: UUID | None = None
    caption: str | None = None
    scheduled_at: datetime | None = None
    status: str = Field(default="planned", max_length=20)
    platform_post_id: str | None = Field(default=None, max_length=200)


class PublicationCreate(PublicationBase):
    pass


class PublicationUpdate(BaseModel):
    campagne_id: UUID | None = None
    media_id: UUID | None = None
    caption: str | None = None
    scheduled_at: datetime | None = None
    status: str | None = Field(default=None, max_length=20)
    platform_post_id: str | None = Field(default=None, max_length=200)


class PublicationOut(PublicationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Overview -----------------------------------------------------------------

class PostingOverview(BaseModel):
    total_collections: int
    total_medias: int
    total_templates: int
    total_campagnes: int
    active_campagnes: int
    total_publications: int
    published: int
    planned: int
    failed: int
