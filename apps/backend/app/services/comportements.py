from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comportement import Preset
from app.schemas.comportement import PresetCreate


async def list_presets(
    db: AsyncSession,
    *,
    plateforme: str | None = None,
    session_type: str | None = None,
) -> Sequence[Preset]:
    q = select(Preset).order_by(Preset.name)
    if plateforme:
        q = q.where(Preset.plateforme == plateforme)
    if session_type:
        q = q.where(Preset.session_type == session_type)
    result = await db.execute(q)
    return result.scalars().all()


async def get_preset(db: AsyncSession, preset_id: UUID) -> Preset | None:
    return await db.get(Preset, preset_id)


async def create_preset(db: AsyncSession, data: PresetCreate) -> Preset:
    p = Preset(**data.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_preset(db: AsyncSession, preset: Preset, data: dict) -> Preset:
    for k, v in data.items():
        setattr(preset, k, v)
    await db.commit()
    await db.refresh(preset)
    return preset


async def delete_preset(db: AsyncSession, preset: Preset) -> None:
    await db.delete(preset)
    await db.commit()
