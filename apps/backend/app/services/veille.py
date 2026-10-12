from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.veille import Album, Favorite, Inspiration, Snipe, VeilleSource
from app.schemas.veille import (
    AlbumCreate,
    FavoriteCreate,
    SnipeCreate,
    VeilleOverview,
    VeilleSourceCreate,
)


# --- Sources ----------------------------------------------------------------

async def list_sources(
    db: AsyncSession,
    *,
    plateforme: str | None = None,
    niche_id: int | None = None,
    active: bool | None = None,
) -> Sequence[VeilleSource]:
    q = select(VeilleSource).order_by(VeilleSource.handle)
    if plateforme:
        q = q.where(VeilleSource.plateforme == plateforme)
    if niche_id is not None:
        q = q.where(VeilleSource.niche_id == niche_id)
    if active is not None:
        q = q.where(VeilleSource.active == active)
    result = await db.execute(q)
    return result.scalars().all()


async def get_source(db: AsyncSession, source_id: UUID) -> VeilleSource | None:
    return await db.get(VeilleSource, source_id)


async def create_source(db: AsyncSession, data: VeilleSourceCreate) -> VeilleSource:
    obj = VeilleSource(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def update_source(db: AsyncSession, source: VeilleSource, data: dict) -> VeilleSource:
    for k, v in data.items():
        setattr(source, k, v)
    await db.commit()
    await db.refresh(source)
    return source


async def delete_source(db: AsyncSession, source: VeilleSource) -> None:
    await db.delete(source)
    await db.commit()


# --- Inspirations -----------------------------------------------------------

async def list_inspirations(
    db: AsyncSession,
    *,
    source_id: UUID | None = None,
    status: str | None = None,
    media_type: str | None = None,
) -> Sequence[Inspiration]:
    q = select(Inspiration).order_by(Inspiration.saved_at.desc())
    if source_id is not None:
        q = q.where(Inspiration.source_id == source_id)
    if status:
        q = q.where(Inspiration.status == status)
    if media_type:
        q = q.where(Inspiration.media_type == media_type)
    result = await db.execute(q)
    return result.scalars().all()


async def get_inspiration(db: AsyncSession, insp_id: UUID) -> Inspiration | None:
    return await db.get(Inspiration, insp_id)


async def update_inspiration(db: AsyncSession, insp: Inspiration, data: dict) -> Inspiration:
    for k, v in data.items():
        setattr(insp, k, v)
    await db.commit()
    await db.refresh(insp)
    return insp


# --- Favorites --------------------------------------------------------------

async def list_favorites(
    db: AsyncSession,
    *,
    album_id: UUID | None = None,
) -> Sequence[Favorite]:
    q = select(Favorite).order_by(Favorite.created_at.desc())
    if album_id is not None:
        q = q.where(Favorite.album_id == album_id)
    result = await db.execute(q)
    return result.scalars().all()


async def get_favorite(db: AsyncSession, fav_id: UUID) -> Favorite | None:
    return await db.get(Favorite, fav_id)


async def add_favorite(db: AsyncSession, data: FavoriteCreate) -> Favorite:
    obj = Favorite(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def remove_favorite(db: AsyncSession, fav: Favorite) -> None:
    await db.delete(fav)
    await db.commit()


# --- Snipes -----------------------------------------------------------------

async def list_snipes(
    db: AsyncSession,
    *,
    status: str | None = None,
    priority: str | None = None,
    persona_id: UUID | None = None,
) -> Sequence[Snipe]:
    q = select(Snipe).order_by(Snipe.created_at.desc())
    if status:
        q = q.where(Snipe.status == status)
    if priority:
        q = q.where(Snipe.priority == priority)
    if persona_id is not None:
        q = q.where(Snipe.target_persona_id == persona_id)
    result = await db.execute(q)
    return result.scalars().all()


async def get_snipe(db: AsyncSession, snipe_id: UUID) -> Snipe | None:
    return await db.get(Snipe, snipe_id)


async def create_snipe(db: AsyncSession, data: SnipeCreate) -> Snipe:
    obj = Snipe(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def update_snipe(db: AsyncSession, snipe: Snipe, data: dict) -> Snipe:
    for k, v in data.items():
        setattr(snipe, k, v)
    await db.commit()
    await db.refresh(snipe)
    return snipe


# --- Albums -----------------------------------------------------------------

async def list_albums(
    db: AsyncSession,
    *,
    persona_id: UUID | None = None,
) -> Sequence[Album]:
    q = select(Album).order_by(Album.name)
    if persona_id is not None:
        q = q.where(Album.persona_id == persona_id)
    result = await db.execute(q)
    return result.scalars().all()


async def get_album(db: AsyncSession, album_id: UUID) -> Album | None:
    return await db.get(Album, album_id)


async def create_album(db: AsyncSession, data: AlbumCreate) -> Album:
    obj = Album(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def update_album(db: AsyncSession, album: Album, data: dict) -> Album:
    for k, v in data.items():
        setattr(album, k, v)
    await db.commit()
    await db.refresh(album)
    return album


async def delete_album(db: AsyncSession, album: Album) -> None:
    await db.delete(album)
    await db.commit()


# --- Overview ---------------------------------------------------------------

async def get_overview(db: AsyncSession) -> VeilleOverview:
    total_sources = (await db.execute(select(func.count(VeilleSource.id)))).scalar() or 0
    new_inspirations = (
        await db.execute(
            select(func.count(Inspiration.id)).where(Inspiration.status == "new")
        )
    ).scalar() or 0
    pending_snipes = (
        await db.execute(
            select(func.count(Snipe.id)).where(Snipe.status == "pending")
        )
    ).scalar() or 0
    total_albums = (await db.execute(select(func.count(Album.id)))).scalar() or 0

    return VeilleOverview(
        total_sources=total_sources,
        new_inspirations=new_inspirations,
        pending_snipes=pending_snipes,
        total_albums=total_albums,
    )
