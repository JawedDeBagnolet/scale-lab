import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

logger = logging.getLogger("api.posting")
from app.schemas.posting import (
    CampagneCreate,
    CampagneOut,
    CampagneUpdate,
    CollectionCreate,
    CollectionOut,
    CollectionUpdate,
    MediaCreate,
    MediaOut,
    MediaUpdate,
    PostingOverview,
    PublicationCreate,
    PublicationOut,
    PublicationUpdate,
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
)
from app.services import posting as service

router = APIRouter()


# --- Overview -----------------------------------------------------------------

@router.get("/overview", response_model=PostingOverview)
async def get_overview(db: AsyncSession = Depends(get_db)):
    return await service.get_overview(db)


# --- Collections --------------------------------------------------------------

@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(
    persona_id: UUID | None = Query(None),
    plateforme: str | None = Query(None),
    collection_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_collections(
        db, persona_id=persona_id, plateforme=plateforme, collection_type=collection_type,
    )


@router.get("/collections/{cid}", response_model=CollectionOut)
async def get_collection(cid: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_collection(db, cid)
    if not c:
        raise HTTPException(404, "collection not found")
    return c


@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(data: CollectionCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_collection(db, data)


@router.patch("/collections/{cid}", response_model=CollectionOut)
async def update_collection(cid: UUID, data: CollectionUpdate, db: AsyncSession = Depends(get_db)):
    c = await service.get_collection(db, cid)
    if not c:
        raise HTTPException(404, "collection not found")
    return await service.update_collection(db, c, data)


@router.delete("/collections/{cid}", status_code=204)
async def delete_collection(cid: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_collection(db, cid)
    if not c:
        raise HTTPException(404, "collection not found")
    await service.delete_collection(db, c)


# --- Medias -------------------------------------------------------------------

@router.get("/medias", response_model=list[MediaOut])
async def list_medias(
    persona_id: UUID | None = Query(None),
    media_type: str | None = Query(None),
    folder: str | None = Query(None),
    used: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_medias(
        db, persona_id=persona_id, media_type=media_type, folder=folder, used=used,
    )


@router.get("/medias/{mid}", response_model=MediaOut)
async def get_media(mid: UUID, db: AsyncSession = Depends(get_db)):
    m = await service.get_media(db, mid)
    if not m:
        raise HTTPException(404, "media not found")
    return m


@router.post("/medias", response_model=MediaOut, status_code=201)
async def create_media(data: MediaCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_media(db, data)


@router.patch("/medias/{mid}", response_model=MediaOut)
async def update_media(mid: UUID, data: MediaUpdate, db: AsyncSession = Depends(get_db)):
    m = await service.get_media(db, mid)
    if not m:
        raise HTTPException(404, "media not found")
    return await service.update_media(db, m, data)


@router.delete("/medias/{mid}", status_code=204)
async def delete_media(mid: UUID, db: AsyncSession = Depends(get_db)):
    m = await service.get_media(db, mid)
    if not m:
        raise HTTPException(404, "media not found")
    await service.delete_media(db, m)


# --- Templates ----------------------------------------------------------------

@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    persona_id: UUID | None = Query(None),
    plateforme: str | None = Query(None),
    template_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_templates(
        db, persona_id=persona_id, plateforme=plateforme, template_type=template_type,
    )


@router.get("/templates/{tid}", response_model=TemplateOut)
async def get_template(tid: UUID, db: AsyncSession = Depends(get_db)):
    t = await service.get_template(db, tid)
    if not t:
        raise HTTPException(404, "template not found")
    return t


@router.post("/templates", response_model=TemplateOut, status_code=201)
async def create_template(data: TemplateCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_template(db, data)


@router.patch("/templates/{tid}", response_model=TemplateOut)
async def update_template(tid: UUID, data: TemplateUpdate, db: AsyncSession = Depends(get_db)):
    t = await service.get_template(db, tid)
    if not t:
        raise HTTPException(404, "template not found")
    return await service.update_template(db, t, data)


@router.delete("/templates/{tid}", status_code=204)
async def delete_template(tid: UUID, db: AsyncSession = Depends(get_db)):
    t = await service.get_template(db, tid)
    if not t:
        raise HTTPException(404, "template not found")
    await service.delete_template(db, t)


# --- Campagnes ----------------------------------------------------------------

@router.get("/campagnes", response_model=list[CampagneOut])
async def list_campagnes(
    persona_id: UUID | None = Query(None),
    plateforme: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_campagnes(
        db, persona_id=persona_id, plateforme=plateforme, status=status,
    )


@router.get("/campagnes/{cid}", response_model=CampagneOut)
async def get_campagne(cid: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_campagne(db, cid)
    if not c:
        raise HTTPException(404, "campagne not found")
    return c


@router.post("/campagnes", response_model=CampagneOut, status_code=201)
async def create_campagne(data: CampagneCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_campagne(db, data)


@router.patch("/campagnes/{cid}", response_model=CampagneOut)
async def update_campagne(cid: UUID, data: CampagneUpdate, db: AsyncSession = Depends(get_db)):
    c = await service.get_campagne(db, cid)
    if not c:
        raise HTTPException(404, "campagne not found")
    return await service.update_campagne(db, c, data)


@router.delete("/campagnes/{cid}", status_code=204)
async def delete_campagne(cid: UUID, db: AsyncSession = Depends(get_db)):
    c = await service.get_campagne(db, cid)
    if not c:
        raise HTTPException(404, "campagne not found")
    await service.delete_campagne(db, c)


# --- Publications -------------------------------------------------------------

@router.get("/publications", response_model=list[PublicationOut])
async def list_publications(
    compte_id: UUID | None = Query(None),
    campagne_id: UUID | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_publications(
        db, compte_id=compte_id, campagne_id=campagne_id, status=status,
    )


@router.get("/publications/{pid}", response_model=PublicationOut)
async def get_publication(pid: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_publication(db, pid)
    if not p:
        raise HTTPException(404, "publication not found")
    return p


@router.post("/publications", response_model=PublicationOut, status_code=201)
async def create_publication(data: PublicationCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_publication(db, data)


@router.patch("/publications/{pid}", response_model=PublicationOut)
async def update_publication(pid: UUID, data: PublicationUpdate, db: AsyncSession = Depends(get_db)):
    p = await service.get_publication(db, pid)
    if not p:
        raise HTTPException(404, "publication not found")
    return await service.update_publication(db, p, data)


@router.delete("/publications/{pid}", status_code=204)
async def delete_publication(pid: UUID, db: AsyncSession = Depends(get_db)):
    p = await service.get_publication(db, pid)
    if not p:
        raise HTTPException(404, "publication not found")
    await service.delete_publication(db, p)


@router.post("/publications/{pid}/publish")
async def dispatch_publication(pid: UUID, db: AsyncSession = Depends(get_db)):
    """Dispatch a publication to the iPhone for immediate execution.

    Resolves: publication → compte → device → media URLs → run_ig_task.
    """
    from app.services.comptes import _log as emit_log

    pub = await service.get_publication(db, pid)
    if not pub:
        raise HTTPException(404, "publication not found")

    if pub.status == "published":
        raise HTTPException(400, "Publication déjà publiée")

    # Resolve compte
    from app.models.compte import Compte
    compte = await db.get(Compte, pub.compte_id)
    if not compte:
        raise HTTPException(400, "Compte introuvable")
    if not compte.device_id:
        raise HTTPException(400, "Pas d'iPhone assigné au compte")

    # Resolve media URLs
    media_urls = pub.media_urls or []
    if not media_urls and pub.media_id:
        from app.models.posting import Media
        media = await db.get(Media, pub.media_id)
        if media and media.url:
            media_urls = [media.url]

    if not media_urls:
        raise HTTPException(400, "Aucun média associé à la publication")

    # Resolve market from persona
    market = "FR"
    if compte.persona_id:
        from app.models.persona import Persona
        persona = await db.get(Persona, compte.persona_id)
        if persona and persona.market:
            market = persona.market

    # Map post_type to runner action
    post_type = pub.post_type or "post"
    action_map = {
        "post": "ig_post",
        "story": "ig_story_post",
        "reel": "ig_reel_post",
        "carousel": "ig_post",
    }
    action = action_map.get(post_type, "ig_post")

    # Build values for the runner
    values = {
        "media_urls": media_urls if action == "ig_post" else None,
        "media_url": media_urls[0] if action != "ig_post" and media_urls else None,
        "caption": pub.caption or "",
        "first_comment": pub.first_comment,
        "market": market,
        "phone_id": str(compte.id),
        "stickers": pub.stickers,
    }
    # Remove None values
    values = {k: v for k, v in values.items() if v is not None}

    # Update status
    pub.status = "publishing"
    await db.commit()

    await emit_log("posting", "publish", "info", compte.handle,
        f"Publication lancée — {post_type} avec {len(media_urls)} média(s)")

    # Dispatch as background task
    asyncio.create_task(
        _run_publication(pub.id, compte.id, compte.plateforme, action, values, compte.handle),
        name=f"publish_{compte.handle}_{pub.id}",
    )

    logger.info("dispatch_publication: %s %s for @%s", action, pub.id, compte.handle)
    return {"ok": True, "action": action, "media_count": len(media_urls), "post_type": post_type}


async def _run_publication(pub_id: UUID, compte_id: UUID, plateforme: str,
                           action: str, values: dict, handle: str = ""):
    """Background task: run the publication on the iPhone."""
    from app.services.engine import LogCollector
    from app.services.comptes import _log as emit_log

    collector = LogCollector()
    try:
        if plateforme == "ig":
            from app.services.automation.ig_runner import run_ig_task
            ok, msg = await run_ig_task(compte_id, action, values=values, log=collector)
        else:
            await emit_log("posting", "publish", "warning", handle,
                f"Pas de script de publication pour {plateforme}")
            return

        meta = {"session_logs": collector.lines}
        if ok:
            logger.info("publish: %s publié — %s", handle, msg)
            await emit_log("posting", "publish", "success", handle,
                f"Publication réussie — {msg}", meta=meta)
            # Update publication status
            from app.db import AsyncSessionLocal
            from app.models.posting import Publication
            async with AsyncSessionLocal() as db:
                p = await db.get(Publication, pub_id)
                if p:
                    p.status = "published"
                    await db.commit()
        else:
            logger.error("publish: %s échec — %s", handle, msg)
            await emit_log("posting", "publish", "error", handle,
                f"Échec publication — {msg}", code="PUBLISH_FAILED", meta=meta)
            from app.db import AsyncSessionLocal
            from app.models.posting import Publication
            async with AsyncSessionLocal() as db:
                p = await db.get(Publication, pub_id)
                if p:
                    p.status = "failed"
                    await db.commit()
    except Exception:
        import traceback
        logger.exception("publish: erreur inattendue pour %s", handle)
        meta = {"session_logs": collector.lines}
        await emit_log("posting", "publish", "error", handle,
            f"Erreur publication: {traceback.format_exc()[-200:]}", code="PUBLISH_EXCEPTION", meta=meta)
        from app.db import AsyncSessionLocal
        from app.models.posting import Publication
        async with AsyncSessionLocal() as db:
            p = await db.get(Publication, pub_id)
            if p:
                p.status = "failed"
                await db.commit()


# --- Sounds (IG music) -------------------------------------------------------

@router.get("/sounds")
async def get_trending_sounds(db: AsyncSession = Depends(get_db)):
    """Récupère les sons tendance IG via l'API privée d'un compte avec session."""
    from app.services.ig_api import IGApiClient
    from app.models.compte import Compte
    from sqlalchemy import select

    # Trouver un compte IG avec une session active
    q = select(Compte).where(
        Compte.plateforme == "ig",
        Compte.session_data.isnot(None),
        Compte.status.in_(["ok", "active"]),
    ).limit(5)
    result = await db.execute(q)
    comptes = result.scalars().all()

    for compte in comptes:
        sd = compte.session_data or {}
        if not sd.get("sessionid") and not sd.get("authorization"):
            continue
        try:
            client = IGApiClient._from_session(sd)
            tracks = await client.get_trending_music(count=30)
            if tracks:
                return tracks
        except Exception as e:
            logger.warning("sounds: trending failed for %s: %s", compte.handle, str(e)[:100])
            continue

    return []


@router.get("/sounds/search")
async def search_sounds(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Recherche de sons IG par titre/artiste."""
    from app.services.ig_api import IGApiClient
    from app.models.compte import Compte
    from sqlalchemy import select

    query = select(Compte).where(
        Compte.plateforme == "ig",
        Compte.session_data.isnot(None),
        Compte.status.in_(["ok", "active"]),
    ).limit(5)
    result = await db.execute(query)
    comptes = result.scalars().all()

    for compte in comptes:
        sd = compte.session_data or {}
        if not sd.get("sessionid") and not sd.get("authorization"):
            continue
        try:
            client = IGApiClient._from_session(sd)
            tracks = await client.search_music(q, count=20)
            if tracks:
                return tracks
        except Exception as e:
            logger.warning("sounds: search failed for %s: %s", compte.handle, str(e)[:100])
            continue

    return []
