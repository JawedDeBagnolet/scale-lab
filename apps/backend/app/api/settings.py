from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.settings import (
    IntegrationUpdate,
    NotificationsUpdate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.services import settings as service

router = APIRouter()

PROVIDERS = ("oc", "gms", "tg")


@router.get("/", response_model=WorkspaceOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await service.get_settings(db)


@router.patch("/workspace", response_model=WorkspaceOut)
async def update_workspace(data: WorkspaceUpdate, db: AsyncSession = Depends(get_db)):
    return await service.update_workspace(db, data.model_dump(exclude_unset=True))


@router.patch("/integrations/{provider}", response_model=WorkspaceOut)
async def update_integration(
    provider: str,
    data: IntegrationUpdate,
    db: AsyncSession = Depends(get_db),
):
    if provider not in PROVIDERS:
        raise HTTPException(400, f"provider must be one of {PROVIDERS}")
    return await service.update_integration(
        db, provider, data.model_dump(exclude_unset=True)
    )


@router.patch("/notifications", response_model=WorkspaceOut)
async def update_notifications(
    data: NotificationsUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await service.update_notifications(db, data.model_dump(exclude_unset=True))
