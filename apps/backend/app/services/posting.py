from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.posting import Campagne, Collection, Media, Publication, Template
from app.schemas.posting import (
    CampagneCreate,
    CampagneUpdate,
    CollectionCreate,
    CollectionUpdate,
    MediaCreate,
    MediaUpdate,
    PostingOverview,
    PublicationCreate,
    PublicationUpdate,
    TemplateCreate,
    TemplateUpdate,
)


# --- Collections --------------------------------------------------------------

async def list_collections(
    db: AsyncSession,
    *,
    persona_id: UUID | None = None,
    plateforme: str | None = None,
    collection_type: str | None = None,
) -> Sequence[Collection]:
    q = select(Collection).order_by(Collection.name)
    if persona_id:
        q = q.where(Collection.persona_id == persona_id)
    if plateforme:
        q = q.where(Collection.plateforme == plateforme)
    if collection_type:
        q = q.where(Collection.collection_type == collection_type)
    result = await db.execute(q)
    return result.scalars().all()


async def get_collection(db: AsyncSession, cid: UUID) -> Collection | None:
    return await db.get(Collection, cid)


async def create_collection(db: AsyncSession, data: CollectionCreate) -> Collection:
    c = Collection(**data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def update_collection(db: AsyncSession, c: Collection, data: CollectionUpdate) -> Collection:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(c, key, value)
    await db.commit()
    await db.refresh(c)
    return c


async def delete_collection(db: AsyncSession, c: Collection) -> None:
    await db.delete(c)
    await db.commit()


# --- Medias -------------------------------------------------------------------

async def list_medias(
    db: AsyncSession,
    *,
    persona_id: UUID | None = None,
    media_type: str | None = None,
    folder: str | None = None,
    used: bool | None = None,
) -> Sequence[Media]:
    q = select(Media).order_by(Media.created_at.desc())
    if persona_id:
        q = q.where(Media.persona_id == persona_id)
    if media_type:
        q = q.where(Media.media_type == media_type)
    if folder:
        q = q.where(Media.folder == folder)
    if used is not None:
        q = q.where(Media.used == used)
    result = await db.execute(q)
    return result.scalars().all()


async def get_media(db: AsyncSession, mid: UUID) -> Media | None:
    return await db.get(Media, mid)


async def create_media(db: AsyncSession, data: MediaCreate) -> Media:
    m = Media(**data.model_dump())
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def update_media(db: AsyncSession, m: Media, data: MediaUpdate) -> Media:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(m, key, value)
    await db.commit()
    await db.refresh(m)
    return m


async def delete_media(db: AsyncSession, m: Media) -> None:
    await db.delete(m)
    await db.commit()


# --- Templates ----------------------------------------------------------------

async def list_templates(
    db: AsyncSession,
    *,
    persona_id: UUID | None = None,
    plateforme: str | None = None,
    template_type: str | None = None,
) -> Sequence[Template]:
    q = select(Template).order_by(Template.name)
    if persona_id:
        q = q.where(Template.persona_id == persona_id)
    if plateforme:
        q = q.where(Template.plateforme == plateforme)
    if template_type:
        q = q.where(Template.template_type == template_type)
    result = await db.execute(q)
    return result.scalars().all()


async def get_template(db: AsyncSession, tid: UUID) -> Template | None:
    return await db.get(Template, tid)


async def create_template(db: AsyncSession, data: TemplateCreate) -> Template:
    t = Template(**data.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def update_template(db: AsyncSession, t: Template, data: TemplateUpdate) -> Template:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(t, key, value)
    await db.commit()
    await db.refresh(t)
    return t


async def delete_template(db: AsyncSession, t: Template) -> None:
    await db.delete(t)
    await db.commit()


# --- Campagnes ----------------------------------------------------------------

async def list_campagnes(
    db: AsyncSession,
    *,
    persona_id: UUID | None = None,
    plateforme: str | None = None,
    status: str | None = None,
) -> Sequence[Campagne]:
    q = select(Campagne).order_by(Campagne.created_at.desc())
    if persona_id:
        q = q.where(Campagne.persona_id == persona_id)
    if plateforme:
        q = q.where(Campagne.plateforme == plateforme)
    if status:
        q = q.where(Campagne.status == status)
    result = await db.execute(q)
    return result.scalars().all()


async def get_campagne(db: AsyncSession, cid: UUID) -> Campagne | None:
    return await db.get(Campagne, cid)


async def create_campagne(db: AsyncSession, data: CampagneCreate) -> Campagne:
    c = Campagne(**data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def update_campagne(db: AsyncSession, c: Campagne, data: CampagneUpdate) -> Campagne:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(c, key, value)
    await db.commit()
    await db.refresh(c)
    return c


async def delete_campagne(db: AsyncSession, c: Campagne) -> None:
    await db.delete(c)
    await db.commit()


# --- Publications -------------------------------------------------------------

async def list_publications(
    db: AsyncSession,
    *,
    compte_id: UUID | None = None,
    campagne_id: UUID | None = None,
    status: str | None = None,
) -> Sequence[Publication]:
    q = select(Publication).order_by(Publication.scheduled_at.desc().nullslast())
    if compte_id:
        q = q.where(Publication.compte_id == compte_id)
    if campagne_id:
        q = q.where(Publication.campagne_id == campagne_id)
    if status:
        q = q.where(Publication.status == status)
    result = await db.execute(q)
    return result.scalars().all()


async def get_publication(db: AsyncSession, pid: UUID) -> Publication | None:
    return await db.get(Publication, pid)


async def create_publication(db: AsyncSession, data: PublicationCreate) -> Publication:
    p = Publication(**data.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_publication(db: AsyncSession, p: Publication, data: PublicationUpdate) -> Publication:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(p, key, value)
    await db.commit()
    await db.refresh(p)
    return p


async def delete_publication(db: AsyncSession, p: Publication) -> None:
    await db.delete(p)
    await db.commit()


# --- Overview -----------------------------------------------------------------

async def get_overview(db: AsyncSession) -> PostingOverview:
    total_col = int((await db.execute(select(func.count(Collection.id)))).scalar() or 0)
    total_med = int((await db.execute(select(func.count(Media.id)))).scalar() or 0)
    total_tpl = int((await db.execute(select(func.count(Template.id)))).scalar() or 0)
    total_camp = int((await db.execute(select(func.count(Campagne.id)))).scalar() or 0)
    active_camp = int((await db.execute(
        select(func.count(Campagne.id)).where(Campagne.status == "active")
    )).scalar() or 0)
    total_pub = int((await db.execute(select(func.count(Publication.id)))).scalar() or 0)
    published = int((await db.execute(
        select(func.count(Publication.id)).where(Publication.status == "published")
    )).scalar() or 0)
    planned = int((await db.execute(
        select(func.count(Publication.id)).where(Publication.status == "planned")
    )).scalar() or 0)
    failed = int((await db.execute(
        select(func.count(Publication.id)).where(Publication.status == "failed")
    )).scalar() or 0)

    return PostingOverview(
        total_collections=total_col,
        total_medias=total_med,
        total_templates=total_tpl,
        total_campagnes=total_camp,
        active_campagnes=active_camp,
        total_publications=total_pub,
        published=published,
        planned=planned,
        failed=failed,
    )
