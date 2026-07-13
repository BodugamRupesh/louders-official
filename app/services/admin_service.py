"""
Admin Service for LOUD Platform Licensing System.

Handles:
- Admin user creation, update, deletion
- Admin password management
- Admin role management
- Admin enable/disable
- JWT operations for admins
- Activity logging for admin actions
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.constants import (
    ROLE_OWNER,
    ROLE_ADMIN,
    ROLE_SUPPORT,
    ADMIN_ROLES,
)

from app.exceptions import (
    AdminUserNotFoundError,
    DuplicateAdminError,
    InvalidCredentialsError,
    InvalidDataError,
    DatabaseError,
    UnauthorizedAdminError,
)
from app.models import AdminUser
from app.services.auth_service import AuthService


class AdminService:
    """Service for handling admin user operations."""

    @staticmethod
    def create_admin(
        db: Session,
        username: str,
        password: str,
        role: str = "support"
    ) -> AdminUser:
        """
        Create a new admin user.
        
        Args:
            db: SQLAlchemy database session.
            username: Admin username (must be unique).
            password: Admin password (minimum 8 characters).
            role: Admin role ('owner', 'admin', or 'support').
            
        Returns:
            Created AdminUser model instance.
            
        Raises:
            InvalidDataError: If data is invalid.
            DuplicateAdminError: If username already exists.
            DatabaseError: If database operation fails.
        """
        if not username or not username.strip():
            raise InvalidDataError("Username cannot be empty")
        
        if len(username) < 3:
            raise InvalidDataError("Username must be at least 3 characters")
        
        if not password or len(password) < 8:
            raise InvalidDataError("Password must be at least 8 characters")
        
        valid_roles = ADMIN_ROLES
        if role not in valid_roles:
            raise InvalidDataError(f"Role must be one of: {', '.join(valid_roles)}")
        
        try:
            # Check if username already exists
            existing = db.query(AdminUser).filter(
                AdminUser.username == username
            ).first()
            
            if existing:
                raise DuplicateAdminError(f"Admin user '{username}' already exists")
            
            # Hash password
            password_hash = AuthService.hash_password(password)
            
            # Create admin
            admin = AdminUser(
                username=username.strip(),
                password_hash=password_hash,
                role=role
            )
            
            db.add(admin)
            db.commit()
            db.refresh(admin)
            
            return admin
            
        except (InvalidDataError, DuplicateAdminError):
            raise
        except IntegrityError:
            db.rollback()
            raise DuplicateAdminError(f"Admin user '{username}' already exists")
        except Exception as e:
            db.rollback()
            raise DatabaseError(f"Failed to create admin: {str(e)}")

    @staticmethod
    def get_admin(db: Session, admin_id: int) -> AdminUser:
        """
        Get admin by ID.
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            
        Returns:
            AdminUser model instance.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
        """
        admin = db.query(AdminUser).filter(
            AdminUser.id == admin_id
        ).first()
        
        if not admin:
            raise AdminUserNotFoundError(f"Admin user with ID {admin_id} not found")
        
        return admin

    @staticmethod
    def get_admin_by_username(db: Session, username: str) -> AdminUser:
        """
        Get admin by username.
        
        Args:
            db: SQLAlchemy database session.
            username: Admin username.
            
        Returns:
            AdminUser model instance.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
        """
        admin = db.query(AdminUser).filter(
            AdminUser.username == username
        ).first()
        
        if not admin:
            raise AdminUserNotFoundError(f"Admin user '{username}' not found")
        
        return admin

    @staticmethod
    def update_admin(
        db: Session,
        admin_id: int,
        username: str | None = None,
        role: str | None = None
    ) -> AdminUser:
        """
        Update admin information.
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            username: New username.
            role: New role.
            
        Returns:
            Updated AdminUser model instance.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
            DuplicateAdminError: If new username already taken.
            InvalidDataError: If data is invalid.
            DatabaseError: If database operation fails.
        """
        try:
            admin = AdminService.get_admin(db, admin_id)
            
            if username is not None:
                if len(username) < 3:
                    raise InvalidDataError("Username must be at least 3 characters")
                
                # Check if new username is taken by another admin
                existing = db.query(AdminUser).filter(
                    AdminUser.username == username,
                    AdminUser.id != admin_id
                ).first()
                
                if existing:
                    raise DuplicateAdminError(f"Admin user '{username}' already exists")
                
                admin.username = username.strip()
            
            if role is not None:
                valid_roles = ("owner", "admin", "support")
                if role not in valid_roles:
                    raise InvalidDataError(
                        f"Role must be one of: {', '.join(valid_roles)}"
                    )
                
                # Prevent demoting the last owner
                if admin.role == ROLE_OWNER and role != ROLE_OWNER:
                    owner_count = (
                        db.query(AdminUser)
                        .filter(AdminUser.role == ROLE_OWNER)
                        .count()
                    )

                    if owner_count == 1:
                        raise InvalidDataError(
                            "Cannot demote the last owner."
                        )

                admin.role = role
            
            db.commit()
            db.refresh(admin)
            
            return admin
            
        except (AdminUserNotFoundError, DuplicateAdminError, InvalidDataError):
            raise
        except Exception as e:
            db.rollback()
            raise DatabaseError(f"Failed to update admin: {str(e)}")

    @staticmethod
    def delete_admin(db: Session, admin_id: int) -> bool:
        """
        Delete an admin user.
        
        Note: Cannot delete if only owner exists (safety measure).
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            
        Returns:
            True if admin deleted successfully.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
            OperationNotAllowedError: If cannot delete (e.g., only owner).
            DatabaseError: If database operation fails.
        """
        try:
            admin = AdminService.get_admin(db, admin_id)
            
            # Safety check: prevent deleting last owner
            if admin.role == ROLE_OWNER:
                other_owners = db.query(AdminUser).filter(
                    AdminUser.role == ROLE_OWNER,
                    AdminUser.id != admin_id
                ).count()
                
                if other_owners == 0:
                    raise InvalidDataError(
                        "Cannot delete the last owner admin user"
                    )
            
            db.delete(admin)
            db.commit()
            
            return True
            
        except (AdminUserNotFoundError, InvalidDataError):
            raise
        except Exception as e:
            db.rollback()
            raise DatabaseError(f"Failed to delete admin: {str(e)}")

    @staticmethod
    def change_password(
        db: Session,
        admin_id: int,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Change admin password.
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            old_password: Current password for verification.
            new_password: New password.
            
        Returns:
            True if password changed successfully.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
            InvalidCredentialsError: If old password is wrong.
            InvalidDataError: If new password is invalid.
            DatabaseError: If database operation fails.
        """
        try:
            admin = AdminService.get_admin(db, admin_id)
            
            # Verify old password
            if not AuthService.verify_password(old_password, admin.password_hash):
                raise InvalidCredentialsError("Current password is incorrect")
            
            # Validate new password
            if not new_password or len(new_password) < 8:
                raise InvalidDataError("New password must be at least 8 characters")
            
            # Hash and update new password
            if AuthService.verify_password(
                new_password,
                admin.password_hash,
            ):
                raise InvalidDataError(
                    "New password must be different from the current password."
             )
            
            db.commit()
            
            return True
            
        except (AdminUserNotFoundError, InvalidCredentialsError, InvalidDataError):
            raise
        except Exception as e:
            db.rollback()
            raise DatabaseError(f"Failed to change password: {str(e)}")

    @staticmethod
    def reset_password(
        db: Session,
        admin_id: int,
        new_password: str
    ) -> bool:
        """
        Reset admin password (admin/owner only, no verification needed).
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            new_password: New password.
            
        Returns:
            True if password reset successfully.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
            InvalidDataError: If new password is invalid.
            DatabaseError: If database operation fails.
        """
        try:
            admin = AdminService.get_admin(db, admin_id)
            
            # Validate new password
            if not new_password or len(new_password) < 8:
                raise InvalidDataError("Password must be at least 8 characters")
            
            # Hash and set new password
            admin.password_hash = AuthService.hash_password(new_password)
            
            db.commit()
            
            return True
            
        except (AdminUserNotFoundError, InvalidDataError):
            raise
        except Exception as e:
            db.rollback()
            raise DatabaseError(f"Failed to reset password: {str(e)}")

    @staticmethod
    def list_admins(db: Session) -> list[AdminUser]:
        """
        List all admin users.
        
        Args:
            db: SQLAlchemy database session.
            
        Returns:
            List of AdminUser model instances.
        """
        return db.query(AdminUser).order_by(AdminUser.created_at.desc()).all()

    @staticmethod
    def search_admins(db: Session, query_str: str) -> list[AdminUser]:
        """
        Search admins by username.
        
        Args:
            db: SQLAlchemy database session.
            query_str: Search query string.
            
        Returns:
            List of matching AdminUser model instances.
        """
        return db.query(AdminUser).filter(
            AdminUser.username.ilike(f"%{query_str}%")
        ).order_by(AdminUser.created_at.desc()).all()

    @staticmethod
    def get_admin_count(db: Session) -> int:
        """
        Get total number of admin users.
        
        Args:
            db: SQLAlchemy database session.
            
        Returns:
            Number of admin users.
        """
        return db.query(AdminUser).count()

    @staticmethod
    def get_admin_by_role(db: Session, role: str) -> list[AdminUser]:
        """
        Get all admins with a specific role.
        
        Args:
            db: SQLAlchemy database session.
            role: Role to filter by ('owner', 'admin', 'support').
            
        Returns:
            List of AdminUser model instances.
        """
        return db.query(AdminUser).filter(
            AdminUser.role == role
        ).order_by(AdminUser.created_at.desc()).all()

    @staticmethod
    def get_admin_stats(db: Session) -> dict:
        """
        Get admin statistics.
        
        Args:
            db: SQLAlchemy database session.
            
        Returns:
            Dictionary with admin statistics.
        """
        total = db.query(AdminUser).count()
        owners = db.query(AdminUser).filter(AdminUser.role == "owner").count()
        admins = db.query(AdminUser).filter(AdminUser.role == "admin").count()
        support = db.query(AdminUser).filter(AdminUser.role == "support").count()
        
        return {
            "total": total,
            "owners": owners,
            "admins": admins,
            "support": support
        }

    @staticmethod
    def verify_admin_credentials(db: Session, username: str, password: str) -> AdminUser:
        """
        Verify admin credentials.
        
        Args:
            db: SQLAlchemy database session.
            username: Admin username.
            password: Admin password.
            
        Returns:
            AdminUser model instance if credentials are valid.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
            InvalidCredentialsError: If password is incorrect.
        """
        admin = AdminService.get_admin_by_username(db, username)
        
        if not AuthService.verify_password(password, admin.password_hash):
            raise InvalidCredentialsError("Invalid username or password")
        
        return admin

    @staticmethod
    def check_admin_has_role(
        db: Session,
        admin_id: int,
        required_role: str
    ) -> bool:
        """
        Check if admin has required role.
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            required_role: Required role ('owner', 'admin', 'support').
            
        Returns:
            True if admin has required role or higher.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
            UnauthorizedAdminError: If admin doesn't have required role.
        """
        admin = AdminService.get_admin(db, admin_id)
        
        # Role hierarchy: owner > admin > support
        role_hierarchy = {
            ROLE_OWNER: 3,
            ROLE_ADMIN: 2,
            ROLE_SUPPORT: 1,
        }
        required_level = role_hierarchy.get(required_role, 0)
        admin_level = role_hierarchy.get(admin.role, 0)
        
        if admin_level < required_level:
            raise UnauthorizedAdminError(
                f"Admin with role '{admin.role}' cannot access this resource"
            )
        
        return True

    @staticmethod
    def is_owner(db: Session, admin_id: int) -> bool:
        """
        Check if admin is an owner.
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            
        Returns:
            True if admin is owner, False otherwise.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
        """
        admin = AdminService.get_admin(db, admin_id)
        return admin.role == ROLE_OWNER

    @staticmethod
    def is_admin_or_owner(db: Session, admin_id: int) -> bool:
        """
        Check if admin is admin or owner.
        
        Args:
            db: SQLAlchemy database session.
            admin_id: Admin user ID.
            
        Returns:
            True if admin is admin or owner, False otherwise.
            
        Raises:
            AdminUserNotFoundError: If admin doesn't exist.
        """
        admin = AdminService.get_admin(db, admin_id)
        return admin.role in (
            ROLE_OWNER,
            ROLE_ADMIN,
            )      
