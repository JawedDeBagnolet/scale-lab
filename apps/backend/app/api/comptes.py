import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.compte import Compte
from app.schemas.compte import CompteCreate, CompteOut, CompteUpdate
from app.services import comptes as service

logger = logging.getLogger("api.comptes")

router = APIRouter()


# ── Batch request models ────────────────────────────────────────────────────

class BatchLoginRequest(BaseModel):
    compte_ids: list[UUID]


class BatchLoginAllRequest(BaseModel):
    plateforme: str | None = None  # "ig", "th", or None for all


@router.get("", response_model=list[CompteOut])
async def list_comptes(
    persona_id: UUID | None = Query(None),
    plateforme: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_comptes(db, persona_id=persona_id, plateforme=plateforme)


@router.get("/{compte_id}", response_model=CompteOut)
async def get_compte(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    return c


@router.post("", response_model=CompteOut, status_code=201)
async def create_compte(data: CompteCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await service.create_compte(db, data)
    except service.PersonaNotFound:
        raise HTTPException(400, "persona not found")


@router.patch("/{compte_id}", response_model=CompteOut)
async def update_compte(compte_id: UUID, data: CompteUpdate, db: AsyncSession = Depends(get_db)):
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    try:
        return await service.update_compte(db, c, data)
    except service.PersonaNotFound:
        raise HTTPException(400, "persona not found")


@router.delete("/{compte_id}", status_code=204)
async def delete_compte(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    await service.delete_compte(db, c)


# ── Batch login endpoints ───────────────────────────────────────────────────

@router.post("/batch-login")
async def batch_login(body: BatchLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login a list of accounts by ID. Each login is dispatched as a background
    task and queued via the per-device FIFO lock. Returns immediately."""
    queued = []
    skipped = []
    for cid in body.compte_ids:
        c = await service.get_compte(db, cid)
        if not c or not c.device_id or not (c.env or {}).get("container_uuid"):
            skipped.append(str(cid))
            continue
        asyncio.create_task(
            service._dispatch_auto_login(c.id, c.plateforme),
            name=f"batch_login_{c.handle}",
        )
        queued.append(str(cid))

    logger.info("batch-login: queued %d, skipped %d", len(queued), len(skipped))
    return {"queued": len(queued), "skipped": len(skipped), "compte_ids": queued, "skipped_ids": skipped}


@router.post("/batch-login-all")
async def batch_login_all(body: BatchLoginAllRequest, db: AsyncSession = Depends(get_db)):
    """Login all eligible accounts (status=ok, device assigned, container ready).
    Optionally filter by plateforme (ig, th)."""
    stmt = select(Compte).where(
        Compte.status == "ok",
        Compte.device_id.isnot(None),
    )
    if body.plateforme:
        stmt = stmt.where(Compte.plateforme == body.plateforme)

    result = await db.execute(stmt)
    comptes = result.scalars().all()

    queued = []
    skipped = []
    for c in comptes:
        if not (c.env or {}).get("container_uuid"):
            skipped.append(str(c.id))
            continue
        asyncio.create_task(
            service._dispatch_auto_login(c.id, c.plateforme),
            name=f"batch_login_{c.handle}",
        )
        queued.append(str(c.id))

    logger.info("batch-login-all: plateforme=%s queued=%d skipped=%d", body.plateforme or "all", len(queued), len(skipped))
    return {"queued": len(queued), "skipped": len(skipped), "plateforme": body.plateforme or "all"}


# ── Profile update (dispatch to iPhone) ───────────────────────────────────

class ProfileUpdateRequest(BaseModel):
    fields: dict  # e.g. {"full_name": "New Name", "biography": "New bio"}


@router.post("/{compte_id}/profile-update")
async def profile_update(compte_id: UUID, body: ProfileUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Dispatch profile edits to the iPhone automation.

    Compares requested fields with current profile_data, then dispatches
    changed fields as an ig_config task. Returns immediately — the actual
    edit runs as a background asyncio task.
    """
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")

    if not c.device_id:
        raise HTTPException(400, "Aucun iPhone associé — impossible de modifier le profil")

    if not (c.env or {}).get("container_uuid"):
        raise HTTPException(400,
            f"iPhone indisponible : Compte {c.handle} sans container UUID "
            f"— associe un container via POST /comptes/{{id}} avec env.container_uuid")

    # Compute diff against current profile_data
    current = c.profile_data or {}
    changed = {}
    for key, new_val in body.fields.items():
        old_val = current.get(key)
        if old_val != new_val:
            changed[key] = new_val

    if not changed:
        return {"status": "noop", "message": "Aucun changement détecté"}

    # Dispatch the edit as a background task
    asyncio.create_task(
        service._dispatch_profile_edit(c.id, c.plateforme, changed, handle=c.handle),
        name=f"profile_edit_{c.handle}",
    )

    logger.info("profile-update: dispatched %s fields for %s", list(changed.keys()), c.handle)
    return {"status": "dispatched", "fields": list(changed.keys())}


# ── Profile live (read from IG API) ──────────────────────────────────────

@router.get("/{compte_id}/profile-live")
async def profile_live(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fetch real-time profile data via IG scraper API and persist it."""
    c = await service.get_compte(db, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")

    try:
        from app.services.ig_api_scraper import IGScraperClient
        client = await IGScraperClient.from_db(db)
        if not client:
            raise HTTPException(503, "Aucun scraper disponible")

        profile = await client.get_user_profile_full(c.handle)
        if not profile:
            raise HTTPException(502, "Profil introuvable via l'API")

        # Persist to profile_data
        c.profile_data = profile
        await db.commit()

        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("profile-live: error for %s", c.handle)
        raise HTTPException(502, f"Erreur lecture profil: {e}")


# ── Scraper bulk create ────────────────────────────────────────────────────

class ScraperBulkItem(BaseModel):
    username: str
    password: str
    totp: str | None = None

class ScraperBulkRequest(BaseModel):
    accounts: list[ScraperBulkItem]
    plateforme: str = "ig"
    proxy_country: str = "FR"
    device_id: str | None = None  # "auto" or specific iPhone id

@router.post("/bulk-scraper", status_code=201)
async def bulk_create_scrapers(body: ScraperBulkRequest, db: AsyncSession = Depends(get_db)):
    """Create multiple scraper accounts and queue their logins on iPhones.

    Each account is created as a Compte with is_scraper=True, then dispatched
    for login on the selected iPhone (or auto-assigned to the first free one).
    """
    from app.schemas.compte import CompteCreate

    created = []
    for item in body.accounts:
        data = CompteCreate(
            handle=item.username.lstrip("@"),
            plateforme=body.plateforme,
            is_scraper=True,
            device_id=body.device_id if body.device_id and body.device_id != "auto" else None,
            env={"proxy_country": body.proxy_country},
            creds_encrypted={"username": item.username.lstrip("@"), "password": item.password, "two_fa": item.totp},
        )
        c = await service.create_compte(db, data)
        created.append(str(c.id))

    logger.info("bulk-scraper: created %d scraper accounts (%s)", len(created), body.plateforme)
    return {"created": len(created), "compte_ids": created}
