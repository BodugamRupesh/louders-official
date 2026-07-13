"""
Devices Router for LOUD Platform Licensing System.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin, require_admin_or_owner, require_owner
from app.models import AdminUser, Device
from app.schemas import (
    DeviceResponse,
    RegisterDeviceRequest,
    ResetDeviceRequest,
    SuccessResponse,
    UpdateDeviceRequest,
)
from app.services.device_service import DeviceService
from app.utils.responses import success_response


router = APIRouter(
    prefix="/api/v1/devices",
    tags=["Devices"],
)


def _serialize_device(device: Device) -> dict:
    return DeviceResponse.model_validate(
        device,
        from_attributes=True,
    ).model_dump()


@router.get(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="List Devices",
    description="Retrieve devices with optional filters. Authenticated admins only.",
)
async def list_devices(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    license_id: int | None = Query(None, ge=1, description="Filter by license ID"),
    device_id: int | None = Query(None, ge=1, description="Filter by device ID"),
    device_uuid: str | None = Query(None, description="Filter by device UUID"),
    browser: str | None = Query(None, description="Filter by browser"),
    operating_system: str | None = Query(None, description="Filter by operating system"),
    product_name: str | None = Query(None, description="Filter by product name"),
    customer_name: str | None = Query(None, description="Filter by customer name"),
    status: str | None = Query(None, description="Filter by device status: online, offline, disabled"),
    q: str | None = Query(None, description="Search devices by UUID, browser, OS, IP, or license key"),
) -> SuccessResponse:
    devices = DeviceService.list_devices(
        db,
        license_id=license_id,
        device_id=device_id,
        device_uuid=device_uuid,
        browser=browser,
        operating_system=operating_system,
        product_name=product_name,
        customer_name=customer_name,
        status=status,
        query_str=q,
    )
    return success_response(
        "Devices retrieved successfully.",
        data={
            "devices": [_serialize_device(device) for device in devices],
            "count": len(devices),
        },
    )


@router.get(
    "/stats",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Device Stats",
    description="Retrieve device statistics. Authenticated admins only.",
)
async def get_device_stats(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    stats = DeviceService.get_device_stats(db)
    return success_response(
        "Device statistics retrieved successfully.",
        data={"stats": stats},
    )


@router.get(
    "/{device_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Device",
    description="Retrieve a specific device by ID. Authenticated admins only.",
)
async def get_device(
    device_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    device = DeviceService.get_device(db, device_id)
    return success_response(
        "Device retrieved successfully.",
        data={"device": _serialize_device(device)},
    )


@router.post(
    "/register",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Device",
    description="Register a device for a license. Admin or Owner only.",
)
async def register_device(
    device_data: RegisterDeviceRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    device = DeviceService.register_device(
        db,
        license_id=device_data.license_id,
        device_uuid=device_data.device_uuid,
        browser=device_data.browser,
        operating_system=device_data.operating_system,
        extension_version=device_data.extension_version,
        device_name=device_data.device_name,
        ip_address=device_data.ip_address,
        device_fingerprint=device_data.device_fingerprint,
    )
    return success_response(
        "Device registered successfully.",
        data={"device": _serialize_device(device)},
    )


@router.post(
    "/reset",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset Device",
    description="Remove a registered device from a license. Owner only.",
)
async def reset_device(
    reset_data: ResetDeviceRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    result = DeviceService.reset_device_by_uuid(
        db,
        license_id=reset_data.license_id,
        device_uuid=reset_data.device_uuid,
    )
    return success_response(
        "Device reset successfully.",
        data={
            "license_id": reset_data.license_id,
            "device_uuid": reset_data.device_uuid,
            "reset": result,
        },
    )


@router.patch(
    "/{device_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Device",
    description="Update device information. Admin or Owner only.",
)
async def update_device(
    device_id: int,
    device_data: UpdateDeviceRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    device = DeviceService.update_device_info(
        db,
        device_id=device_id,
        browser=device_data.browser,
        operating_system=device_data.operating_system,
        extension_version=device_data.extension_version,
        device_name=device_data.device_name,
        ip_address=device_data.ip_address,
        device_fingerprint=device_data.device_fingerprint,
    )
    return success_response(
        "Device updated successfully.",
        data={"device": _serialize_device(device)},
    )


@router.post(
    "/{device_id}/disable",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable Device",
    description="Disable a device so it can no longer verify or heartbeat.",
)
async def disable_device(
    device_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    device = DeviceService.disable_device(db, device_id)
    return success_response(
        "Device disabled successfully.",
        data={"device": _serialize_device(device)},
    )


@router.post(
    "/{device_id}/force-logout",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Force Logout Device",
    description="Force logout a device by disabling it and invalidating its extension token.",
)
async def force_logout_device(
    device_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    device = DeviceService.force_logout_device(db, device_id)
    return success_response(
        "Device force logged out successfully.",
        data={"device": _serialize_device(device)},
    )


@router.post(
    "/{device_id}/reactivate",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate Device",
    description="Reactivate a previously disabled device.",
)
async def reactivate_device(
    device_id: int,
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessResponse:
    device = DeviceService.reactivate_device(db, device_id)
    return success_response(
        "Device reactivated successfully.",
        data={"device": _serialize_device(device)},
    )


@router.post(
    "/{device_id}/heartbeat",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Heartbeat Device",
    description="Update the last seen timestamp for a device.",
)
async def heartbeat_device(
    device_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    browser: str | None = Query(None, description="Browser name"),
    operating_system: str | None = Query(None, description="Operating system"),
    extension_version: str | None = Query(None, description="Extension version"),
    ip_address: str | None = Query(None, description="Public IP address"),
) -> SuccessResponse:
    device = DeviceService.update_heartbeat(
        db,
        device_id,
        browser=browser,
        operating_system=operating_system,
        extension_version=extension_version,
        ip_address=ip_address,
    )
    return success_response(
        "Device heartbeat updated successfully.",
        data={"device": _serialize_device(device)},
    )
