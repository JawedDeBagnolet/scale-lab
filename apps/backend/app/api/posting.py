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


@router.post("/medias/generate-thumbnails")
async def generate_thumbnails(db: AsyncSession = Depends(get_db)):
    """Generate R2 thumbnails for all image medias that don't have one yet."""
    from app.services.thumb_generator import generate_missing_thumbnails
    result = await generate_missing_thumbnails(db)
    return result


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
    values["username"] = compte.handle
    # Audio query from stickers or publication extras
    if pub.stickers:
        if pub.stickers.get("audio_query"):
            values["audio_query"] = pub.stickers["audio_query"]
        if pub.stickers.get("feed_session"):
            values["feed_session"] = True
            feed_cfg = pub.stickers.get("feed_cfg", {})
            values["feed_duration_min"] = feed_cfg.get("min", 1)
            values["feed_duration_max"] = feed_cfg.get("max", 3)
            values["feed_preset_id"] = feed_cfg.get("beh")  # UUID du preset comportement
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

async def _get_ig_client(db):
    """Get an IG API client from any compte with a valid session + proxy."""
    from app.services.ig_api import IGApiClient
    from app.models.compte import Compte
    from sqlalchemy import select

    q = select(Compte).where(
        Compte.plateforme == "ig",
        Compte.session_data.isnot(None),
        Compte.status.in_(["ok", "active"]),
    ).limit(5)
    result = await db.execute(q)
    for compte in result.scalars():
        sd = compte.session_data or {}
        if sd.get("sessionid") or sd.get("authorization"):
            try:
                client = IGApiClient._from_session(sd)
                # Attach Scrapigo proxy if available
                try:
                    from app.services.scrapigo import get_scrapigo_client
                    scrapigo = await get_scrapigo_client()
                    if scrapigo:
                        env = compte.env or {}
                        country = env.get("proxy_country", "FR")
                        proxy = await scrapigo.get_proxy_for_account(
                            account_id=str(compte.id), country=country, ttl_minutes=120,
                        )
                        if proxy:
                            client.proxy_url = proxy.url
                            logger.info("sounds: proxy %s:%d (%s)", proxy.host, proxy.port, country)
                except Exception as pe:
                    logger.warning("sounds: proxy unavailable: %s", str(pe)[:100])
                return client, compte.handle
            except Exception:
                continue
    return None, None


@router.get("/sounds")
async def get_trending_sounds(db: AsyncSession = Depends(get_db)):
    """Trending IG sounds — hybride: local DB + scrape IG si besoin.

    Retourne les sons stockés localement, enrichis par un refresh IG
    en background si les données ont plus de 30 min.
    """
    from app.models.posting import Sound
    from sqlalchemy import select
    from datetime import UTC, datetime, timedelta
    import asyncio

    # 1. Charger les sons locaux (trending)
    q = select(Sound).where(Sound.is_trending == True).order_by(Sound.ig_rank.asc()).limit(50)
    result = await db.execute(q)
    local_sounds = result.scalars().all()

    # 2. Si on a des sons récents (< 30 min), retourner directement
    if local_sounds:
        newest = max(s.updated_at for s in local_sounds)
        if newest > datetime.now(UTC) - timedelta(minutes=30):
            return [_sound_to_dict(s) for s in local_sounds]

    # 3. Scrape IG trending et persiste
    client, handle = await _get_ig_client(db)
    if client:
        try:
            tracks = await client.get_trending_music(count=30)
            if tracks:
                logger.info("sounds: %s returned %d trending tracks, persisting...", handle, len(tracks))
                await _upsert_sounds(db, tracks, source="ig_trending")
                # Re-fetch from DB (clean data)
                result = await db.execute(
                    select(Sound).where(Sound.is_trending == True).order_by(Sound.ig_rank.asc()).limit(50)
                )
                local_sounds = result.scalars().all()
        except Exception as e:
            logger.warning("sounds: trending scrape failed: %s", str(e)[:200])

    return [_sound_to_dict(s) for s in local_sounds]


@router.get("/sounds/search")
async def search_sounds(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Recherche de sons — IG live direct, sans persistence (vitesse max).

    Les sons recherchés ne sont pas stockés en base. L'utilisateur like
    ceux qu'il veut garder. Seuls trending (scrape) et veille persistent.
    """
    from app.services.ig_api import IGApiClient
    from app.models.compte import Compte
    from sqlalchemy import select

    # Client IG SANS proxy (vitesse max pour la recherche live)
    stmt = select(Compte).where(
        Compte.plateforme == "ig",
        Compte.session_data.isnot(None),
        Compte.status.in_(["ok", "active"]),
    ).limit(5)
    result = await db.execute(stmt)
    for compte in result.scalars():
        sd = compte.session_data or {}
        if not sd.get("sessionid") and not sd.get("authorization"):
            continue
        try:
            client = IGApiClient._from_session(sd)
            # Pas de proxy → requête directe → ~1-2s au lieu de ~5-6s
            return await client.search_music(q, count=20)
        except Exception as e:
            logger.warning("sounds: search failed for %s: %s", compte.handle, str(e)[:100])
            continue

    return []


async def _upsert_sounds(db, tracks: list[dict], source: str = "ig_trending"):
    """Insert or update sounds in DB from IG API results."""
    from app.models.posting import Sound
    from sqlalchemy import select
    from datetime import UTC, datetime

    is_trending = source == "ig_trending"

    # Reset trending flags if this is a trending refresh
    if is_trending:
        from sqlalchemy import update
        await db.execute(update(Sound).where(Sound.is_trending == True).values(is_trending=False, ig_rank=None))

    for i, t in enumerate(tracks):
        ig_id = str(t.get("id", ""))
        if not ig_id:
            continue

        # Check if exists
        existing = await db.execute(select(Sound).where(Sound.ig_id == ig_id))
        sound = existing.scalar_one_or_none()

        if sound:
            # Update
            sound.title = t.get("title") or sound.title
            sound.artist = t.get("artist") or sound.artist
            sound.cover_url = t.get("cover_url") or sound.cover_url
            sound.preview_url = t.get("preview_url") or sound.preview_url
            sound.duration_ms = t.get("duration_ms") or sound.duration_ms
            if t.get("use_count"):
                sound.use_count = t["use_count"]
            if is_trending:
                sound.is_trending = True
                sound.ig_rank = i + 1
            sound.updated_at = datetime.now(UTC)
        else:
            # Insert
            sound = Sound(
                ig_id=ig_id,
                title=t.get("title", ""),
                artist=t.get("artist", ""),
                cover_url=t.get("cover_url"),
                preview_url=t.get("preview_url"),
                duration_ms=t.get("duration_ms"),
                use_count=t.get("use_count", 0),
                ig_rank=i + 1 if is_trending else None,
                is_trending=is_trending,
                source=source,
            )
            db.add(sound)

    await db.commit()


def _sound_to_dict(s) -> dict:
    """Convert Sound model to API response dict."""
    return {
        "id": str(s.ig_id),
        "title": s.title,
        "artist": s.artist or "",
        "cover_url": s.cover_url or "",
        "preview_url": s.preview_url or "",
        "duration_ms": s.duration_ms or 0,
        "use_count": s.use_count or 0,
        "ofm_score": s.ofm_score or 0,
        "ig_rank": s.ig_rank,
        "is_trending": s.is_trending,
        "source": s.source,
    }
