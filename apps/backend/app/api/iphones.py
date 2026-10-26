from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.iphone import (
    IPhoneCreate, IPhoneOut, IPhoneUpdate, ProvisionRequest,
    TelemetryUpdate, TunnelProvisionRequest, TunnelProbeResult,
    USBMonitorStatus, USBScanResult,
)
from app.services import iphones as service
from app.services.usb import scan_usb_devices, provision_device, usb_monitor, _PYMOBILE_AVAILABLE

router = APIRouter()


@router.get("/", response_model=list[IPhoneOut])
async def list_iphones(
    status: str | None = Query(None),
    market: str | None = Query(None),
    rack: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_iphones(db, status=status, market=market, rack=rack)


@router.get("/{iphone_id}", response_model=IPhoneOut)
async def get_iphone(iphone_id: UUID, db: AsyncSession = Depends(get_db)):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    return iphone


@router.post("/", response_model=IPhoneOut, status_code=201)
async def create_iphone(data: IPhoneCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_iphone(db, data)


@router.patch("/{iphone_id}", response_model=IPhoneOut)
async def update_iphone(
    iphone_id: UUID, data: IPhoneUpdate, db: AsyncSession = Depends(get_db)
):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    return await service.update_iphone(db, iphone, data.model_dump(exclude_unset=True))


@router.patch("/{iphone_id}/telemetry", response_model=IPhoneOut)
async def update_telemetry(
    iphone_id: UUID, data: TelemetryUpdate, db: AsyncSession = Depends(get_db)
):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    return await service.update_telemetry(db, iphone, data)


@router.delete("/{iphone_id}", status_code=204)
async def delete_iphone(iphone_id: UUID, db: AsyncSession = Depends(get_db)):
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")
    await service.delete_iphone(db, iphone)


# --- USB Detection ------------------------------------------------------------

@router.post("/usb/scan", response_model=USBScanResult)
async def usb_scan():
    """Scan USB bus for connected iPhones."""
    if not _PYMOBILE_AVAILABLE:
        return USBScanResult(devices=[], usbmuxd_available=False)
    devices = await scan_usb_devices()
    return USBScanResult(devices=devices, usbmuxd_available=True)


@router.post("/usb/provision", response_model=IPhoneOut, status_code=201)
async def usb_provision(data: ProvisionRequest, db: AsyncSession = Depends(get_db)):
    """Pair and register a detected iPhone."""
    try:
        return await provision_device(
            db,
            data.serial,
            name=data.name,
            rack=data.rack,
            market=data.market,
            max_comptes=data.max_comptes,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/usb/status", response_model=USBMonitorStatus)
async def usb_status():
    """Get USB monitor background service status."""
    return USBMonitorStatus(
        running=usb_monitor.is_running,
        connected_count=usb_monitor.connected_count,
        pymobiledevice_available=_PYMOBILE_AVAILABLE,
    )


@router.get("/{iphone_id}/agent")
async def agent_status(iphone_id: UUID, db: AsyncSession = Depends(get_db)):
    """Check if the on-device agent is running and reachable."""
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")

    conn_type = iphone.connection_type or "usb"

    if conn_type == "tunnel":
        if not iphone.mcp_port:
            return {"reachable": False, "reason": "tunnel mode but no mcp_port configured"}
        from app.services.dispatch import check_agent_status
        status = await check_agent_status(
            "",
            connection_type="tunnel",
            mcp_port=iphone.mcp_port,
            crane_port=iphone.crane_port,
        )
    else:
        udid = (iphone.telemetry or {}).get("udid")
        if not udid:
            return {"reachable": False, "reason": "no UDID — re-provision via USB"}
        from app.services.dispatch import check_agent_status
        status = await check_agent_status(udid, connection_type="usb")

    if status is None:
        return {"reachable": False, "reason": "agent not reachable"}
    return {"reachable": True, "agent": status}


# --- Tunnel provisioning ------------------------------------------------------

@router.post("/tunnel/provision", response_model=IPhoneOut, status_code=201)
async def tunnel_provision(
    data: TunnelProvisionRequest, db: AsyncSession = Depends(get_db)
):
    """Register an iPhone connected via reverse SSH tunnel."""
    # Create the iPhone with tunnel connection_type
    create_data = IPhoneCreate(
        name=data.name,
        model=data.model,
        ios_version=data.ios_version,
        jailbreak=data.jailbreak,
        rack=data.rack,
        market=data.market,
        max_comptes=data.max_comptes,
        connection_type="tunnel",
        mcp_port=data.mcp_port,
        crane_port=data.crane_port,
    )
    iphone = await service.create_iphone(db, create_data)

    # Store UDID in telemetry
    telemetry = iphone.telemetry or {}
    telemetry["udid"] = data.udid
    await service.update_iphone(db, iphone, {"telemetry": telemetry, "status": "online"})

    return iphone


@router.get("/{iphone_id}/tunnel/probe", response_model=TunnelProbeResult)
async def tunnel_probe_endpoint(
    iphone_id: UUID, db: AsyncSession = Depends(get_db)
):
    """Probe MCP + crane endpoints for a tunnel-connected iPhone."""
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")

    if (iphone.connection_type or "usb") != "tunnel":
        raise HTTPException(400, "iPhone is not in tunnel mode")

    from app.services.dispatch import tunnel_probe
    result = await tunnel_probe(
        mcp_port=iphone.mcp_port or 8190,
        crane_port=iphone.crane_port or 8180,
    )
    return TunnelProbeResult(**result)


@router.get("/{iphone_id}/containers")
async def list_device_containers(
    iphone_id: UUID, db: AsyncSession = Depends(get_db)
):
    """List containers on a tunnel-connected iPhone via crane-controller."""
    iphone = await service.get_iphone(db, iphone_id)
    if not iphone:
        raise HTTPException(404, "iphone not found")

    if (iphone.connection_type or "usb") != "tunnel":
        raise HTTPException(400, "Containers only available for tunnel-connected iPhones")

    from app.services.dispatch import list_containers
    containers = await list_containers(iphone.crane_port or 8180)
    return {"containers": containers}
