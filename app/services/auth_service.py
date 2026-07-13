"""
Authentication Service for LOUD Platform Licensing System.

Handles admin authentication, password changes, and role authorization.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ROLE_ADMIN, ROLE_OWNER, ROLE_SUPPORT
from app.exceptions import (
    AdminUserNotFoundError,
    DatabaseError,
    InvalidCredentialsError,
    InvalidTokenError,
    UnauthorizedAdminError,
)
from app.models import AdminUser
from app.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)


class AuthService:
    """Service for authentication operations."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        return hash_password(password)

    @staticmethod
    def verify_password(
        plain_password: str,
        hashed_password: str,
    ) -> bool:
        """Verify a password."""
        return verify_password(
            plain_password,
            hashed_password,
        )

    @staticmethod
    def create_access_token(data: dict) -> str:
        """Create a JWT access token."""
        return create_access_token(data)

    @staticmethod
    def verify_token(token: str) -> dict:
        """Verify a JWT token."""
        return verify_token(token)

    @staticmethod
    def get_current_admin(token: str) -> dict:
        """Decode the JWT payload and ensure it contains admin identity."""
        payload = verify_token(token)

        if "sub" not in payload:
            raise InvalidTokenError("Token does not contain admin information.")

        return payload

    @staticmethod
    def admin_login(
        db: Session,
        username: str,
        password: str,
    ) -> dict:
        """Authenticate an admin user."""
        normalized_username = username.strip() if username else ""

        if not normalized_username:
            raise InvalidCredentialsError("Invalid username or password.")

        admin = (
            db.query(AdminUser)
            .filter(AdminUser.username == normalized_username)
            .first()
        )

        if admin is None:
            raise AdminUserNotFoundError(
                f"Admin '{normalized_username}' not found."
            )

        if not verify_password(password, admin.password_hash):
            raise InvalidCredentialsError("Invalid username or password.")

        access_token = create_access_token(
            {
                "sub": admin.username,
                "admin_id": admin.id,
                "role": admin.role,
            }
        )

        return {
            "admin_id": admin.id,
            "username": admin.username,
            "role": admin.role,
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    @staticmethod
    def change_password(
        db: Session,
        admin_id: int,
        old_password: str,
        new_password: str,
    ) -> bool:
        """Change an admin password."""
        admin = (
            db.query(AdminUser)
            .filter(AdminUser.id == admin_id)
            .first()
        )

        if admin is None:
            raise AdminUserNotFoundError(
                f"Admin user with ID {admin_id} not found."
            )

        if not verify_password(old_password, admin.password_hash):
            raise InvalidCredentialsError("Current password is incorrect.")

        if not new_password or len(new_password) < 8:
            raise InvalidCredentialsError(
                "Password must contain at least 8 characters."
            )

        try:
            admin.password_hash = hash_password(new_password)
            db.commit()
            return True
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to change password: {exc}") from exc

    @staticmethod
    def check_admin_role(
        token_payload: dict,
        required_role: str,
    ) -> bool:
        """Validate role hierarchy."""
        hierarchy = {
            ROLE_SUPPORT: 1,
            ROLE_ADMIN: 2,
            ROLE_OWNER: 3,
        }

        current_role = token_payload.get("role", ROLE_SUPPORT)
        current_level = hierarchy.get(current_role, 0)
        required_level = hierarchy.get(required_role, 0)

        if current_level < required_level:
            raise UnauthorizedAdminError(
                f"Role '{current_role}' does not have permission."
            )

        return True