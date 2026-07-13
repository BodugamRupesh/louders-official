"""
Dependency Injection for LOUD Platform Licensing System.

Provides:
- JWT token verification
- Current admin user resolution
- Role-based access control
- Database session management
- Product API key validation
"""

from typing import Annotated, Callable, Optional

from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import (
    AdminUserNotFoundError,
    InvalidTokenError,
)
from app.models import AdminUser, Product
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService

security = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> None:
    """Raise a standardized 401 Unauthorized response."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str) -> None:
    """Raise a standardized 403 Forbidden response."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


async def verify_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security),
    ],
) -> dict:
    """
    Verify a JWT token from the Authorization header.
    """

    if credentials is None:
        _unauthorized("Missing authorization header")

    token = credentials.credentials

    try:
        return AuthService.verify_token(token)
    except InvalidTokenError as exc:
        _unauthorized(str(exc))


async def get_current_admin(
    db: Annotated[Session, Depends(get_db)],
    token_payload: Annotated[dict, Depends(verify_token)],
) -> AdminUser:
    """
    Return the authenticated admin from the verified JWT payload.
    """
    admin_id = token_payload.get("admin_id")

    if admin_id is None:
        _unauthorized("Invalid token: missing admin_id")

    try:
        return AdminService.get_admin(db, admin_id)
    except AdminUserNotFoundError:
        _unauthorized("Admin user not found")


def require_role(*allowed_roles: str) -> Callable:
    """
    Create a dependency requiring one of the specified roles.
    """

    async def check_role(
        current_admin: Annotated[AdminUser, Depends(get_current_admin)],
    ) -> AdminUser:
        if current_admin.role not in allowed_roles:
            _forbidden(
                f"Admin with role '{current_admin.role}' cannot access this resource"
            )

        return current_admin

    return check_role


def require_owner(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminUser:
    """
    Dependency requiring the owner role.
    """
    if current_admin.role != "owner":
        _forbidden("Only owner can access this resource")

    return current_admin


def require_admin_or_owner(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminUser:
    """
    Dependency requiring owner or admin role.
    """
    if current_admin.role not in ("owner", "admin"):
        _forbidden("Admin or owner role required")

    return current_admin


async def validate_product_api_key(
    db: Session = Depends(get_db),
    api_key: Optional[str] = Header(None),
    api_key_query: Optional[str] = Query(None, alias="product_api_key"),
) -> Product:
    """
    Validate product API key from header or query parameter.
    
    Args:
        db: Database session
        api_key: Product API key from X-Api-Key header
        api_key_query: Product API key from query parameter
    
    Returns:
        Product object if API key is valid
    
    Raises:
        HTTPException: 401 if authentication fails, 403 if product inactive
    """
    
    # Priority: header > query parameter
    key = api_key or api_key_query
    
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing product API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate against database
    product = db.query(Product).filter(Product.api_key == key).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid product API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if product.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Product is not active",
        )
    
    return product