from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.proxy import ProxyCreate, ProxyOut, ProxyUpdate
from app.services import proxies as service

router = APIRouter()


@router.get("/", response_model=list[ProxyOut])
async def list_proxies(
    pool: str | None = Query(None),
    status: str | None = Query(None),
    country: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_proxies(db, pool=pool, status=status, country=country)


@router.get("/{proxy_id}", response_model=ProxyOut)
async def get_proxy(proxy_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_proxy(db, proxy_id)
    if not p:
        raise HTTPException(404, "proxy not found")
    return p


@router.post("/", response_model=ProxyOut, status_code=201)
async def create_proxy(data: ProxyCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_proxy(db, data)


@router.patch("/{proxy_id}", response_model=ProxyOut)
async def update_proxy(
    proxy_id: UUID, data: ProxyUpdate, db: AsyncSession = Depends(get_db)
):
    p = await service.get_proxy(db, proxy_id)
    if not p:
        raise HTTPException(404, "proxy not found")
    return await service.update_proxy(db, p, data.model_dump(exclude_unset=True))


@router.delete("/{proxy_id}", status_code=204)
async def delete_proxy(proxy_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_proxy(db, proxy_id)
    if not p:
        raise HTTPException(404, "proxy not found")
    await service.delete_proxy(db, p)
