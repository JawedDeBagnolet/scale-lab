"""Integration endpoints — test/status/sync for OC and GMS APIs."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services import settings as settings_svc
from app.services import gms_client, oc_client

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────

class TestKeyRequest(BaseModel):
    api_key: str | None = None  # If None, uses the stored key


class TestResult(BaseModel):
    ok: bool
    error: str | None = None
    details: dict | None = None


class StatusResult(BaseModel):
    ok: bool
    error: str | None = None
    data: dict | None = None


# ── Test Connection ─────────────────────────────────────

@router.post("/oc/test", response_model=TestResult)
async def test_oc(body: TestKeyRequest, db: AsyncSession = Depends(get_db)):
    """Test OnlyChat API key validity."""
    key = body.api_key
    if not key:
        s = await settings_svc.get_or_create(db)
        key = s.oc_api_key
    if not key:
        raise HTTPException(400, "Aucune cle API OnlyChat fournie")

    result = await oc_client.test_connection(key)

    # If testing the stored key and it's valid, update connected status
    if result["ok"] and not body.api_key:
        s = await settings_svc.get_or_create(db)
        s.oc_connected = True
        await db.commit()

    return TestResult(
        ok=result["ok"],
        error=result.get("error"),
        details={k: v for k, v in result.items() if k not in ("ok", "error")},
    )


@router.post("/gms/test", response_model=TestResult)
async def test_gms(body: TestKeyRequest, db: AsyncSession = Depends(get_db)):
    """Test GetMySocial API key validity."""
    key = body.api_key
    if not key:
        s = await settings_svc.get_or_create(db)
        key = s.gms_api_key
    if not key:
        raise HTTPException(400, "Aucune cle API GetMySocial fournie")

    result = await gms_client.test_connection(key)

    if result["ok"] and not body.api_key:
        s = await settings_svc.get_or_create(db)
        s.gms_connected = True
        await db.commit()

    return TestResult(
        ok=result["ok"],
        error=result.get("error"),
        details={k: v for k, v in result.items() if k not in ("ok", "error")},
    )


# ── Save Key + Test ─────────────────────────────────────

@router.put("/oc/key")
async def save_oc_key(body: TestKeyRequest, db: AsyncSession = Depends(get_db)):
    """Save OC API key and test it."""
    if not body.api_key:
        raise HTTPException(400, "api_key requis")

    # Test first
    result = await oc_client.test_connection(body.api_key)

    # Save the key regardless (user typed it, we store it)
    s = await settings_svc.get_or_create(db)
    s.oc_api_key = body.api_key
    s.oc_connected = result["ok"]
    if result["ok"]:
        s.oc_last_sync = datetime.now(UTC)
    await db.commit()
    await db.refresh(s)

    return {
        "ok": result["ok"],
        "error": result.get("error"),
        "key_tail": f"***{body.api_key[-4:]}",
        "connected": result["ok"],
    }


@router.put("/gms/key")
async def save_gms_key(body: TestKeyRequest, db: AsyncSession = Depends(get_db)):
    """Save GMS API key and test it."""
    if not body.api_key:
        raise HTTPException(400, "api_key requis")

    result = await gms_client.test_connection(body.api_key)

    s = await settings_svc.get_or_create(db)
    s.gms_api_key = body.api_key
    s.gms_connected = result["ok"]
    if result["ok"]:
        s.gms_last_sync = datetime.now(UTC)
    await db.commit()
    await db.refresh(s)

    return {
        "ok": result["ok"],
        "error": result.get("error"),
        "key_tail": f"***{body.api_key[-4:]}",
        "connected": result["ok"],
    }


# ── Remove Key ──────────────────────────────────────────

@router.delete("/oc/key")
async def remove_oc_key(db: AsyncSession = Depends(get_db)):
    """Remove OC API key and disconnect."""
    s = await settings_svc.get_or_create(db)
    s.oc_api_key = None
    s.oc_connected = False
    s.oc_last_sync = None
    await db.commit()
    return {"ok": True}


@router.delete("/gms/key")
async def remove_gms_key(db: AsyncSession = Depends(get_db)):
    """Remove GMS API key and disconnect."""
    s = await settings_svc.get_or_create(db)
    s.gms_api_key = None
    s.gms_connected = False
    s.gms_last_sync = None
    await db.commit()
    return {"ok": True}


# ── Status ──────────────────────────────────────────────

@router.get("/oc/status", response_model=StatusResult)
async def oc_status(db: AsyncSession = Depends(get_db)):
    """Get live OC account status (creators, balance, etc.)."""
    s = await settings_svc.get_or_create(db)
    if not s.oc_api_key:
        return StatusResult(ok=False, error="Pas de cle API configuree")

    result = await oc_client.get_status(s.oc_api_key)
    return StatusResult(
        ok=result.get("ok", False),
        error=result.get("error"),
        data={k: v for k, v in result.items() if k not in ("ok", "error")},
    )


@router.get("/gms/status", response_model=StatusResult)
async def gms_status(db: AsyncSession = Depends(get_db)):
    """Get live GMS account status (links, plan, etc.)."""
    s = await settings_svc.get_or_create(db)
    if not s.gms_api_key:
        return StatusResult(ok=False, error="Pas de cle API configuree")

    result = await gms_client.get_status(s.gms_api_key)
    return StatusResult(
        ok=result.get("ok", False),
        error=result.get("error"),
        data={k: v for k, v in result.items() if k not in ("ok", "error")},
    )


# ── GMS Data Proxies (for frontend modules) ────────────

@router.get("/gms/links")
async def gms_links(
    limit: int = 25,
    cursor: str | None = None,
    sort: str = "-created",
    group_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Proxy GMS links list."""
    s = await settings_svc.get_or_create(db)
    if not s.gms_api_key:
        raise HTTPException(400, "Pas de cle API GMS configuree")
    return await gms_client.list_links(
        s.gms_api_key, limit=limit, cursor=cursor, sort=sort, group_id=group_id
    )


@router.get("/gms/links/{link_id}")
async def gms_link_detail(link_id: str, db: AsyncSession = Depends(get_db)):
    """Proxy single GMS link."""
    s = await settings_svc.get_or_create(db)
    if not s.gms_api_key:
        raise HTTPException(400, "Pas de cle API GMS configuree")
    return await gms_client.get_link(s.gms_api_key, link_id)


@router.get("/gms/analytics/overview")
async def gms_analytics_overview(
    timeframe: str = "today",
    link_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Proxy GMS analytics overview."""
    s = await settings_svc.get_or_create(db)
    if not s.gms_api_key:
        raise HTTPException(400, "Pas de cle API GMS configuree")
    return await gms_client.get_analytics_overview(
        s.gms_api_key, timeframe=timeframe, link_id=link_id
    )


@router.get("/gms/analytics/time-series")
async def gms_analytics_time_series(
    timeframe: str = "7",
    interval: str = "day",
    metric: str = "pageviews",
    link_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Proxy GMS analytics time series."""
    s = await settings_svc.get_or_create(db)
    if not s.gms_api_key:
        raise HTTPException(400, "Pas de cle API GMS configuree")
    return await gms_client.get_analytics_time_series(
        s.gms_api_key, timeframe=timeframe, interval=interval,
        metric=metric, link_id=link_id,
    )


@router.get("/gms/groups")
async def gms_groups_list(db: AsyncSession = Depends(get_db)):
    """Proxy GMS groups list."""
    s = await settings_svc.get_or_create(db)
    if not s.gms_api_key:
        raise HTTPException(400, "Pas de cle API GMS configuree")
    return await gms_client.list_groups(s.gms_api_key)


# ── OC Data Proxies ────────────────────────────────────

@router.get("/oc/creators")
async def oc_creators(db: AsyncSession = Depends(get_db)):
    """Proxy OC creators list."""
    s = await settings_svc.get_or_create(db)
    if not s.oc_api_key:
        raise HTTPException(400, "Pas de cle API OC configuree")
    creators = await oc_client.list_creators(s.oc_api_key)
    return {"data": creators, "count": len(creators)}


@router.get("/oc/creators/{creator_id}/stats")
async def oc_creator_stats(creator_id: str, db: AsyncSession = Depends(get_db)):
    """Proxy OC creator stats."""
    s = await settings_svc.get_or_create(db)
    if not s.oc_api_key:
        raise HTTPException(400, "Pas de cle API OC configuree")
    return await oc_client.get_creator_stats(s.oc_api_key, creator_id)


@router.get("/oc/creators/{creator_id}/scripts")
async def oc_creator_scripts(creator_id: str, db: AsyncSession = Depends(get_db)):
    """Proxy OC scripts for a creator."""
    s = await settings_svc.get_or_create(db)
    if not s.oc_api_key:
        raise HTTPException(400, "Pas de cle API OC configuree")
    scripts = await oc_client.list_scripts(s.oc_api_key, creator_id)
    return {"data": scripts, "count": len(scripts)}


@router.get("/oc/creators/{creator_id}/fans")
async def oc_creator_fans(
    creator_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    """Proxy OC fans for a creator."""
    s = await settings_svc.get_or_create(db)
    if not s.oc_api_key:
        raise HTTPException(400, "Pas de cle API OC configuree")
    fans = await oc_client.list_fans(s.oc_api_key, creator_id, limit=limit)
    return {"data": fans, "count": len(fans)}
