from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.schemas.persona import PersonaCreate, PersonaUpdate


async def list_personas(db: AsyncSession) -> Sequence[Persona]:
    result = await db.execute(select(Persona).order_by(Persona.first_name))
    return result.scalars().all()


async def get_persona(db: AsyncSession, persona_id: UUID) -> Persona | None:
    return await db.get(Persona, persona_id)


async def create_persona(db: AsyncSession, data: PersonaCreate) -> Persona:
    persona = Persona(**data.model_dump())
    db.add(persona)
    await db.commit()
    # Charge explicitement la relation : un lazy-load implicite est interdit en async
    await db.refresh(persona, attribute_names=["comptes"])
    return persona


async def update_persona(db: AsyncSession, persona: Persona, data: PersonaUpdate) -> Persona:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(persona, key, value)
    await db.commit()
    return persona


async def delete_persona(db: AsyncSession, persona: Persona) -> None:
    await db.delete(persona)
    await db.commit()
