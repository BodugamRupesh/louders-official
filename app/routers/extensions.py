"""
Extension API router for device activation, verification, and license management.

Security:
- All endpoints require product API key validation
- Licenses must belong to the requesting product
- Extension JWT tokens generated on activation
- All operations logged with activity logging
"""

from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.utils.datetime_utils import get_current_time, remaining_days
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, Product
from app.schemas import (
    ExtensionActivateRequest,
    ExtensionVerifyRequest,
    ExtensionExtendRequest,
    ExtensionHeartbeatRequest,
    ExtensionDeactivateRequest,
    ExtensionActivationResponse,
    ExtensionVerifyResponse,
    ExtensionExtendResponse,
    ExtensionDeactivateResponse,
    ExtensionErrorResponse,
    ExtensionHeartbeatResponse,
)
from app.services.extension_service import ExtensionService
from app.services.license_service import LicenseService
from app.services.device_service import DeviceService
from app.services.extension_jwt_service import ExtensionJWTService
from app.services.activity_log_service import ActivityLogService
from app.exceptions import (
    InvalidProductKeyError,
    ProductNotFoundError,
    LicenseNotFoundError,
    LicenseExpiredError,
    LicenseSuspendedError,
    LicenseRevokedError,
    DeviceLimitExceededError,
    DeviceNotFoundError,
    DatabaseException,
    LicenseServerException,
)
from app.constants import ExtensionErrorCode


router = APIRouter(
    prefix="/api/v1/extensions",
    tags=["Extensions"],
)


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    if request.client:
        return request.client.host
    return None



@router.post(
    "/activate",
    response_model=ExtensionActivationResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate License",
    description="Activate a license for an extension device. Requires product API key.",
)
async def activate_license(
    request: Request,
    payload: ExtensionActivateRequest,
    db: Session = Depends(get_db),
) -> ExtensionActivationResponse:
    """
    Activate a license for the first time on a device.
    
    Returns:
    - License key
    - Extension JWT token (24-hour expiry)
    - Activation timestamp
    - Device info
    """
    try:
        product = ExtensionService.validate_product_api_key(db, payload.product_api_key)
        license_obj = LicenseService.get_license_by_key(db, payload.license_key)

        if license_obj.product_id != product.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="License does not belong to this product",
            )

        # The customer email must match the license owner for activation.
        if not payload.customer_email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="customer_email is required for extension activation",
            )

        owner_email = (license_obj.customer.email or "").lower() if getattr(license_obj, "customer", None) else ""
        if owner_email != payload.customer_email.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customer email does not match license owner",
            )

        result = ExtensionService.activate_extension(
            db,
            license_key=payload.license_key,
            device_uuid=payload.device_uuid,
            browser=payload.browser,
            operating_system=payload.operating_system,
            extension_version=payload.extension_version,
            ip_address=_get_client_ip(request),
            device_fingerprint=getattr(payload, "device_fingerprint", None),
        )

        device_id = result.get("device_id")
        if device_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Extension activation completed without a device identifier.",
            )

        device = DeviceService.get_device(db, device_id)
        token = ExtensionJWTService.generate_token(
            license_id=license_obj.id,
            license_key=license_obj.license_key,
            product_id=product.id,
            customer_id=license_obj.customer_id,
            device_uuid=payload.device_uuid,
            device_token_version=device.token_version,
        )

        ActivityLogService.log_activity(
            db,
            license_id=license_obj.id,
            action=ActivityLogService.ACTION_LICENSE_ACTIVATED,
            ip_address=_get_client_ip(request),
            browser=payload.browser,
            additional_data={
                "device_uuid": payload.device_uuid,
                "product_id": product.id,
            },
        )

        return ExtensionActivationResponse(
            success=True,
            license_key=license_obj.license_key,
            extension_token=token,
            expires_in_seconds=86400,  # 24 hours
            activated_at=result.get("activated_at", license_obj.activated_at),
            expires_at=result["expiration"],
            device_id=device_id,
            max_devices=result["devices_allowed"],
        )
    
    except LicenseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )
    
    except InvalidProductKeyError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid product API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except DeviceLimitExceededError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device limit reached for this license",
        )
    
    except LicenseServerException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/verify",
    response_model=ExtensionVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify License",
    description="Verify a license and device status. Requires product API key.",
)
async def verify_license(
    request: Request,
    payload: ExtensionVerifyRequest,
    db: Session = Depends(get_db),
) -> ExtensionVerifyResponse:
    """
    Verify a license is still active and device is registered.
    
    Returns:
    - License status
    - Device registration status
    - Days remaining
    - Device count
    """
    try:
        product = ExtensionService.validate_product_api_key(db, payload.product_api_key)
        license_obj = LicenseService.get_license_by_key(db, payload.license_key)

        if license_obj.product_id != product.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="License does not belong to this product",
            )

        result = ExtensionService.verify_extension(
            db,
            license_key=payload.license_key,
            device_uuid=payload.device_uuid,
            browser=payload.browser,
            ip_address=_get_client_ip(request),
            extension_token=getattr(payload, "extension_token", None),
        )

        return ExtensionVerifyResponse(
            success=True,
            license_key=result["license_key"],
            status=result["license_status"],
            activated=result["license_status"] == "active",
            expires_at=result["expires_at"],
            days_remaining=max(0, remaining_days(result["expires_at"])),
            max_devices=result["devices_allowed"],
            activated_devices=result["devices_used"],
            current_device_registered=True,
        )

    except LicenseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )
    
    except LicenseServerException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/extend",
    response_model=ExtensionExtendResponse,
    status_code=status.HTTP_200_OK,
    summary="Extend License",
    description="Extend a license expiry date. Requires product API key.",
)
async def extend_license(
    request: Request,
    payload: ExtensionExtendRequest,
    db: Session = Depends(get_db),
) -> ExtensionExtendResponse:
    """
    Extend the expiry date of a license.
    
    Returns:
    - New expiry date
    - Days added
    """
    try:
        product = ExtensionService.validate_product_api_key(db, payload.product_api_key)
        license_obj = LicenseService.get_license_by_key(db, payload.license_key)

        if license_obj.product_id != product.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="License does not belong to this product",
            )

        plan = LicenseService.validate_plan(db, payload.plan_id)
        days_to_add = plan.duration_days

        license_obj = LicenseService.extend_license(
            db,
            license_key=payload.license_key,
            plan_id=payload.plan_id,
        )

        ActivityLogService.log_activity(
            db,
            license_id=license_obj.id,
            action=ActivityLogService.ACTION_LICENSE_EXTENDED,
            ip_address=_get_client_ip(request),
            additional_data={
                "plan_id": payload.plan_id,
                "new_expiry": license_obj.expires_at.isoformat(),
                "days_added": days_to_add,
            },
        )

        return ExtensionExtendResponse(
            success=True,
            license_key=license_obj.license_key,
            new_expiry_date=license_obj.expires_at,
            days_added=days_to_add,
            expires_at=license_obj.expires_at,
        )
    
    except LicenseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )
    
    except LicenseServerException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/heartbeat",
    response_model=ExtensionHeartbeatResponse,
    status_code=status.HTTP_200_OK,
    summary="Heartbeat",
    description="Send a heartbeat for device activity tracking. Requires product API key.",
)
async def heartbeat(
    request: Request,
    payload: ExtensionHeartbeatRequest,
    db: Session = Depends(get_db),
) -> ExtensionHeartbeatResponse:
    """
    Update device last_seen timestamp and log activity.
    
    Returns:
    - License status
    - Days remaining
    """
    try:
        product = ExtensionService.validate_product_api_key(db, payload.product_api_key)
        license_obj = LicenseService.get_license_by_key(db, payload.license_key)

        if license_obj.product_id != product.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="License does not belong to this product",
            )

        result = ExtensionService.heartbeat(
            db,
            license_key=payload.license_key,
            device_uuid=payload.device_uuid,
            browser=payload.browser,
            operating_system=payload.operating_system,
            extension_version=payload.extension_version,
            ip_address=_get_client_ip(request),
            extension_token=getattr(payload, "extension_token", None),
        )

        ActivityLogService.log_activity(
            db,
            license_id=license_obj.id,
            action=ActivityLogService.ACTION_DEVICE_HEARTBEAT,
            ip_address=_get_client_ip(request),
            additional_data={
                "device_uuid": payload.device_uuid,
            },
        )

        return ExtensionHeartbeatResponse(
            success=result["success"],
            license_status=result["license_status"],
            days_remaining=max(0, remaining_days(license_obj.expires_at)),
            last_checked_at=result["last_verified"],
        )
    
    except LicenseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )
    
    except LicenseServerException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/deactivate",
    response_model=ExtensionDeactivateResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate License",
    description="Deactivate a device session and remove the device from the license.",
)
async def deactivate_license(
    request: Request,
    payload: ExtensionDeactivateRequest,
    db: Session = Depends(get_db),
) -> ExtensionDeactivateResponse:
    """
    Deactivate a device and log the device reset activity.
    """
    try:
        product = ExtensionService.validate_product_api_key(db, payload.product_api_key)
        license_obj = LicenseService.get_license_by_key(db, payload.license_key)

        if license_obj.product_id != product.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="License does not belong to this product",
            )

        result = ExtensionService.deactivate_extension(
            db,
            license_key=payload.license_key,
            device_uuid=payload.device_uuid,
        )

        ActivityLogService.log_activity(
            db,
            license_id=license_obj.id,
            action=ActivityLogService.ACTION_DEVICE_RESET,
            ip_address=_get_client_ip(request),
            additional_data={
                "device_uuid": payload.device_uuid,
            },
        )

        remaining_devices = db.query(Device).filter(
            Device.license_id == license_obj.id
        ).count()

        return ExtensionDeactivateResponse(
            success=result["success"],
            message="Device deactivated successfully.",
            license_key=license_obj.license_key,
            device_uuid=payload.device_uuid,
            device_removed=result.get("removed", False),
            remaining_devices=remaining_devices,
            license_status=license_obj.status,
        )

    except LicenseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License not found",
        )

    except LicenseServerException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/version",
    summary="Get Extension Version",
    description="Retrieve the latest extension version.",
)
async def get_extension_version(
    db: Session = Depends(get_db),
    product_api_key: Optional[str] = None,
):
    version = "1.0.0"
    if product_api_key:
        product = db.query(Product).filter(Product.api_key == product_api_key).first()
        if product:
            version = product.version
    return {
        "success": True,
        "version": version,
        "latest_version": version,
        "min_version": "1.0.0",
    }

