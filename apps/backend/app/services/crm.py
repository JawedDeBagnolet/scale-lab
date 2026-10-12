from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import Fan, Script, Transaction
from app.schemas.crm import (
    CrmOverview,
    FanCreate,
    FanUpdate,
    ScriptCreate,
    ScriptUpdate,
    TransactionCreate,
)


# --- Fans ---------------------------------------------------------------------

async def list_fans(
    db: AsyncSession,
    *,
    creator_id: UUID | None = None,
    platform_origin: str | None = None,
) -> Sequence[Fan]:
    q = select(Fan).order_by(Fan.pseudo)
    if creator_id:
        q = q.where(Fan.creator_id == creator_id)
    if platform_origin:
        q = q.where(Fan.platform_origin == platform_origin)
    result = await db.execute(q)
    return result.scalars().all()


async def get_fan(db: AsyncSession, fan_id: UUID) -> Fan | None:
    return await db.get(Fan, fan_id)


async def create_fan(db: AsyncSession, data: FanCreate) -> Fan:
    fan = Fan(**data.model_dump())
    db.add(fan)
    await db.commit()
    await db.refresh(fan)
    return fan


async def update_fan(db: AsyncSession, fan: Fan, data: FanUpdate) -> Fan:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(fan, key, value)
    await db.commit()
    await db.refresh(fan)
    return fan


# --- Transactions -------------------------------------------------------------

async def list_transactions(
    db: AsyncSession,
    *,
    fan_id: UUID | None = None,
    creator_id: UUID | None = None,
    transaction_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Sequence[Transaction]:
    q = select(Transaction).order_by(Transaction.timestamp.desc())
    if fan_id:
        q = q.where(Transaction.fan_id == fan_id)
    if creator_id:
        q = q.where(Transaction.creator_id == creator_id)
    if transaction_type:
        q = q.where(Transaction.transaction_type == transaction_type)
    if date_from:
        q = q.where(Transaction.timestamp >= date_from)
    if date_to:
        q = q.where(Transaction.timestamp <= date_to)
    result = await db.execute(q)
    return result.scalars().all()


async def create_transaction(db: AsyncSession, data: TransactionCreate) -> Transaction:
    tx = Transaction(**data.model_dump())
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


async def get_revenue_summary(db: AsyncSession, creator_id: UUID) -> dict:
    result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.creator_id == creator_id)
    )
    total = int(result.scalar() or 0)
    return {"creator_id": str(creator_id), "total_revenue": total}


# --- Scripts ------------------------------------------------------------------

async def list_scripts(
    db: AsyncSession,
    *,
    active: bool | None = None,
    folder: str | None = None,
) -> Sequence[Script]:
    q = select(Script).order_by(Script.created_at.desc())
    if active is not None:
        q = q.where(Script.active == active)
    if folder:
        q = q.where(Script.folder == folder)
    result = await db.execute(q)
    return result.scalars().all()


async def get_script(db: AsyncSession, script_id: UUID) -> Script | None:
    return await db.get(Script, script_id)


async def create_script(db: AsyncSession, data: ScriptCreate) -> Script:
    script = Script(**data.model_dump())
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


async def update_script(db: AsyncSession, script: Script, data: ScriptUpdate) -> Script:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(script, key, value)
    await db.commit()
    await db.refresh(script)
    return script


async def delete_script(db: AsyncSession, script: Script) -> None:
    await db.delete(script)
    await db.commit()


# --- CRM Overview -------------------------------------------------------------

async def get_overview(db: AsyncSession) -> CrmOverview:
    # Total fans
    fans_result = await db.execute(select(func.count(Fan.id)))
    total_fans = int(fans_result.scalar() or 0)

    # Total revenue
    rev_result = await db.execute(select(func.coalesce(func.sum(Transaction.amount), 0)))
    total_revenue = int(rev_result.scalar() or 0)

    # Average LTV (avg total_spent across fans)
    ltv_result = await db.execute(select(func.coalesce(func.avg(Fan.total_spent), 0)))
    avg_ltv = round(float(ltv_result.scalar() or 0), 2)

    # Top script (highest total revenue in stats JSONB)
    # Simple approach: script with most transactions linked
    top_q = (
        select(Script.folder)
        .join(Transaction, Transaction.script_id == Script.id)
        .group_by(Script.id, Script.folder)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(1)
    )
    top_result = await db.execute(top_q)
    top_script = top_result.scalar()

    return CrmOverview(
        total_fans=total_fans,
        total_revenue=total_revenue,
        avg_ltv=avg_ltv,
        top_script=top_script,
    )
