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



# ── Profile live (via scraper API) ─────────────────────────────────────

@router.get("/{compte_id}/profile-live")
async def get_profile_live(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fetch real-time profile data for a compte via the IG private API.

    Uses a scraper account's session + Scrapigo proxy to fetch profile
    info, stats, bio, highlights etc. for the given account's handle.
    """
    compte = await service.get_compte(db, compte_id)
    if not compte:
        raise HTTPException(404, "compte not found")

    if compte.plateforme != "ig":
        raise HTTPException(400, "profile-live only supports Instagram for now")

    from app.services.comptes import _log as emit_log
    await emit_log("comptes", "scrape", "info", compte.handle, f"Lecture profil live @{compte.handle} via API privée")

    try:
        from app.services.ig_api_scraper import IGScraperClient
        client = await IGScraperClient.from_db(db)
        if not client:
            await emit_log("comptes", "scrape", "error", compte.handle, "Aucun compte scraper avec session valide", code="NO_SCRAPER")
            raise HTTPException(503, "Aucun compte scraper avec session valide")

        profile = await client.get_user_profile_full(compte.handle)
        if not profile:
            await emit_log("comptes", "scrape", "warning", compte.handle, f"Profil @{compte.handle} introuvable via l'API privée")
            raise HTTPException(404, f"Profil @{compte.handle} introuvable via l'API privée")

        hl_count = len(profile.get("highlights", []))
        await emit_log("comptes", "scrape", "success", compte.handle,
            f"Profil @{compte.handle} récupéré — {profile.get('follower_count', 0)} followers, {profile.get('media_count', 0)} posts, {hl_count} highlights")

        # Persist live profile data in DB
        compte.profile_data = profile
        await db.commit()

        # Merge with internal config (age_limit, pro_type, etc. — not from API)
        config = compte.profile_config or {}
        result = {**profile}
        result["_config"] = config  # internal fields the frontend should preserve

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("profile-live error for %s", compte.handle)
        await emit_log("comptes", "scrape", "error", compte.handle, f"Erreur API privée: {str(e)[:150]}", code="SCRAPE_ERROR")
        raise HTTPException(502, f"Erreur API privée: {str(e)[:150]}")



# ── Profile update (diff-based, dispatches to iPhone) ──────────────────

class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    biography: str | None = None
    external_url: str | None = None
    is_private: bool | None = None
    is_business: bool | None = None
    # Internal-only config (not pushed to IG, stored locally)
    age_limit: str | None = None      # "18+", "21+", or null
    pro_type: str | None = None        # "creator", "business"
    pro_category: str | None = None

@router.post("/{compte_id}/profile-update")
async def update_profile(compte_id: UUID, body: ProfileUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Update profile config. Only changed fields (vs profile_data) are dispatched to iPhone.

    Internal fields (age_limit, pro_type) are stored in profile_config only.
    IG fields (bio, name, link, privacy) are diffed against last known profile_data
    and dispatched as an automation task on the assigned iPhone.
    """
    from app.services.comptes import _log as emit_log

    compte = await service.get_compte(db, compte_id)
    if not compte:
        raise HTTPException(404, "compte not found")

    changes = body.model_dump(exclude_unset=True)
    live = compte.profile_data or {}
    config = compte.profile_config or {}

    # Separate internal config vs IG-pushable fields
    INTERNAL_KEYS = {"age_limit", "pro_type", "pro_category"}
    IG_KEYS = {"full_name", "biography", "external_url", "is_private", "is_business"}

    # Update internal config
    config_changed = False
    for k in INTERNAL_KEYS:
        if k in changes:
            config[k] = changes[k]
            config_changed = True

    if config_changed:
        compte.profile_config = config

    # Diff IG fields against live data
    ig_diff = {}
    for k in IG_KEYS:
        if k in changes and changes[k] != live.get(k):
            ig_diff[k] = changes[k]

    if ig_diff:
        await emit_log("comptes", "profile", "info", compte.handle,
            f"Modification profil demandée : {', '.join(ig_diff.keys())}")

        # Dispatch to iPhone automation
        if compte.device_id:
            import asyncio
            asyncio.create_task(
                _dispatch_profile_edit(compte.id, compte.plateforme, ig_diff),
                name=f"profile_edit_{compte.handle}",
            )
            logger.info("profile-update: dispatched %s changes for @%s", list(ig_diff.keys()), compte.handle)
            await emit_log("comptes", "profile", "info", compte.handle,
                f"Ordre de configuration envoyé à l'iPhone — {', '.join(ig_diff.keys())}")
        else:
            await emit_log("comptes", "profile", "warning", compte.handle,
                "Pas d'iPhone assigné — modifications enregistrées mais non appliquées sur IG")

    await db.commit()
    return {"ok": True, "ig_changes": ig_diff, "config_changes": {k: config[k] for k in INTERNAL_KEYS if k in changes}}


async def _dispatch_profile_edit(compte_id: UUID, plateforme: str, changes: dict):
    """Background task: edit profile on iPhone via automation script."""
    try:
        if plateforme == "ig":
            from app.services.automation.ig_runner import run_ig_task
            ok, msg = await run_ig_task(compte_id, "ig_edit_profile", values=changes)
        else:
            logger.info("profile_edit: plateforme %s not yet supported", plateforme)
            return

        from app.services.comptes import _log as emit_log
        if ok:
            await emit_log("comptes", "profile", "success", str(compte_id), f"Profil modifié — {msg}")
        else:
            await emit_log("comptes", "profile", "error", str(compte_id), f"Échec modification profil — {msg}")
    except Exception:
        logger.exception("profile_edit error for %s", compte_id)
