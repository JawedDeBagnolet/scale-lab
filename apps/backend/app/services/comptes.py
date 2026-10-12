from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compte import Compte
from app.models.persona import Persona
from app.schemas.compte import CompteCreate, CompteUpdate


class PersonaNotFound(Exception):
    pass


async def _check_persona(db: AsyncSession, persona_id: UUID | None) -> None:
    if persona_id is not None and await db.get(Persona, persona_id) is None:
        raise PersonaNotFound


async def list_comptes(
    db: AsyncSession, persona_id: UUID | None = None, plateforme: str | None = None
) -> Sequence[Compte]:
    q = select(Compte).order_by(Compte.handle)
    if persona_id:
        q = q.where(Compte.persona_id == persona_id)
    if plateforme:
        q = q.where(Compte.plateforme == plateforme)
    result = await db.execute(q)
    return result.scalars().all()


async def get_compte(db: AsyncSession, compte_id: UUID) -> Compte | None:
    return await db.get(Compte, compte_id)


async def create_compte(db: AsyncSession, data: CompteCreate) -> Compte:
    await _check_persona(db, data.persona_id)
    compte = Compte(**data.model_dump())
    db.add(compte)
    await db.commit()
    return compte


async def update_compte(db: AsyncSession, compte: Compte, data: CompteUpdate) -> Compte:
    changes = data.model_dump(exclude_unset=True)
    await _check_persona(db, changes.get("persona_id"))
    for key, value in changes.items():
        setattr(compte, key, value)
    await db.commit()
    return compte


async def delete_compte(db: AsyncSession, compte: Compte) -> None:
    await db.delete(compte)
    await db.commit()
