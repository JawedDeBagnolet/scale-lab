from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PersonaBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    market: str | None = Field(default=None, max_length=10)
    city: str | None = Field(default=None, max_length=100)
    age: int | None = Field(default=None, ge=18, le=99)
    platforms: list[str] | None = None
    niches: list[str] | None = None
    bios: list[dict] | None = None
    prompt: str | None = None
    funnel: str | None = None
    telegram: dict | None = None
    photo_url: str | None = None
    prs_id: str | None = Field(default=None, max_length=100)


class PersonaCreate(PersonaBase):
    pass


class PersonaUpdate(PersonaBase):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)


class CompteOut(BaseModel):
    id: UUID
    handle: str
    plateforme: str
    workflow: str
    status: str
    model_config = {"from_attributes": True}


class PersonaOut(PersonaBase):
    id: UUID
    # Pas de contrainte en sortie : on ne rejette pas une ligne deja en base
    first_name: str
    color: str | None = None
    age: int | None = None
    created_at: datetime
    updated_at: datetime
    comptes: list[CompteOut] = []
    model_config = {"from_attributes": True}
