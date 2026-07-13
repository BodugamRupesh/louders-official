"""
Licenses Router for LOUD Platform Licensing System.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin, require_admin_or_owner, require_owner
from app.models import ActivityLog, AdminUser, License
from app.schemas import (
    ActivityLogResponse,
    LicenseActivate,
    LicenseCreate,
    LicenseExtend,
    LicenseReactivate,
    LicenseResetDevice,
    LicenseRevoke,
    LicenseResponse,
    LicenseVerify,
    SuccessResponse,
)
from app.services.license_service import LicenseService
from app.utils.responses import success_response


router = APIRouter(
    prefix="/api/v1/licenses",
    tags=["Licenses"],
)


def _serialize_license(license_obj: License) -> dict:
    return LicenseResponse.model_validate(
        license_obj,
        from_attributes=True,
    ).model_dump()


def _serialize_activity_log(activity: ActivityLog) -> dict:
    return ActivityLogResponse.model_validate(
        activity,
        from_attributes=True,
    ).model_dump()


@router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Create License",
    description="Create a new license. Admin or Owner only.",
)
async def create_license(
    create_data: LicenseCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    license = LicenseService.create_license(
        db,
        product_id=create_data.product_id,
        customer_id=create_data.customer_id,
        plan_id=create_data.plan_id,
    )
    return success_response(
        "License created successfully.",
        data={"license": _serialize_license(license)},
    )


@router.post(
    "/reactivate",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate License",
    description="Reactivate a suspended or expired license. Admin or Owner only.",
)
async def reactivate_license(
    reactivate_data: LicenseReactivate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    license = LicenseService.reactivate_license(
        db,
        license_key=reactivate_data.license_key,
    )
    return success_response(
        "License reactivated successfully.",
        data={"license": _serialize_license(license)},
    )


@router.get(
    "/search",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Licenses",
    description="Search licenses by query, customer, product, or status. Authenticated admins only.",
)
async def search_licenses(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    q: str | None = Query(None, min_length=1, description="Search query"),
    customer_id: int | None = Query(None, ge=1, description="Filter by customer ID"),
    product_id: int | None = Query(None, ge=1, description="Filter by product ID"),
    status: str | None = Query(None, description="Filter by license status"),
) -> SuccessResponse:
    if q is not None:
        q = q.strip()
        if not q:
            q = None

    licenses = LicenseService.search_licenses(
        db,
        query_str=q,
        customer_id=customer_id,
        product_id=product_id,
        status=status,
    )
    return success_response(
        "Licenses searched successfully.",
        data={
            "licenses": [_serialize_license(license_obj) for license_obj in licenses],
            "count": len(licenses),
        },
    )


@router.post(
    "/activate",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate License",
    description="Activate a license and register the first device. Authenticated admins only.",
)
async def activate_license(
    activation_data: LicenseActivate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    result = LicenseService.activate_license(
        db,
        license_key=activation_data.license_key,
        device_uuid=activation_data.device_uuid,
        browser=activation_data.browser,
        operating_system=activation_data.operating_system,
        extension_version=activation_data.extension_version,
    )
    return success_response(
        "License activated successfully.",
        data={"activation": result},
    )


@router.post(
    "/verify",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify License",
    description="Verify a license and device. Authenticated admins only.",
)
async def verify_license(
    verification_data: LicenseVerify,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    result = LicenseService.verify_license(
        db,
        license_key=verification_data.license_key,
        device_uuid=verification_data.device_uuid,
        browser=verification_data.browser,
    )
    return success_response(
        "License verified successfully.",
        data={"verification": result},
    )


@router.post(
    "/extend",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Extend License",
    description="Extend an existing license. Admin or Owner only.",
)
async def extend_license(
    extend_data: LicenseExtend,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    license = LicenseService.extend_license(
        db,
        license_key=extend_data.license_key,
        plan_id=extend_data.plan_id,
    )
    return success_response(
        "License extended successfully.",
        data={"license": _serialize_license(license)},
    )


@router.post(
    "/suspend",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Suspend License",
    description="Temporarily suspend a license. Admin or Owner only.",
)
async def suspend_license(
    revoke_data: LicenseRevoke,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    license = LicenseService.suspend_license(
        db,
        license_key=revoke_data.license_key,
        reason=revoke_data.reason,
    )
    return success_response(
        "License suspended successfully.",
        data={"license": _serialize_license(license)},
    )


@router.post(
    "/revoke",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke License",
    description="Permanently revoke a license. Admin or Owner only.",
)
async def revoke_license(
    revoke_data: LicenseRevoke,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    license = LicenseService.revoke_license(
        db,
        license_key=revoke_data.license_key,
        reason=revoke_data.reason,
    )
    return success_response(
        "License revoked successfully.",
        data={"license": _serialize_license(license)},
    )



@router.post(
    "/delete-revoked",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Revoked License",
    description="Delete a license that has been revoked. Admin or Owner.",
)
async def delete_revoked_license(
    revoke_data: LicenseRevoke,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    result = LicenseService.delete_revoked_license(
        db,
        license_key=revoke_data.license_key,
    )
    return success_response(
        "Revoked license deleted successfully.",
        data={"deleted": result},
    )


@router.post(
    "/reset-device",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset Device",
    description="Reset the registered device for a license. Admin or Owner only.",
)
async def reset_device(
    reset_data: LicenseResetDevice,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    result = LicenseService.reset_device(
        db,
        license_key=reset_data.license_key,
    )
    return success_response(
        "Device reset successfully.",
        data={"reset": result},
    )


@router.delete(
    "/{license_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete License",
    description="Delete a license. Owner only.",
)
async def delete_license(
    license_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    LicenseService.delete_license(db, license_id)
    return success_response(
        "License deleted successfully.",
        data={"license_id": license_id},
    )


@router.get(
    "/{license_id}/activity",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get License Activity",
    description="Retrieve the activity history for a license. Authenticated admins only.",
)
async def get_license_activity(
    license_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    activity = LicenseService.get_license_activity(db, license_id)
    return success_response(
        "License activity retrieved successfully.",
        data={
            "activity": [_serialize_activity_log(log) for log in activity],
            "count": len(activity),
        },
    )


@router.get(
    "/stats",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get License Stats",
    description="Retrieve overall license statistics. Authenticated admins only.",
)
async def get_license_stats(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    stats = LicenseService.get_license_stats(db)
    return success_response(
        "License statistics retrieved successfully.",
        data={"stats": stats},
    )
