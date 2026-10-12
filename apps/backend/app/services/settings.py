from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import WorkspaceSettings
from app.schemas.settings import IntegrationStatus, WorkspaceOut


def _tail(key: str | None) -> str | None:
    """Show only the last 4 chars of an API key."""
    if not key:
        return None
    return f"***{key[-4:]}"


def _to_out(s: WorkspaceSettings) -> WorkspaceOut:
    return WorkspaceOut(
        name=s.name,
        currency=s.currency,
        timezone=s.timezone,
        oc=IntegrationStatus(
            connected=s.oc_connected,
            last_sync=s.oc_last_sync,
            key_tail=_tail(s.oc_api_key),
        ),
        gms=IntegrationStatus(
            connected=s.gms_connected,
            last_sync=s.gms_last_sync,
            key_tail=_tail(s.gms_api_key),
        ),
        tg=IntegrationStatus(
            connected=s.tg_connected,
            key_tail=_tail(s.tg_bot_token),
        ),
        env_providers=s.env_providers,
        notifications=s.notifications,
        updated_at=s.updated_at,
    )


async def get_or_create(db: AsyncSession) -> WorkspaceSettings:
    """Return the single settings row, creating it if missing."""
    s = await db.get(WorkspaceSettings, 1)
    if not s:
        s = WorkspaceSettings(id=1)
        db.add(s)
        await db.commit()
        await db.refresh(s)
    return s


async def get_settings(db: AsyncSession) -> WorkspaceOut:
    s = await get_or_create(db)
    return _to_out(s)


async def update_workspace(db: AsyncSession, data: dict) -> WorkspaceOut:
    s = await get_or_create(db)
    for k, v in data.items():
        if v is not None:
            setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return _to_out(s)


async def update_integration(
    db: AsyncSession, provider: str, data: dict
) -> WorkspaceOut:
    s = await get_or_create(db)

    if provider == "oc":
        if "api_key" in data and data["api_key"] is not None:
            s.oc_api_key = data["api_key"]
            s.oc_connected = bool(data["api_key"])
    elif provider == "gms":
        if "api_key" in data and data["api_key"] is not None:
            s.gms_api_key = data["api_key"]
            s.gms_connected = bool(data["api_key"])
    elif provider == "tg":
        if "bot_token" in data and data["bot_token"] is not None:
            s.tg_bot_token = data["bot_token"]
        if "chat_id" in data and data["chat_id"] is not None:
            s.tg_chat_id = data["chat_id"]
        s.tg_connected = bool(s.tg_bot_token and s.tg_chat_id)

    await db.commit()
    await db.refresh(s)
    return _to_out(s)


async def update_notifications(db: AsyncSession, data: dict) -> WorkspaceOut:
    s = await get_or_create(db)
    current = s.notifications or {}
    current.update({k: v for k, v in data.items() if v is not None})
    s.notifications = current
    await db.commit()
    await db.refresh(s)
    return _to_out(s)
