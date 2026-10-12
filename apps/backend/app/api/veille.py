from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.veille import (
    AlbumCreate,
    AlbumOut,
    AlbumUpdate,
    FavoriteCreate,
    FavoriteOut,
    InspirationOut,
    InspirationUpdate,
    SnipeCreate,
    SnipeOut,
    SnipeUpdate,
    VeilleOverview,
    VeilleSourceCreate,
    VeilleSourceOut,
    VeilleSourceUpdate,
)
from app.services import veille as service

router = APIRouter()


# --- Overview ---------------------------------------------------------------

@router.get("/overview", response_model=VeilleOverview)
async def overview(db: AsyncSession = Depends(get_db)):
    return await service.get_overview(db)


# --- Sources ----------------------------------------------------------------

@router.get("/sources", response_model=list[VeilleSourceOut])
async def list_sources(
    plateforme: str | None = Query(None),
    niche_id: int | None = Query(None),
    active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_sources(
        db, plateforme=plateforme, niche_id=niche_id, active=active
    )


@router.post("/sources", response_model=VeilleSourceOut, status_code=201)
async def create_source(data: VeilleSourceCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_source(db, data)


@router.patch("/sources/{source_id}", response_model=VeilleSourceOut)
async def update_source(
    source_id: UUID, data: VeilleSourceUpdate, db: AsyncSession = Depends(get_db)
):
    s = await service.get_source(db, source_id)
    if not s:
        raise HTTPException(404, "source not found")
    return await service.update_source(db, s, data.model_dump(exclude_unset=True))


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    s = await service.get_source(db, source_id)
    if not s:
        raise HTTPException(404, "source not found")
    await service.delete_source(db, s)


# --- Inspirations -----------------------------------------------------------

@router.get("/inspirations", response_model=list[InspirationOut])
async def list_inspirations(
    source_id: UUID | None = Query(None),
    status: str | None = Query(None),
    media_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_inspirations(
        db, source_id=source_id, status=status, media_type=media_type
    )


@router.patch("/inspirations/{insp_id}", response_model=InspirationOut)
async def update_inspiration(
    insp_id: UUID, data: InspirationUpdate, db: AsyncSession = Depends(get_db)
):
    insp = await service.get_inspiration(db, insp_id)
    if not insp:
        raise HTTPException(404, "inspiration not found")
    return await service.update_inspiration(db, insp, data.model_dump(exclude_unset=True))


# --- Favorites --------------------------------------------------------------

@router.get("/favorites", response_model=list[FavoriteOut])
async def list_favorites(
    album_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_favorites(db, album_id=album_id)


@router.post("/favorites", response_model=FavoriteOut, status_code=201)
async def add_favorite(data: FavoriteCreate, db: AsyncSession = Depends(get_db)):
    return await service.add_favorite(db, data)


@router.delete("/favorites/{fav_id}", status_code=204)
async def remove_favorite(fav_id: UUID, db: AsyncSession = Depends(get_db)):
    fav = await service.get_favorite(db, fav_id)
    if not fav:
        raise HTTPException(404, "favorite not found")
    await service.remove_favorite(db, fav)


# --- Snipes -----------------------------------------------------------------

@router.get("/snipes", response_model=list[SnipeOut])
async def list_snipes(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    persona_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_snipes(
        db, status=status, priority=priority, persona_id=persona_id
    )


@router.post("/snipes", response_model=SnipeOut, status_code=201)
async def create_snipe(data: SnipeCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_snipe(db, data)


@router.patch("/snipes/{snipe_id}", response_model=SnipeOut)
async def update_snipe(
    snipe_id: UUID, data: SnipeUpdate, db: AsyncSession = Depends(get_db)
):
    snipe = await service.get_snipe(db, snipe_id)
    if not snipe:
        raise HTTPException(404, "snipe not found")
    return await service.update_snipe(db, snipe, data.model_dump(exclude_unset=True))


# --- Albums -----------------------------------------------------------------

@router.get("/albums", response_model=list[AlbumOut])
async def list_albums(
    persona_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_albums(db, persona_id=persona_id)


@router.post("/albums", response_model=AlbumOut, status_code=201)
async def create_album(data: AlbumCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_album(db, data)


@router.patch("/albums/{album_id}", response_model=AlbumOut)
async def update_album(
    album_id: UUID, data: AlbumUpdate, db: AsyncSession = Depends(get_db)
):
    album = await service.get_album(db, album_id)
    if not album:
        raise HTTPException(404, "album not found")
    return await service.update_album(db, album, data.model_dump(exclude_unset=True))


@router.delete("/albums/{album_id}", status_code=204)
async def delete_album(album_id: UUID, db: AsyncSession = Depends(get_db)):
    album = await service.get_album(db, album_id)
    if not album:
        raise HTTPException(404, "album not found")
    await service.delete_album(db, album)
