from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.lien import (
    ClickEventCreate,
    ClickEventOut,
    DomainCreate,
    DomainOut,
    DomainUpdate,
    LinkStats,
    TrackedLinkCreate,
    TrackedLinkOut,
    TrackedLinkUpdate,
)
from app.services import liens as service

router = APIRouter()


# --- Links (collection) ------------------------------------------------------


@router.get("/", response_model=list[TrackedLinkOut])
async def list_links(
    domain_id: UUID | None = Query(None),
    plateforme: str | None = Query(None),
    active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_links(
        db, domain_id=domain_id, plateforme=plateforme, active=active
    )


@router.post("/", response_model=TrackedLinkOut, status_code=201)
async def create_link(data: TrackedLinkCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_link(db, data)


# --- Domains ------------------------------------------------------------------
# IMPORTANT : ces routes DOIVENT être définies AVANT /{link_id}
# sinon FastAPI tente de parser "domains" comme un UUID → 422


@router.get("/domains", response_model=list[DomainOut])
async def list_domains(db: AsyncSession = Depends(get_db)):
    return await service.list_domains(db)


@router.post("/domains", response_model=DomainOut, status_code=201)
async def create_domain(data: DomainCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_domain(db, data)


@router.patch("/domains/{domain_id}", response_model=DomainOut)
async def update_domain(
    domain_id: UUID, data: DomainUpdate, db: AsyncSession = Depends(get_db)
):
    domain = await service.get_domain(db, domain_id)
    if not domain:
        raise HTTPException(404, "domain not found")
    return await service.update_domain(db, domain, data.model_dump(exclude_unset=True))


@router.delete("/domains/{domain_id}", status_code=204)
async def delete_domain(domain_id: UUID, db: AsyncSession = Depends(get_db)):
    domain = await service.get_domain(db, domain_id)
    if not domain:
        raise HTTPException(404, "domain not found")
    await service.delete_domain(db, domain)


# --- Links (par ID) -----------------------------------------------------------
# APRÈS les routes /domains/* pour éviter que FastAPI
# ne parse "domains" comme un UUID


@router.get("/{link_id}", response_model=TrackedLinkOut)
async def get_link(link_id: UUID, db: AsyncSession = Depends(get_db)):
    link = await service.get_link(db, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    return link


@router.get("/{link_id}/stats", response_model=LinkStats)
async def get_link_stats(link_id: UUID, db: AsyncSession = Depends(get_db)):
    link = await service.get_link(db, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    return await service.get_link_stats(db, link_id)


@router.patch("/{link_id}", response_model=TrackedLinkOut)
async def update_link(
    link_id: UUID, data: TrackedLinkUpdate, db: AsyncSession = Depends(get_db)
):
    link = await service.get_link(db, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    return await service.update_link(db, link, data.model_dump(exclude_unset=True))


@router.delete("/{link_id}", status_code=204)
async def delete_link(link_id: UUID, db: AsyncSession = Depends(get_db)):
    link = await service.get_link(db, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    await service.delete_link(db, link)


# --- Clicks -------------------------------------------------------------------


@router.get("/{link_id}/clicks", response_model=list[ClickEventOut])
async def list_clicks(
    link_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    link = await service.get_link(db, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    return await service.list_clicks(db, link_id, limit)


@router.post("/{link_id}/click", response_model=ClickEventOut, status_code=201)
async def record_click(
    link_id: UUID, data: ClickEventCreate, db: AsyncSession = Depends(get_db)
):
    link = await service.get_link(db, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    return await service.record_click(db, link_id, data)
