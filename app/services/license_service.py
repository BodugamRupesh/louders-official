"""
License Service for LOUD Platform Licensing System.

The core service handling all license operations:
- License key generation and validation
- License lifecycle management (create, activate, verify, extend, revoke, suspend)
- Device management and limit enforcement
- Product API key validation
- Plan validation and expiry checking
- Comprehensive activity logging
- Transaction management with proper error handling
"""

import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.utils.datetime_utils import get_current_time, remaining_days
from sqlalchemy.orm import Session
from app.constants import (
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_SUSPENDED,
    LICENSE_STATUS_REVOKED,
    LICENSE_STATUS_EXPIRED,
)

from app.exceptions import (
    LicenseNotFoundError,
    LicenseExpiredError,
    LicenseRevokedError,
    LicenseSuspendedError,
    DeviceDisabledError,
    DeviceLimitExceededError,
    InvalidProductKeyError,
    ProductNotFoundError,
    CustomerNotFoundError,
    PlanNotFoundError,
    DeviceNotFoundError,
    InvalidLicenseKeyFormatError,
    OperationNotAllowedError,
    InvalidDataError,
    DatabaseError,
)
from app.models import License, Device, ActivityLog, Product, Plan, Customer
from app.services.device_service import DeviceService


class LicenseService:
    """Service for handling all license operations."""

    # License key format constants
    LICENSE_KEY_PREFIX = "LP"
    LICENSE_KEY_CHARS = string.ascii_uppercase + string.digits
    LICENSE_KEY_SEGMENT_LENGTH = 4

    @staticmethod
    def generate_license_key() -> str:
        """
        Generate a professional license key.
        
        Format: LP-YY-XXXX-XXXX-XXXX
        Example: LP-26-8QX2-KM7P-H9TW
        
        Returns:
            Generated license key string.
        """
        # Generate year (current year last 2 digits)
        year_digits = get_current_time().strftime("%y")
        
        # Generate 3 segments of random alphanumeric
        segments = [year_digits]
        
        for _ in range(3):
            segment = ''.join(
                secrets.choice(LicenseService.LICENSE_KEY_CHARS)
                for _ in range(LicenseService.LICENSE_KEY_SEGMENT_LENGTH)
            )
            segments.append(segment)
        
        return f"{LicenseService.LICENSE_KEY_PREFIX}-{'-'.join(segments)}"

    @staticmethod
    def validate_license_key_format(license_key: str) -> bool:
        """
        Validate license key format.
        
        Args:
            license_key: License key to validate.
            
        Returns:
            True if format is valid.
            
        Raises:
            InvalidLicenseKeyFormatError: If format is invalid.
        """
        if not license_key or not isinstance(license_key, str):
            raise InvalidLicenseKeyFormatError("License key must be a non-empty string")
        
        parts = license_key.split('-')
        
        if len(parts) != 5:
            raise InvalidLicenseKeyFormatError(
                f"License key must have 5 segments separated by hyphens, got {len(parts)}"
            )
        
        if parts[0] != LicenseService.LICENSE_KEY_PREFIX:
            raise InvalidLicenseKeyFormatError(
                f"License key must start with '{LicenseService.LICENSE_KEY_PREFIX}'"
            )
        
        return True

    @staticmethod
    def validate_product_api_key(db: Session, api_key: str) -> Product:
        """
        Validate and retrieve product by API key.
        
        Args:
            db: SQLAlchemy database session.
            api_key: Product API key.
            
        Returns:
            Product model instance.
            
        Raises:
            InvalidProductKeyError: If API key is invalid.
            ProductNotFoundError: If product doesn't exist.
        """
        if not api_key:
            raise InvalidProductKeyError("Product API key is required")
        
        product = db.query(Product).filter(
            Product.api_key == api_key
        ).first()
        
        if product is None:
            raise InvalidProductKeyError(f"Invalid product API key: {api_key}")
        
        if product.status != LICENSE_STATUS_ACTIVE:
            raise InvalidProductKeyError(
                f"Product is not active (status: {product.status})"
            )
        
        return product

    @staticmethod
    def validate_plan(db: Session, plan_id: int) -> Plan:
        """
        Validate and retrieve plan by ID.
        
        Args:
            db: SQLAlchemy database session.
            plan_id: Plan ID.
            
        Returns:
            Plan model instance.
            
        Raises:
            PlanNotFoundError: If plan doesn't exist.
        """
        plan = db.query(Plan).filter(Plan.id == plan_id).first()
        
        if plan is None:
            raise PlanNotFoundError(f"Plan with ID {plan_id} not found")
        
        if plan.status != LICENSE_STATUS_ACTIVE:
            raise InvalidDataError(f"Plan is not active (status: {plan.status})")
        
        return plan

    @staticmethod
    def create_license(
        db: Session,
        product_id: int,
        customer_id: int,
        plan_id: int,
        api_key: str | None = None
    ) -> License:
        """
        Create a new license.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Product ID.
            customer_id: Customer ID.
            plan_id: Plan ID.
            api_key: Optional product API key for validation.
            
        Returns:
            Created License model instance.
            
        Raises:
            ProductNotFoundError: If product doesn't exist.
            CustomerNotFoundError: If customer doesn't exist.
            PlanNotFoundError: If plan doesn't exist.
            InvalidProductKeyError: If API key is invalid.
            DatabaseError: If database operation fails.
        """
        try:
            # Validate product
            product = db.query(Product).filter(
                Product.id == product_id
            ).first()
            
            if not product:
                raise ProductNotFoundError(f"Product with ID {product_id} not found")
            
            # Validate API key if provided
            if api_key:
                LicenseService.validate_product_api_key(db, api_key)
            
            # Validate customer
            customer = db.query(Customer).filter(
                Customer.id == customer_id
            ).first()
            
            if customer is None:
                raise CustomerNotFoundError(f"Customer with ID {customer_id} not found")
            
            # Validate and get plan
            plan = LicenseService.validate_plan(db, plan_id)
            
            # Generate unique license key
            license_key = LicenseService.generate_license_key()
            
            # Check for uniqueness
            while db.query(License).filter(
                License.license_key == license_key
            ).first():
                license_key = LicenseService.generate_license_key()
            
            # Calculate expiry date
            expires_at = get_current_time() + timedelta(days=plan.duration_days)
            
            # Create license
            license_obj = License(
                product_id=product_id,
                customer_id=customer_id,
                plan_id=plan_id,
                license_key=license_key,
                status=LICENSE_STATUS_ACTIVE,
                expires_at=expires_at
            )
            
            db.add(license_obj)
            db.commit()
            db.refresh(license_obj)
            
            # Log activity
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action="license_created",
                ip_address=None,
                browser=None
            )
            
            return license_obj
            
        except (ProductNotFoundError, CustomerNotFoundError, PlanNotFoundError, 
                InvalidProductKeyError):
            raise
        except IntegrityError as exc:
            db.rollback()
            raise DatabaseError("Failed to create license: duplicate license key") from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to create license: {exc}") from exc

    @staticmethod
    def get_license(db: Session, license_id: int) -> License:
        """
        Get license by ID.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            
        Returns:
            License model instance.
            
        Raises:
            LicenseNotFoundError: If license doesn't exist.
        """
        license_obj = db.query(License).filter(
            License.id == license_id
        ).first()
        
        if license_obj is None:
            raise LicenseNotFoundError(f"License with ID {license_id} not found")
        
        return license_obj

    @staticmethod
    def delete_license(db: Session, license_id: int) -> bool:
        """
        Delete a license record by ID.

        Args:
            db: SQLAlchemy database session.
            license_id: License ID.

        Returns:
            True if deleted successfully.
        """
        try:
            license_obj = LicenseService.get_license(db, license_id)
            db.delete(license_obj)
            db.commit()
            return True
        except LicenseNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to delete license: {exc}") from exc

    @staticmethod
    def delete_revoked_license(db: Session, license_key: str) -> bool:
        """
        Delete a license that is already revoked.

        Args:
            db: SQLAlchemy database session.
            license_key: License key string.

        Returns:
            True if deleted successfully.

        Raises:
            LicenseNotFoundError: If license not found.
            OperationNotAllowedError: If license is not revoked.
            DatabaseError: If DB operation fails.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)

            if license_obj.status != LICENSE_STATUS_REVOKED:
                raise OperationNotAllowedError(
                    f"License '{license_key}' is not revoked and cannot be deleted via this endpoint"
                )

            # perform delete
            db.delete(license_obj)
            db.commit()
            return True
        except LicenseNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to delete revoked license: {exc}") from exc

    @staticmethod
    def get_license_by_key(db: Session, license_key: str) -> License:
        """
        Get license by license key.
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key string.
            
        Returns:
            License model instance.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
        """
        LicenseService.validate_license_key_format(license_key)
        
        license_obj = db.query(License).filter(
            License.license_key == license_key
        ).first()
        
        if not license_obj:
            raise LicenseNotFoundError(f"License '{license_key}' not found")
        
        return license_obj

    @staticmethod
    def activate_license(
        db: Session,
        license_key: str,
        device_uuid: str,
        browser: str,
        operating_system: str | None = None,
        extension_version: str | None = None,
        ip_address: str | None = None
        , device_fingerprint: str | None = None
    ) -> dict:
        """
        Activate a license by registering first device.
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key.
            device_uuid: Device UUID.
            browser: Browser name.
            operating_system: Optional OS.
            extension_version: Optional extension version.
            ip_address: Optional IP address for logging.
            
        Returns:
            Dictionary with license and device info.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
            LicenseExpiredError: If license is expired.
            LicenseRevokedError: If license is revoked.
            LicenseSuspendedError: If license is suspended.
            DeviceLimitExceededError: If device limit exceeded.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            
            # Check license status
            if license_obj.status ==  LICENSE_STATUS_REVOKED:
                raise LicenseRevokedError(f"License '{license_key}' has been revoked")
            
            if license_obj.status == LICENSE_STATUS_SUSPENDED:
                raise LicenseSuspendedError(f"License '{license_key}' is suspended")
            
            # Check expiry
            if get_current_time() > license_obj.expires_at:
                license_obj.status =  LICENSE_STATUS_EXPIRED
                db.commit()
                raise LicenseExpiredError(f"License '{license_key}' has expired")
            
            # Register or update device using shared device service logic
            device = DeviceService.register_device(
                db,
                license_id=license_obj.id,
                device_uuid=device_uuid,
                browser=browser,
                operating_system=operating_system,
                extension_version=extension_version,
                device_fingerprint=device_fingerprint,
            )
            
            # Update activation metadata on first activation
            if not license_obj.activated_at:
                license_obj.activated_at = get_current_time()
            license_obj.activated_device_count = len(license_obj.devices)
            
            db.commit()
            db.refresh(license_obj)
            db.refresh(device)
            
            # Log activity
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action="license_activated",
                ip_address=ip_address,
                browser=browser
            )
            
            return {
                "license_id": license_obj.id,
                "license_key": license_obj.license_key,
                "status": license_obj.status,
                "expires_at": license_obj.expires_at,
                "activated_at": license_obj.activated_at,
                "device_id": device.id,
                "device_uuid": device.device_uuid,
                "max_devices": license_obj.plan.max_devices,
                "devices_used": len(license_obj.devices)
            }
            
        except (
            LicenseNotFoundError,
            InvalidLicenseKeyFormatError,
            LicenseExpiredError,
            LicenseRevokedError,
            LicenseSuspendedError,
            DeviceLimitExceededError,
        ):
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to activate license: {exc}") from exc

    @staticmethod
    def verify_license(
        db: Session,
        license_key: str,
        device_uuid: str,
        browser: str | None = None,
        ip_address: str | None = None
    ) -> dict:
        """
        Verify a license and device.
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key.
            device_uuid: Device UUID.
            browser: Optional browser for verification.
            ip_address: Optional IP address for logging.
            
        Returns:
            Dictionary with license validity info.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
            LicenseExpiredError: If license is expired.
            LicenseRevokedError: If license is revoked.
            LicenseSuspendedError: If license is suspended.
            DeviceNotFoundError: If device not registered.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            
            # Check license status
            if license_obj.status ==  LICENSE_STATUS_REVOKED:
                raise LicenseRevokedError(f"License '{license_key}' has been revoked")
            
            if license_obj.status == LICENSE_STATUS_SUSPENDED:
                raise LicenseSuspendedError(f"License '{license_key}' is suspended")
            
            # Check expiry
            if get_current_time() > license_obj.expires_at:
                license_obj.status =  LICENSE_STATUS_EXPIRED
                db.commit()
                raise LicenseExpiredError(f"License '{license_key}' has expired")
            
            # Find device
            device = db.query(Device).filter(
                Device.license_id == license_obj.id,
                Device.device_uuid == device_uuid
            ).first()
            
            if device is None:
                raise DeviceNotFoundError(
                    f"Device '{device_uuid}' not registered for license '{license_key}'"
                )

            if device.is_disabled:
                raise DeviceDisabledError(
                    f"Device '{device_uuid}' has been disabled and cannot verify."
                )
            
            # Update device last_seen and verification timestamp
            now = get_current_time()
            device.last_seen = now
            device.last_verified_at = now
            if browser is not None:
                device.browser = browser
            if ip_address is not None:
                device.ip_address = ip_address
            
            # Update license last_verified
            license_obj.last_verified = now
            
            db.commit()
            
            # Log activity
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action="license_verified",
                ip_address=ip_address,
                browser=browser
            )
            
            return {
                "valid": True,
                "license_key": license_obj.license_key,
                "status": license_obj.status,
                "expires_at": license_obj.expires_at,
                "days_remaining": remaining_days(license_obj.expires_at),
                "device_uuid": device.device_uuid,
                "devices_used": len(license_obj.devices),
                "max_devices": license_obj.plan.max_devices
            }
            
        except (
            LicenseNotFoundError,
            InvalidLicenseKeyFormatError,
            LicenseExpiredError,
            LicenseRevokedError,
            LicenseSuspendedError,
            DeviceNotFoundError,
        ):
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to verify license: {exc}") from exc

    @staticmethod
    def extend_license(
        db: Session,
        license_key: str,
        plan_id: int,
        ip_address: str | None = None
    ) -> License:
        """
        Extend a license with a new plan.
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key.
            plan_id: New plan ID.
            ip_address: Optional IP address for logging.
            
        Returns:
            Updated License model instance.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
            PlanNotFoundError: If plan doesn't exist.
            LicenseRevokedError: If license is revoked.
            OperationNotAllowedError: If license cannot be extended.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            
            # Check if can extend
            if license_obj.status ==  LICENSE_STATUS_REVOKED:
                raise LicenseRevokedError(f"Cannot extend revoked license '{license_key}'")
            
            # Validate plan
            plan = LicenseService.validate_plan(db, plan_id)
            
            # Add duration to current expiry or from now if expired
            if get_current_time() > license_obj.expires_at:
                new_expiry = get_current_time() + timedelta(days=plan.duration_days)
            else:
                new_expiry = license_obj.expires_at + timedelta(days=plan.duration_days)
            
            license_obj.expires_at = new_expiry
            license_obj.status = LICENSE_STATUS_ACTIVE
            
            db.commit()
            db.refresh(license_obj)
            
            # Log activity
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action="license_extended",
                ip_address=ip_address,
                browser=None
            )
            
            return license_obj
            
        except (
            LicenseNotFoundError,
            InvalidLicenseKeyFormatError,
            PlanNotFoundError,
            LicenseRevokedError,
        ):
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to extend license: {exc}") from exc

    @staticmethod
    def revoke_license(
        db: Session,
        license_key: str,
        reason: str | None = None,
        ip_address: str | None = None
    ) -> License:
        """
        Revoke a license (permanent).
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key.
            reason: Optional revocation reason.
            ip_address: Optional IP address for logging.
            
        Returns:
            Updated License model instance.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
            OperationNotAllowedError: If license already revoked.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            
            if license_obj.status ==  LICENSE_STATUS_REVOKED:
                raise OperationNotAllowedError(
                    f"License '{license_key}' is already revoked"
                )
            
            license_obj.status = LICENSE_STATUS_REVOKED

            # Immediately expire the license to reduce remaining validity time
            now = get_current_time()
            if license_obj.expires_at is None or license_obj.expires_at > now:
                license_obj.expires_at = now

            # Disable and invalidate all devices for this license so extension tokens stop working
            for device in list(license_obj.devices):
                try:
                    device.is_disabled = True
                    # bump token_version to invalidate existing tokens
                    device.token_version = (device.token_version or 0) + 1
                    db.add(device)
                except Exception:
                    # continue disabling other devices even if one fails
                    continue

            db.commit()
            db.refresh(license_obj)

            # Log activity
            action_note = f"license_revoked ({reason})" if reason else "license_revoked"
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action=action_note,
                ip_address=ip_address,
                browser=None
            )

            return license_obj
            
        except (LicenseNotFoundError, InvalidLicenseKeyFormatError, OperationNotAllowedError):
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to revoke license: {exc}") from exc

    @staticmethod
    def suspend_license(
        db: Session,
        license_key: str,
        reason: str | None = None,
        ip_address: str | None = None
    ) -> License:
        """
        Suspend a license (temporary).
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key.
            reason: Optional suspension reason.
            ip_address: Optional IP address for logging.
            
        Returns:
            Updated License model instance.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
            OperationNotAllowedError: If license already suspended/revoked.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            
            if license_obj.status in (LICENSE_STATUS_REVOKED, LICENSE_STATUS_SUSPENDED):
                raise OperationNotAllowedError(
                    f"Cannot suspend license with status '{license_obj.status}'"
                )
            
            license_obj.status = LICENSE_STATUS_SUSPENDED
            
            db.commit()
            db.refresh(license_obj)
            
            # Log activity
            action_note = f"license_suspended ({reason})" if reason else "license_suspended"
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action=action_note,
                ip_address=ip_address,
                browser=None
            )
            
            return license_obj
            
        except (LicenseNotFoundError, InvalidLicenseKeyFormatError, OperationNotAllowedError):
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to suspend license: {exc}") from exc

    @staticmethod
    def reactivate_license(
        db: Session,
        license_key: str,
        ip_address: str | None = None
    ) -> License:
        """
        Reactivate a suspended license.
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key.
            ip_address: Optional IP address for logging.
            
        Returns:
            Updated License model instance.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
            OperationNotAllowedError: If license cannot be reactivated.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            
            if license_obj.status ==  LICENSE_STATUS_REVOKED:
                raise OperationNotAllowedError(
                    f"Cannot reactivate revoked license '{license_key}'"
                )
            
            if license_obj.status not in (LICENSE_STATUS_SUSPENDED, LICENSE_STATUS_EXPIRED):
                raise OperationNotAllowedError(
                    f"License with status '{license_obj.status}' cannot be reactivated"
                )
            
            license_obj.status = LICENSE_STATUS_ACTIVE
            
            # If expired, extend expiry
            if get_current_time() > license_obj.expires_at:
                license_obj.expires_at = get_current_time() + timedelta(
                    days=license_obj.plan.duration_days
                )
            
            db.commit()
            db.refresh(license_obj)
            
            # Log activity
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action="license_reactivated",
                ip_address=ip_address,
                browser=None
            )
            
            return license_obj
            
        except (LicenseNotFoundError, InvalidLicenseKeyFormatError, OperationNotAllowedError):
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to reactivate license: {exc}") from exc

    @staticmethod
    def reset_device(
        db: Session,
        license_key: str,
        device_uuid: str,
        ip_address: str | None = None
    ) -> bool:
        """
        Remove a device from a license.
        
        Args:
            db: SQLAlchemy database session.
            license_key: License key.
            device_uuid: Device UUID to remove.
            ip_address: Optional IP address for logging.
            
        Returns:
            True if device reset successfully.
            
        Raises:
            InvalidLicenseKeyFormatError: If key format is invalid.
            LicenseNotFoundError: If license doesn't exist.
            DeviceNotFoundError: If device not registered.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            
            device = db.query(Device).filter(
                Device.license_id == license_obj.id,
                Device.device_uuid == device_uuid
            ).first()
            
            if not device:
                raise DeviceNotFoundError(
                    f"Device '{device_uuid}' not found for license '{license_key}'"
                )
            
            db.delete(device)
            db.commit()
            
            # Log activity
            LicenseService._create_activity_log(
                db,
                license_obj.id,
                action="device_reset",
                ip_address=ip_address,
                browser=None
            )
            
            return True
            
        except (LicenseNotFoundError, InvalidLicenseKeyFormatError, DeviceNotFoundError):
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to reset device: {exc}") from exc

    @staticmethod
    def search_licenses(
        db: Session,
        query_str: str | None = None,
        customer_id: int | None = None,
        product_id: int | None = None,
        status: str | None = None
    ) -> list[License]:
        """
        Search licenses by multiple criteria.
        
        Args:
            db: SQLAlchemy database session.
            query_str: Search by license key, customer name, or email.
            customer_id: Filter by customer ID.
            product_id: Filter by product ID.
            status: Filter by status.
            
        Returns:
            List of matching License model instances.
        """
        query = db.query(License)
        
        if query_str:
            query = query.filter(
                (License.license_key.ilike(f"%{query_str}%")) |
                (License.customer.has(Customer.name.ilike(f"%{query_str}%"))) |
                (License.customer.has(Customer.email.ilike(f"%{query_str}%")))
            )
        
        if customer_id is not None:
            query = query.filter(License.customer_id == customer_id)
        
        if product_id is not None:
            query = query.filter(License.product_id == product_id)
        
        if status is not None:
            query = query.filter(License.status == status)
        
        return query.order_by(License.created_at.desc()).all()

    @staticmethod
    def get_license_activity(
        db: Session,
        license_id: int,
        limit: int = 50
    ) -> list[ActivityLog]:
        """
        Get activity logs for a license.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            limit: Maximum number of logs to return.
            
        Returns:
            List of ActivityLog model instances.
            
        Raises:
            LicenseNotFoundError: If license doesn't exist.
        """
        LicenseService.get_license(db, license_id)
        
        return db.query(ActivityLog).filter(
            ActivityLog.license_id == license_id
        ).order_by(ActivityLog.timestamp.desc()).limit(limit).all()

    @staticmethod
    def _create_activity_log(
        db: Session,
        license_id: int,
        action: str,
        ip_address: str | None = None,
        browser: str | None = None
    ) -> ActivityLog:
        """
        Create an activity log entry (internal method).
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            action: Action description.
            ip_address: Optional IP address.
            browser: Optional browser name.
            
        Returns:
            Created ActivityLog model instance.
        """
        log = ActivityLog(
            license_id=license_id,
            action=action,
            ip_address=ip_address,
            browser=browser,
            timestamp=get_current_time()
        )
        
        try:
            db.add(log)
            db.commit()
            db.refresh(log)
            return log
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to create activity log: {exc}") from exc

    @staticmethod
    def get_license_stats(db: Session, product_id: int | None = None) -> dict:
        """
        Get license statistics.
        
        Args:
            db: SQLAlchemy database session.
            product_id: Optional product ID filter.
            
        Returns:
            Dictionary with license statistics.
        """
        query = db.query(License)
        
        if product_id is not None:
            query = query.filter(License.product_id == product_id)
        
        total = query.count()
        active = query.filter(License.status == LICENSE_STATUS_ACTIVE).count()
        suspended = query.filter(License.status == LICENSE_STATUS_SUSPENDED).count()
        revoked = query.filter(License.status == LICENSE_STATUS_REVOKED).count()
        expired = query.filter(License.status == LICENSE_STATUS_EXPIRED).count()

        today = get_current_time().date()
        today_start = datetime.combine(today, datetime.min.time())
        yesterday = today - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        yesterday_end = datetime.combine(yesterday, datetime.max.time())

        licenses_today = query.filter(License.created_at >= today_start).count()
        licenses_yesterday = query.filter(
            License.created_at >= yesterday_start,
            License.created_at <= yesterday_end,
        ).count()

        return {
            "total": total,
            LICENSE_STATUS_ACTIVE: active,
            LICENSE_STATUS_SUSPENDED: suspended,
            LICENSE_STATUS_REVOKED: revoked,
            LICENSE_STATUS_EXPIRED: expired,
            "licenses_created_today": licenses_today,
            "licenses_created_yesterday": licenses_yesterday,
        }