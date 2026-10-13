from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TelemetryData(BaseModel):
    battery_pct: int | None = None
    charging: bool | None = None
    network_quality: str | None = None
    data_used_mb: float | None = None
    current_run: str | None = None
    current_compte: str | None = None
    last_run_at: datetime | None = None
    offline_since: datetime | None = None


class IPhoneBase(BaseModel):
    name: str
    model: str
    ios_version: str
    rack: str | None = None
    market: str | None = None
    status: str | None = "offline"
    jailbreak: bool | None = False
    max_comptes: int | None = 3
    proxy_id: UUID | None = None


class IPhoneCreate(IPhoneBase):
    pass


class IPhoneUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    ios_version: str | None = None
    rack: str | None = None
    market: str | None = None
    status: str | None = None
    jailbreak: bool | None = None
    max_comptes: int | None = None
    proxy_id: UUID | None = None


class TelemetryUpdate(BaseModel):
    battery_pct: int | None = None
    charging: bool | None = None
    network_quality: str | None = None
    data_used_mb: float | None = None
    current_run: str | None = None
    current_compte: str | None = None
    last_run_at: datetime | None = None
    offline_since: datetime | None = None


class IPhoneOut(IPhoneBase):
    id: UUID
    telemetry: dict | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- USB Detection ------------------------------------------------------------

class USBDeviceInfo(BaseModel):
    """Device detected on the USB bus."""
    udid: str
    name: str
    model: str
    model_name: str | None = None
    ios_version: str
    jailbreak: bool = False
    serial_number: str | None = None
    battery_pct: int | None = None
    charging: bool | None = None
    storage_total_gb: float | None = None
    storage_free_gb: float | None = None
    connection_type: str = "USB"
    db_match: UUID | None = None       # iPhone ID if already registered
    db_status: str | None = None       # current DB status if registered


class USBScanResult(BaseModel):
    """Result of a USB scan."""
    devices: list[USBDeviceInfo]
    usbmuxd_available: bool = True


class ProvisionRequest(BaseModel):
    """Request to provision a detected iPhone."""
    serial: str                        # UDID of the device
    name: str | None = None            # override device name
    rack: str | None = None
    market: str | None = None
    max_comptes: int = 3


class USBMonitorStatus(BaseModel):
    """Status of the USB monitor background service."""
    running: bool
    connected_count: int
    pymobiledevice_available: bool
