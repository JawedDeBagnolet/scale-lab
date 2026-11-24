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
    thumbnail_url: str | None = None
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
    thumbnail_url: str | None = None
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


# --- Story Template -----------------------------------------------------------

class StoryTemplateBase(BaseModel):
    persona_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    story_type: str = Field(default="lifestyle", max_length=50)
    username: str = Field(default="", max_length=100)
    color: str = Field(default="#1b1f33", max_length=20)
    media_ids: list | None = None
    bg_idx: int = -1
    elements: list[dict] = []
    moments: list | None = None
    is_liked: bool = False


class StoryTemplateCreate(StoryTemplateBase):
    pass


class StoryTemplateUpdate(BaseModel):
    persona_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    story_type: str | None = Field(default=None, max_length=50)
    username: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=20)
    media_ids: list | None = None
    bg_idx: int | None = None
    elements: list[dict] | None = None
    moments: list | None = None
    is_liked: bool | None = None


class StoryTemplateOut(StoryTemplateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Story Planner -----------------------------------------------------------

class StoryPlannerBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    persona_id: UUID | None = None
    status: str = Field(default="active", max_length=20)
    rules: list[dict] = []
    highlight_collections: list = []
    highlight_config: dict = {}
    anti_repetition_days: int = 3
    seed: int = 1

class StoryPlannerCreate(StoryPlannerBase):
    pass

class StoryPlannerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    persona_id: UUID | None = None
    status: str | None = Field(default=None, max_length=20)
    rules: list[dict] | None = None
    highlight_collections: list | None = None
    highlight_config: dict | None = None
    anti_repetition_days: int | None = None
    seed: int | None = None

class StoryPlannerOut(StoryPlannerBase):
    id: UUID
    cycle: int = 0
    depth_days: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class DepthEstimation(BaseModel):
    total_variants: int
    unique_medias: int
    variants_per_day: float
    depth_days: int
    by_type: dict = {}


# --- Story Type --------------------------------------------------------------

class StoryTypeBase(BaseModel):
    slug: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#4ade80", max_length=20)
    icon: str = Field(default="sparkle", max_length=50)
    personas: list | None = None
    position: int = 0

class StoryTypeCreate(StoryTypeBase):
    pass

class StoryTypeUpdate(BaseModel):
    slug: str | None = Field(default=None, max_length=50)
    label: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=20)
    icon: str | None = Field(default=None, max_length=50)
    personas: list | None = None
    position: int | None = None

class StoryTypeOut(StoryTypeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Story Collection ---------------------------------------------------------

class StoryCollectionBase(BaseModel):
    persona_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(max_length=10)  # story, hl
    story_type: str | None = Field(default=None, max_length=50)
    template_ids: list | None = None
    by_persona: dict | None = None
    highlight_name: str | None = Field(default=None, max_length=200)
    highlight_icon: str | None = Field(default=None, max_length=50)
    schedule: dict | None = None


class StoryCollectionCreate(StoryCollectionBase):
    pass


class StoryCollectionUpdate(BaseModel):
    persona_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = Field(default=None, max_length=10)
    story_type: str | None = Field(default=None, max_length=50)
    template_ids: list | None = None
    by_persona: dict | None = None
    highlight_name: str | None = Field(default=None, max_length=200)
    highlight_icon: str | None = Field(default=None, max_length=50)
    schedule: dict | None = None


class StoryCollectionOut(StoryCollectionBase):
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
    media_urls: list[str] | None = None
    post_type: str = Field(default="post", max_length=20)
    caption: str | None = None
    first_comment: str | None = None
    scheduled_at: datetime | None = None
    status: str = Field(default="planned", max_length=20)
    platform_post_id: str | None = Field(default=None, max_length=200)
    stickers: dict | None = None


class PublicationCreate(PublicationBase):
    pass


class PublicationUpdate(BaseModel):
    campagne_id: UUID | None = None
    media_id: UUID | None = None
    media_urls: list[str] | None = None
    post_type: str | None = Field(default=None, max_length=20)
    caption: str | None = None
    first_comment: str | None = None
    scheduled_at: datetime | None = None
    status: str | None = Field(default=None, max_length=20)
    platform_post_id: str | None = Field(default=None, max_length=200)
    stickers: dict | None = None


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
