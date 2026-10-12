from datetime import datetime

from pydantic import BaseModel


class IntegrationStatus(BaseModel):
    connected: bool
    last_sync: datetime | None = None
    key_tail: str | None = None  # 4 derniers chars de la cle


class WorkspaceOut(BaseModel):
    name: str
    currency: str
    timezone: str
    oc: IntegrationStatus
    gms: IntegrationStatus
    tg: IntegrationStatus
    env_providers: dict | None = None
    notifications: dict | None = None
    updated_at: datetime


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None
    timezone: str | None = None


class IntegrationUpdate(BaseModel):
    """Update one integration's key(s). `test` triggers a live check."""

    api_key: str | None = None
    bot_token: str | None = None
    chat_id: str | None = None
    test: bool = False


class NotificationsUpdate(BaseModel):
    domain_full: bool | None = None
    oc_balance_low: bool | None = None
    link_unavailable: bool | None = None
