from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_personas: int
    total_comptes: int
    total_targets: int
    total_presets: int
    total_events: int
    errors_24h: int
    open_incidents: int
    comptes_ok: int
    comptes_error: int
