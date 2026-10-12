from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compte import Compte
from app.models.comportement import Preset
from app.models.log import Event, Incident
from app.models.persona import Persona
from app.models.target import Target
from app.schemas.dashboard import DashboardStats


async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)

    total_personas = await db.scalar(select(func.count(Persona.id))) or 0
    total_comptes = await db.scalar(select(func.count(Compte.id))) or 0
    total_targets = await db.scalar(select(func.count(Target.id))) or 0
    total_presets = await db.scalar(select(func.count(Preset.id))) or 0
    total_events = await db.scalar(select(func.count(Event.id))) or 0

    errors_24h = await db.scalar(
        select(func.count(Event.id)).where(
            Event.level.in_(["error", "critical"]),
            Event.timestamp >= day_ago,
        )
    ) or 0

    open_incidents = await db.scalar(
        select(func.count(Incident.id)).where(Incident.status == "open")
    ) or 0

    comptes_ok = await db.scalar(
        select(func.count(Compte.id)).where(Compte.status == "ok")
    ) or 0

    comptes_error = await db.scalar(
        select(func.count(Compte.id)).where(Compte.status.in_(["error", "suspendu"]))
    ) or 0

    return DashboardStats(
        total_personas=total_personas,
        total_comptes=total_comptes,
        total_targets=total_targets,
        total_presets=total_presets,
        total_events=total_events,
        errors_24h=errors_24h,
        open_incidents=open_incidents,
        comptes_ok=comptes_ok,
        comptes_error=comptes_error,
    )
