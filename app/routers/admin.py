"""Admin router for LOUD Platform Licensing System."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_admin,
    require_admin_or_owner,
    require_owner,
)
from app.models import AdminUser
from app.schemas import (
    AdminUpdateRequest,
    AdminUserCreate,
    AdminUserResponse,
    ChangePasswordRequest,
    ResetPasswordRequest,
    SuccessResponse,
)
from app.services.admin_service import AdminService
from app.utils.responses import success_response


router = APIRouter(
    prefix="/api/v1/admins",
    tags=["Admins"],
)


def _serialize_admin(admin: AdminUser) -> dict:
    return AdminUserResponse.model_validate(
        admin,
        from_attributes=True,
    ).model_dump()


@router.get(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="List Admins",
    description="List all admin users. Authenticated admins only.",
)
async def list_admins(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    admins = AdminService.list_admins(db)
    return success_response(
        "Admins retrieved successfully.",
        data={
            "admins": [_serialize_admin(admin) for admin in admins],
            "count": len(admins),
        },
    )


@router.get(
    "/search",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Admins",
    description="Search admin users by username. Authenticated admins only.",
)
async def search_admins(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    query: str | None = Query(None, description="Search query"),
) -> SuccessResponse:
    if query and query.strip():
        admins = AdminService.search_admins(db, query.strip())
    else:
        admins = AdminService.list_admins(db)
    return success_response(
        "Admins search completed successfully.",
        data={
            "admins": [_serialize_admin(admin) for admin in admins],
            "count": len(admins),
        },
    )


@router.get(
    "/stats",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Admin Stats",
    description="Get admin statistics. Authenticated admins only.",
)
async def get_admin_stats(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    total_admins = AdminService.get_admin_count(db)
    return success_response(
        "Admin statistics retrieved successfully.",
        data={"stats": {"total_admins": total_admins}},
    )


@router.get(
    "/{admin_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Admin",
    description="Get a specific admin user by ID. Authenticated admins only.",
)
async def get_admin(
    admin_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    admin = AdminService.get_admin(db, admin_id)
    return success_response(
        "Admin retrieved successfully.",
        data={"admin": _serialize_admin(admin)},
    )


@router.post(
    "",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Admin",
    description="Create a new admin user. Owner only.",
)
async def create_admin(
    admin_data: AdminUserCreate,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    admin = AdminService.create_admin(
        db,
        username=admin_data.username,
        password=admin_data.password,
        role=admin_data.role,
    )
    return success_response(
        "Admin created successfully.",
        data={"admin": _serialize_admin(admin)},
    )


@router.put(
    "/{admin_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Admin",
    description="Update an admin user's username or role. Admin or Owner only.",
)
async def update_admin(
    admin_id: int,
    admin_data: AdminUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    admin = AdminService.update_admin(
        db,
        admin_id=admin_id,
        username=admin_data.username,
        role=admin_data.role,
    )
    return success_response(
        "Admin updated successfully.",
        data={"admin": _serialize_admin(admin)},
    )


@router.delete(
    "/{admin_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Admin",
    description="Delete an admin user. Owner only.",
)
async def delete_admin(
    admin_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    AdminService.delete_admin(db, admin_id)
    return success_response(
        "Admin deleted successfully.",
        data={
            "admin_id": admin_id,
            "deleted": True,
        }
    )


@router.post(
    "/change-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Change Password",
    description="Change the current admin's password. Admin or Owner only.",
)
async def change_password(
    password_data: ChangePasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_admin_or_owner)],
) -> SuccessResponse:
    AdminService.change_password(
        db,
        admin_id=current_admin.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    return success_response(
        "Password changed successfully.",
        data={"changed": True},
    )


@router.post(
    "/reset-password",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset Password",
    description="Reset another admin user's password. Owner only.",
)
async def reset_password(
    password_data: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[AdminUser, Depends(require_owner)],
) -> SuccessResponse:
    AdminService.reset_password(
        db,
        admin_id=password_data.admin_id,
        new_password=password_data.new_password,
    )
    return success_response(
        "Password reset successfully.",
        data={"reset": True},
    )


alias_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin Alias"],
)
alias_router.add_api_route("/stats", get_admin_stats, methods=["GET"], response_model=SuccessResponse)
alias_router.add_api_route("", list_admins, methods=["GET"], response_model=SuccessResponse)
alias_router.add_api_route("/search", search_admins, methods=["GET"], response_model=SuccessResponse)
alias_router.add_api_route("/change-password", change_password, methods=["POST"], response_model=SuccessResponse)
alias_router.add_api_route("/reset-password", reset_password, methods=["POST"], response_model=SuccessResponse)


