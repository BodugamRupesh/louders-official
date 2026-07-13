"""
Authentication Router for LOUD Platform Licensing System.

Endpoints:
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- POST /api/v1/auth/refresh
- GET /api/v1/auth/me
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import AdminUser
from app.schemas import (
    AdminLogin,
    AdminUserResponse,
    SuccessResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin Login",
    description="Authenticate an admin and return a JWT access token.",
    responses={
        401: {"description": "Invalid username or password"},
        422: {"description": "Validation error"},
    },
)
async def login(
    credentials: AdminLogin,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate an admin and return a JWT access token."""

    result = AuthService.admin_login(
        db=db,
        username=credentials.username,
        password=credentials.password,
    )

    return TokenResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
        expires_in=result["expires_in"],
    )


@router.post(
    "/logout",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin Logout",
    description="Logout the current admin session.",
)
async def logout(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> SuccessResponse:
    """
    Logout the currently authenticated admin.

    JWT logout is client-side only.
    The client should discard the token after logout.
    """

    return SuccessResponse(
        success=True,
        message="Logged out successfully.",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Token",
    description="Generate a fresh JWT access token for the authenticated admin.",
)
async def refresh_token(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> TokenResponse:
    """Refresh the access token."""

    access_token = AuthService.create_access_token(
        {
            "sub": current_admin.username,
            "admin_id": current_admin.id,
            "role": current_admin.role,
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=AdminUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Admin",
    description="Retrieve information about the authenticated admin.",
)
async def get_current_admin_info(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminUserResponse:
    """Return the authenticated admin."""

    return AdminUserResponse(
        id=current_admin.id,
        username=current_admin.username,
        role=current_admin.role,
        created_at=current_admin.created_at,
    )