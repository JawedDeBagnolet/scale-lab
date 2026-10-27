from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Plateforme = Literal["ig", "th", "x"]
Workflow = Literal["Onboarding", "Warmup", "Actif"]
Status = Literal["ok", "session", "error", "suspendu"]


class CompteBase(BaseModel):
    handle: str = Field(min_length=1, max_length=100)
    persona_id: UUID | None = None
    plateforme: Plateforme
    workflow: Workflow = "Onboarding"
    status: Status = "ok"
    device_id: str | None = Field(default=None, max_length=100)
    proxy_id: UUID | None = None
    env: dict | None = None
    sessions: int = Field(default=0, ge=0)
    follows: int = Field(default=0, ge=0)


class CompteCreate(CompteBase):
    creds_encrypted: dict | None = None  # {password, two_fa, token}


class CompteUpdate(BaseModel):
    handle: str | None = Field(default=None, min_length=1, max_length=100)
    persona_id: UUID | None = None
    plateforme: Plateforme | None = None
    workflow: Workflow | None = None
    status: Status | None = None
    device_id: str | None = Field(default=None, max_length=100)
    proxy_id: UUID | None = None
    env: dict | None = None
    sessions: int | None = Field(default=None, ge=0)
    follows: int | None = Field(default=None, ge=0)
    creds_encrypted: dict | None = None  # {password, two_fa, token}


class CompteOut(BaseModel):
    id: UUID
    handle: str
    persona_id: UUID | None
    plateforme: str
    workflow: str
    status: str
    device_id: str | None
    proxy_id: UUID | None
    env: dict | None
    sessions: int
    follows: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
