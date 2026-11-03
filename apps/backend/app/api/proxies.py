from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.proxy import ProxyCreate, ProxyOut, ProxyUpdate
from app.services import proxies as service
from app.services.proxy_tester import test_proxy

router = APIRouter()


class ProxyTestOut(BaseModel):
    success: bool
    exit_ip: str | None = None
    exit_country: str | None = None
    exit_org: str | None = None
    latency_ms: int | None = None
    blacklists: list[str] | None = None
    is_datacenter: bool = False
    error: str | None = None


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


@router.post("/{proxy_id}/test", response_model=ProxyTestOut)
async def test_proxy_endpoint(proxy_id: UUID, db: AsyncSession = Depends(get_db)):
    """Test a proxy: connect through it, measure latency, get exit IP, check blacklists."""
    p = await service.get_proxy(db, proxy_id)
    if not p:
        raise HTTPException(404, "proxy not found")

    result = await test_proxy(ip=p.ip, proxy_type="socks5" if "5" in p.type else "http")

    # Update proxy in DB with real test results
    update_data = {"updated_at": datetime.now(UTC)}
    if result.success:
        update_data["latency_ms"] = result.latency_ms
        update_data["status"] = "online"
        update_data["blacklists"] = result.blacklists or []
    else:
        update_data["status"] = "error"

    await service.update_proxy(db, p, update_data)

    return ProxyTestOut(
        success=result.success,
        exit_ip=result.exit_ip,
        exit_country=result.exit_country,
        exit_org=result.exit_org,
        latency_ms=result.latency_ms,
        blacklists=result.blacklists,
        is_datacenter=result.is_datacenter,
        error=result.error,
    )


@router.post("/test-all")
async def test_all_proxies(db: AsyncSession = Depends(get_db)):
    """Test all online proxies."""
    proxies = await service.list_proxies(db)
    results = []
    for p in proxies:
        result = await test_proxy(ip=p.ip, proxy_type="socks5" if "5" in p.type else "http")
        update_data = {"updated_at": datetime.now(UTC)}
        if result.success:
            update_data["latency_ms"] = result.latency_ms
            update_data["status"] = "online"
            update_data["blacklists"] = result.blacklists or []
        else:
            update_data["status"] = "error"
        await service.update_proxy(db, p, update_data)
        results.append({"id": str(p.id), "ip": p.ip, "success": result.success, "error": result.error})
    return {"tested": len(results), "results": results}
