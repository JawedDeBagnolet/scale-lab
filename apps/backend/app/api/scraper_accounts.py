"""API routes for scraper accounts — CRUD + session + proxy management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services import scraper_accounts as service

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────

class ScraperAccountCreate(BaseModel):
    platform: str  # ig, threads, x
    username: str
    password: str | None = None
    proxy_country: str = "FR"


class ScraperAccountUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    proxy_country: str | None = None
    status: str | None = None


class ScraperAccountOut(BaseModel):
    id: UUID
    platform: str
    username: str
    has_password: bool = False
    ds_user_id: str | None = None
    user_agent: str | None = None
    has_session: bool = False
    proxy_country: str
    status: str
    last_error: str | None = None
    bytes_used: int
    requests_count: int
    last_used_at: str | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, m):
        return cls(
            id=m.id,
            platform=m.platform,
            username=m.username,
            has_password=bool(m.password),
            ds_user_id=m.ds_user_id,
            user_agent=m.user_agent,
            has_session=bool(m.session_data),
            proxy_country=m.proxy_country,
            status=m.status,
            last_error=m.last_error,
            bytes_used=m.bytes_used,
            requests_count=m.requests_count,
            last_used_at=m.last_used_at.isoformat() if m.last_used_at else None,
            created_at=m.created_at.isoformat(),
            updated_at=m.updated_at.isoformat(),
        )


class SessionSaveRequest(BaseModel):
    session_data: dict
    user_agent: str | None = None
    ds_user_id: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ScraperAccountOut])
async def list_scraper_accounts(
    platform: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    accounts = await service.list_accounts(db, platform=platform, status=status)
    return [ScraperAccountOut.from_model(a) for a in accounts]


@router.get("/{account_id}", response_model=ScraperAccountOut)
async def get_scraper_account(account_id: UUID, db: AsyncSession = Depends(get_db)):
    a = await service.get_account(db, account_id)
    if not a:
        raise HTTPException(404, "scraper account not found")
    return ScraperAccountOut.from_model(a)


@router.post("/", response_model=ScraperAccountOut, status_code=201)
async def create_scraper_account(
    data: ScraperAccountCreate, db: AsyncSession = Depends(get_db)
):
    a = await service.create_account(db, data.model_dump())
    return ScraperAccountOut.from_model(a)


@router.patch("/{account_id}", response_model=ScraperAccountOut)
async def update_scraper_account(
    account_id: UUID,
    data: ScraperAccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    a = await service.get_account(db, account_id)
    if not a:
        raise HTTPException(404, "scraper account not found")
    a = await service.update_account(db, a, data.model_dump(exclude_unset=True))
    return ScraperAccountOut.from_model(a)


@router.delete("/{account_id}", status_code=204)
async def delete_scraper_account(account_id: UUID, db: AsyncSession = Depends(get_db)):
    a = await service.get_account(db, account_id)
    if not a:
        raise HTTPException(404, "scraper account not found")
    await service.delete_account(db, a)


# ── Session management ───────────────────────────────────────────────────

@router.post("/{account_id}/session", response_model=ScraperAccountOut)
async def save_session(
    account_id: UUID,
    data: SessionSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save extracted session data (from iPhone login) to a scraper account."""
    a = await service.save_session(
        db, account_id,
        session_data=data.session_data,
        user_agent=data.user_agent,
        ds_user_id=data.ds_user_id,
    )
    if not a:
        raise HTTPException(404, "scraper account not found")
    return ScraperAccountOut.from_model(a)


@router.post("/{account_id}/verify")
async def verify_session(account_id: UUID, db: AsyncSession = Depends(get_db)):
    """Verify the scraper account's session is still valid."""
    a = await service.get_account(db, account_id)
    if not a:
        raise HTTPException(404, "scraper account not found")
    if not a.session_data:
        raise HTTPException(400, "no session data")

    from app.services.ig_api_scraper import IGScraperClient
    client = IGScraperClient.from_scraper_account(a)
    if not client:
        raise HTTPException(400, "cannot build client from session")

    try:
        result = await client.verify()
        if result.get("ok"):
            await service.update_account(db, a, {"status": "active", "last_error": None})
            return {"ok": True, "user": result.get("user")}
        else:
            error = result.get("error", "session invalid")
            await service.mark_error(db, account_id, error)
            return {"ok": False, "error": error}
    except Exception as e:
        await service.mark_error(db, account_id, str(e)[:200])
        return {"ok": False, "error": str(e)[:200]}


# ── Scrapigo ─────────────────────────────────────────────────────────────

@router.get("/scrapigo/balance")
async def scrapigo_balance():
    """Check Scrapigo account balance."""
    from app.services.scrapigo import get_scrapigo_client
    client = await get_scrapigo_client()
    if not client:
        raise HTTPException(400, "Scrapigo non configuré (clé API manquante)")
    balance = await client.get_balance()
    if not balance:
        raise HTTPException(502, "Erreur Scrapigo API")
    return balance


@router.get("/scrapigo/usage")
async def scrapigo_usage():
    """Get Scrapigo usage stats."""
    from app.services.scrapigo import get_scrapigo_client
    client = await get_scrapigo_client()
    if not client:
        raise HTTPException(400, "Scrapigo non configuré")
    return await client.get_usage_summary() or {}
