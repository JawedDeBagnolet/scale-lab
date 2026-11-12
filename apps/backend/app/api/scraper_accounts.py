"""API routes for scraper accounts — queries Comptes with is_scraper=True.

Scraper accounts are regular Comptes that go through the standard iPhone
login pipeline. The only difference is they're flagged is_scraper=True and
used exclusively for IG/Threads/X private API scraping (veille, search, stats).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.compte import Compte

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────

class ScraperCompteOut(BaseModel):
    id: UUID
    handle: str
    plateforme: str
    workflow: str
    status: str
    has_session: bool
    proxy_country: str
    bytes_used: int
    requests_count: int
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, c: Compte):
        env = c.env or {}
        return cls(
            id=c.id,
            handle=c.handle,
            plateforme=c.plateforme,
            workflow=c.workflow,
            status=c.status,
            has_session=bool(c.session_data),
            proxy_country=env.get("proxy_country", "FR"),
            bytes_used=c.scraper_bytes_used,
            requests_count=c.scraper_requests_count,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )


# ── Routes ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ScraperCompteOut])
async def list_scraper_accounts(
    platform: str | None = Query(None, alias="plateforme"),
    db: AsyncSession = Depends(get_db),
):
    """List all comptes flagged as scraper."""
    stmt = (
        select(Compte)
        .where(Compte.is_scraper.is_(True))
        .order_by(Compte.created_at.desc())
    )
    if platform:
        stmt = stmt.where(Compte.plateforme == platform)
    result = await db.execute(stmt)
    return [ScraperCompteOut.from_model(c) for c in result.scalars().all()]


@router.delete("/{compte_id}", status_code=204)
async def delete_scraper_account(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    """Remove scraper flag from a compte (doesn't delete the compte itself)."""
    c = await db.get(Compte, compte_id)
    if not c or not c.is_scraper:
        raise HTTPException(404, "scraper account not found")
    c.is_scraper = False
    c.session_data = None
    c.scraper_bytes_used = 0
    c.scraper_requests_count = 0
    await db.commit()


@router.post("/{compte_id}/verify")
async def verify_session(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    """Verify a scraper compte's session is still valid via IG private API."""
    c = await db.get(Compte, compte_id)
    if not c or not c.is_scraper:
        raise HTTPException(404, "scraper account not found")
    if not c.session_data:
        raise HTTPException(400, "no session data — login via iPhone first")

    from app.services.ig_api_scraper import IGScraperClient
    client = IGScraperClient.from_compte(c)
    if not client:
        raise HTTPException(400, "cannot build client from session")

    try:
        result = await client.verify()
        if result.get("ok"):
            c.status = "ok"
            await db.commit()
            return {"ok": True, "user": result.get("user")}
        else:
            error = result.get("error", "session invalid")
            c.status = "session"
            await db.commit()
            return {"ok": False, "error": error}
    except Exception as e:
        c.status = "error"
        await db.commit()
        return {"ok": False, "error": str(e)[:200]}


# ── Scrapigo ─────────────────────────────────────────────────────────────

@router.get("/scrapigo/balance")
async def scrapigo_balance():
    """Check Scrapigo account balance."""
    from app.services.scrapigo import get_scrapigo_client
    client = await get_scrapigo_client()
    if not client:
        raise HTTPException(400, "Scrapigo non configuré (clé API manquante)")
    raw = await client.get_balance()
    if not raw:
        raise HTTPException(502, "Erreur Scrapigo API")
    # Normalize: Scrapigo returns creditUsd, frontend expects balance
    credit = float(raw.get("creditUsd", 0))
    rate_per_gb = 0.99  # residential rate
    return {
        "balance": credit,
        "creditUsd": raw.get("creditUsd"),
        "data_remaining_gb": round(credit / rate_per_gb, 1) if rate_per_gb else None,
        "dailySpendCapUsd": raw.get("key", {}).get("dailySpendCapUsd"),
        "keyName": raw.get("key", {}).get("name"),
        "callerIp": raw.get("callerIp"),
    }


@router.get("/scrapigo/usage")
async def scrapigo_usage():
    """Get Scrapigo usage stats."""
    from app.services.scrapigo import get_scrapigo_client
    client = await get_scrapigo_client()
    if not client:
        raise HTTPException(400, "Scrapigo non configuré")
    return await client.get_usage_summary() or {}
