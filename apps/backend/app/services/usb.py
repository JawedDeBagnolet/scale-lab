"""USB iPhone detection service — monitors connected iPhones via usbmuxd.

Uses pymobiledevice3 to:
- Detect iPhones connected via USB
- Read device info (UDID, model, iOS version, jailbreak status)
- Auto-update iPhone status in database (online/offline)
- Collect telemetry (battery, storage) on heartbeat ticks
- Broadcast status changes via WebSocket

Requires usbmuxd running on the VPS (apt install usbmuxd).
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models.iphone import IPhone
from app.ws import manager as ws_manager

logger = logging.getLogger("usb")

# ---------------------------------------------------------------------------
# pymobiledevice3 wrappers (graceful fallback if usbmuxd not available)
# ---------------------------------------------------------------------------

_PYMOBILE_AVAILABLE = False

try:
    from pymobiledevice3.usbmux import list_devices as _usbmux_list_devices
    from pymobiledevice3.lockdown import create_using_usbmux as _create_lockdown
    from pymobiledevice3.exceptions import (
        ConnectionFailedToUsbmuxdError,
        MuxException,
    )
    _PYMOBILE_AVAILABLE = True
except ImportError:
    logger.warning("pymobiledevice3 not installed — USB detection disabled")


async def _list_usb_devices() -> list[dict]:
    """Return list of connected USB devices with basic info.

    Each dict: {serial: str, device_id: int, connection_type: str}
    Returns empty list if usbmuxd is unavailable.
    """
    if not _PYMOBILE_AVAILABLE:
        return []

    try:
        devices = await _usbmux_list_devices()
        return [
            {
                "serial": d.serial,
                "device_id": d.device_id,
                "connection_type": d.connection_type,
            }
            for d in devices
        ]
    except ConnectionFailedToUsbmuxdError:
        logger.debug("usbmuxd not running or not accessible")
        return []
    except Exception:
        logger.exception("Error listing USB devices")
        return []


async def _get_device_info(serial: str) -> dict | None:
    """Get detailed info from a connected iPhone via lockdown.

    Returns dict with: udid, name, model, ios_version, jailbreak, battery, storage
    Returns None if device not reachable.
    """
    if not _PYMOBILE_AVAILABLE:
        return None

    try:
        lockdown = await _create_lockdown(serial=serial)

        # Basic device info from lockdown values
        all_values = lockdown.all_values

        info = {
            "udid": all_values.get("UniqueDeviceID", serial),
            "name": all_values.get("DeviceName", "iPhone"),
            "model": all_values.get("ProductType", "Unknown"),       # e.g. iPhone14,5
            "model_name": all_values.get("MarketingName", ""),        # e.g. iPhone 13 Pro
            "ios_version": all_values.get("ProductVersion", "?"),     # e.g. 16.5
            "serial_number": all_values.get("SerialNumber", ""),
            "wifi_mac": all_values.get("WiFiAddress", ""),
            "phone_number": all_values.get("PhoneNumber", ""),
            "jailbreak": _check_jailbreak(all_values),
        }

        # Battery info (may fail on some devices)
        try:
            battery = all_values.get("BatteryCurrentCapacity")
            if battery is not None:
                info["battery_pct"] = int(battery)
                info["charging"] = all_values.get("BatteryIsCharging", False)
        except Exception:
            pass

        # Disk space
        try:
            total = all_values.get("TotalDiskCapacity", 0)
            available = all_values.get("AmountDataAvailable", 0)
            if total:
                info["storage_total_gb"] = round(total / (1024 ** 3), 1)
                info["storage_free_gb"] = round(available / (1024 ** 3), 1)
        except Exception:
            pass

        return info

    except ConnectionFailedToUsbmuxdError:
        return None
    except Exception:
        logger.exception("Error getting device info for %s", serial)
        return None


def _check_jailbreak(values: dict) -> bool:
    """Heuristic jailbreak detection from lockdown values."""
    # Common indicators
    if values.get("BrickState"):
        return False
    # Jailbroken devices often have modified ProductionSOC or other markers
    # Most reliable: check for Cydia/Sileo presence via lockdown
    # For now, use a conservative check
    return False  # Will be updated with proper detection


# ---------------------------------------------------------------------------
# Detection scan (called from API)
# ---------------------------------------------------------------------------

async def scan_usb_devices() -> list[dict]:
    """Scan USB bus and return info for each connected iPhone.

    Returns list of dicts with device info, plus a `db_match` field
    indicating if the device is already registered in the database.
    """
    raw_devices = await _list_usb_devices()
    if not raw_devices:
        return []

    results = []
    async with AsyncSessionLocal() as db:
        for dev in raw_devices:
            serial = dev["serial"]

            # Get detailed info
            info = await _get_device_info(serial)
            if not info:
                # Can't read info, still report the device
                info = {"udid": serial, "name": "Unknown", "model": "Unknown", "ios_version": "?"}

            # Check if already in database (match by UDID in name or device_id-like field)
            # We store UDID as part of the telemetry or match by serial
            existing = await _find_iphone_by_udid(db, serial)
            info["db_match"] = str(existing.id) if existing else None
            info["db_status"] = existing.status if existing else None
            info["connection_type"] = dev.get("connection_type", "USB")

            results.append(info)

    return results


async def provision_device(
    db: AsyncSession,
    serial: str,
    *,
    name: str | None = None,
    rack: str | None = None,
    market: str | None = None,
    max_comptes: int = 3,
) -> IPhone:
    """Pair and register a new iPhone from USB detection.

    Reads device info via lockdown, creates or updates the iPhone record.
    """
    info = await _get_device_info(serial)
    if not info:
        raise ValueError(f"Cannot read device info for serial {serial}. Is the device trusted?")

    # Check if already registered
    existing = await _find_iphone_by_udid(db, serial)
    if existing:
        # Update with fresh info
        existing.status = "online"
        existing.model = info.get("model_name") or info.get("model", existing.model)
        existing.ios_version = info.get("ios_version", existing.ios_version)
        existing.jailbreak = info.get("jailbreak", existing.jailbreak)
        telemetry = dict(existing.telemetry or {})
        telemetry["udid"] = info["udid"]
        telemetry["last_seen"] = datetime.now(UTC).isoformat()
        if "battery_pct" in info:
            telemetry["battery_pct"] = info["battery_pct"]
            telemetry["charging"] = info.get("charging", False)
        if "storage_total_gb" in info:
            telemetry["storage_total_gb"] = info["storage_total_gb"]
            telemetry["storage_free_gb"] = info["storage_free_gb"]
        existing.telemetry = telemetry
        await db.commit()
        await db.refresh(existing)
        await _broadcast_iphone_status(existing)
        return existing

    # Create new iPhone record
    device_name = name or info.get("name", "iPhone")
    iphone = IPhone(
        name=device_name,
        model=info.get("model_name") or info.get("model", "Unknown"),
        ios_version=info.get("ios_version", "?"),
        rack=rack,
        market=market,
        status="online",
        jailbreak=info.get("jailbreak", False),
        max_comptes=max_comptes,
        telemetry={
            "udid": info["udid"],
            "serial_number": info.get("serial_number", ""),
            "wifi_mac": info.get("wifi_mac", ""),
            "last_seen": datetime.now(UTC).isoformat(),
            "battery_pct": info.get("battery_pct"),
            "charging": info.get("charging"),
            "storage_total_gb": info.get("storage_total_gb"),
            "storage_free_gb": info.get("storage_free_gb"),
        },
    )
    db.add(iphone)
    await db.commit()
    await db.refresh(iphone)
    await _broadcast_iphone_status(iphone)
    logger.info("Provisioned new iPhone: %s (UDID: %s)", device_name, info["udid"])
    return iphone


# ---------------------------------------------------------------------------
# Background monitor loop
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL = 30  # seconds between heartbeats
OFFLINE_GRACE = 60       # seconds before marking disconnected device as offline


class USBMonitor:
    """Background service that monitors USB-connected iPhones."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._known_serials: set[str] = set()  # currently connected

    async def start(self) -> None:
        if self._running:
            return
        if not _PYMOBILE_AVAILABLE:
            logger.info("USB monitor disabled — pymobiledevice3 not available")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="usb-monitor")
        logger.info("USB monitor started (heartbeat every %ds)", HEARTBEAT_INTERVAL)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("USB monitor stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._heartbeat()
            except Exception:
                logger.exception("USB heartbeat error")
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _heartbeat(self) -> None:
        """One heartbeat cycle: detect devices, update statuses, collect telemetry."""
        current_devices = await _list_usb_devices()
        current_serials = {d["serial"] for d in current_devices}

        async with AsyncSessionLocal() as db:
            # Detect newly connected devices
            new_serials = current_serials - self._known_serials
            for serial in new_serials:
                iphone = await _find_iphone_by_udid(db, serial)
                if iphone and iphone.status != "online":
                    iphone.status = "online"
                    telemetry = dict(iphone.telemetry or {})
                    telemetry["last_seen"] = datetime.now(UTC).isoformat()
                    telemetry.pop("offline_since", None)
                    iphone.telemetry = telemetry
                    await db.commit()
                    await db.refresh(iphone)
                    await _broadcast_iphone_status(iphone)
                    logger.info("iPhone back online: %s (%s)", iphone.name, serial)

            # Detect disconnected devices
            lost_serials = self._known_serials - current_serials
            for serial in lost_serials:
                iphone = await _find_iphone_by_udid(db, serial)
                if iphone and iphone.status == "online":
                    iphone.status = "offline"
                    telemetry = dict(iphone.telemetry or {})
                    telemetry["offline_since"] = datetime.now(UTC).isoformat()
                    iphone.telemetry = telemetry
                    await db.commit()
                    await db.refresh(iphone)
                    await _broadcast_iphone_status(iphone)
                    logger.warning("iPhone went offline: %s (%s)", iphone.name, serial)

            # Update telemetry for all connected devices
            for dev in current_devices:
                serial = dev["serial"]
                iphone = await _find_iphone_by_udid(db, serial)
                if not iphone:
                    continue

                info = await _get_device_info(serial)
                if not info:
                    continue

                telemetry = dict(iphone.telemetry or {})
                telemetry["last_seen"] = datetime.now(UTC).isoformat()
                if "battery_pct" in info:
                    telemetry["battery_pct"] = info["battery_pct"]
                    telemetry["charging"] = info.get("charging", False)
                if "storage_total_gb" in info:
                    telemetry["storage_total_gb"] = info["storage_total_gb"]
                    telemetry["storage_free_gb"] = info["storage_free_gb"]
                iphone.telemetry = telemetry
                iphone.ios_version = info.get("ios_version", iphone.ios_version)
                iphone.jailbreak = info.get("jailbreak", iphone.jailbreak)
                await db.commit()

            self._known_serials = current_serials

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def connected_count(self) -> int:
        return len(self._known_serials)


# Singleton
usb_monitor = USBMonitor()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _find_iphone_by_udid(db: AsyncSession, udid: str) -> IPhone | None:
    """Find an iPhone record by its UDID stored in telemetry."""
    # Query all iPhones and check telemetry UDID
    # Using JSONB containment operator for efficiency
    result = await db.execute(
        select(IPhone).where(
            IPhone.telemetry["udid"].astext == udid
        )
    )
    return result.scalars().first()


async def _broadcast_iphone_status(iphone: IPhone) -> None:
    """Broadcast iPhone status change via WebSocket."""
    if ws_manager.count == 0:
        return
    await ws_manager.broadcast({
        "type": "iphone_status",
        "iphone_id": str(iphone.id),
        "name": iphone.name,
        "status": iphone.status,
        "telemetry": iphone.telemetry or {},
        "ts": datetime.now(UTC).isoformat(),
    })
