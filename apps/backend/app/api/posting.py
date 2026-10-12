from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
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
