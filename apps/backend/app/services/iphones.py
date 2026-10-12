from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.iphone import IPhone
from app.schemas.iphone import IPhoneCreate, TelemetryUpdate


async def list_iphones(
    db: AsyncSession,
    *,
    status: str | None = None,
    market: str | None = None,
    rack: str | None = None,
) -> Sequence[IPhone]:
    q = select(IPhone).order_by(IPhone.name)
    if status:
        q = q.where(IPhone.status == status)
    if market:
        q = q.where(IPhone.market == market)
    if rack:
        q = q.where(IPhone.rack == rack)
    result = await db.execute(q)
    return result.scalars().all()


async def get_iphone(db: AsyncSession, iphone_id: UUID) -> IPhone | None:
    return await db.get(IPhone, iphone_id)


async def create_iphone(db: AsyncSession, data: IPhoneCreate) -> IPhone:
    iphone = IPhone(**data.model_dump())
    db.add(iphone)
    await db.commit()
    await db.refresh(iphone)
    return iphone


async def update_iphone(db: AsyncSession, iphone: IPhone, data: dict) -> IPhone:
    for k, v in data.items():
        setattr(iphone, k, v)
    await db.commit()
    await db.refresh(iphone)
    return iphone


async def update_telemetry(
    db: AsyncSession, iphone: IPhone, data: TelemetryUpdate
) -> IPhone:
    current = iphone.telemetry or {}
    patch = data.model_dump(exclude_unset=True)
    # Serialize datetimes to ISO strings for JSON storage
    for k, v in patch.items():
        if hasattr(v, "isoformat"):
            patch[k] = v.isoformat()
    current.update(patch)
    iphone.telemetry = current
    await db.commit()
    await db.refresh(iphone)
    return iphone


async def delete_iphone(db: AsyncSession, iphone: IPhone) -> None:
    await db.delete(iphone)
    await db.commit()
