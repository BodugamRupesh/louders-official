"""
Device Service for LOUD Platform Licensing System.

Handles:
- Device registration and tracking
- Device removal and reset
- Device validation
- Device count and limit checking
- Browser and OS tracking
"""

from app.utils.datetime_utils import get_current_time
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import LICENSE_STATUS_ACTIVE
from app.exceptions import (
    DeviceNotFoundError,
    LicenseNotFoundError,
    DeviceLimitExceededError,
    DatabaseError,
    OperationNotAllowedError,
)
from app.models import Device, License, Product, Customer


class DeviceService:
    """Service for handling device operations."""

    @staticmethod
    def register_device(
        db: Session,
        license_id: int,
        device_uuid: str,
        browser: str,
        operating_system: str | None = None,
        extension_version: str | None = None,
        ip_address: str | None = None,
        device_name: str | None = None,
        device_fingerprint: str | None = None,
    ) -> Device:
        """
        Register a new device for a license.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            device_uuid: Device UUID (unique identifier).
            browser: Browser name (Chrome, Edge, Firefox, etc.).
            operating_system: Optional OS name.
            extension_version: Optional extension version.
            
        Returns:
            Created Device model instance.
            
        Raises:
            LicenseNotFoundError: If license doesn't exist.
            DeviceLimitExceededError: If device limit exceeded.
            DatabaseError: If database operation fails.
        """
        try:
            # Verify license exists
            license_obj = db.query(License).filter(
                License.id == license_id
            ).first()
            
            if license_obj is None:
                raise LicenseNotFoundError(f"License with ID {license_id} not found")
            
            # Check if device already registered
            existing = db.query(Device).filter(
                Device.license_id == license_id,
                Device.device_uuid == device_uuid
            ).first()
            
            now = get_current_time()
            if existing is not None:
                existing.device_name = device_name or existing.device_name
                existing.browser = browser
                if operating_system is not None:
                    existing.operating_system = operating_system
                if extension_version is not None:
                    existing.extension_version = extension_version
                if ip_address is not None:
                    existing.ip_address = ip_address
                if device_fingerprint is not None:
                    existing.device_fingerprint = device_fingerprint
                if existing.is_disabled:
                    existing.token_version += 1
                existing.is_disabled = False
                existing.last_seen = now
                existing.last_heartbeat_at = now
                existing.last_verified_at = now
                
                db.commit()
                db.refresh(existing)
                db.expire(license_obj, ["devices"])
                
                return existing
            
            # Check device limit only when a new device would be created
            current_device_count = db.query(Device).filter(
                Device.license_id == license_id
            ).count()
            
            max_devices = license_obj.plan.max_devices
            
            if current_device_count >= max_devices:
                raise DeviceLimitExceededError(
                    f"License has reached maximum device limit of {max_devices}"
                )
            
            # Create new device
            device = Device(
                license_id=license_id,
                device_uuid=device_uuid,
                device_fingerprint=device_fingerprint,
                device_name=device_name,
                browser=browser,
                operating_system=operating_system,
                extension_version=extension_version,
                ip_address=ip_address,
                first_activated_at=now,
                last_verified_at=now,
                last_heartbeat_at=now,
                last_seen=now,
            )
            
            db.add(device)
            db.flush()
            current_count = db.query(Device).filter(
                Device.license_id == license_id
            ).count()
            license_obj.activated_device_count = current_count
            db.commit()
            db.refresh(device)
            db.refresh(license_obj)
            db.expire(license_obj, ["devices"])
            
            return device
            
        except (LicenseNotFoundError, DeviceLimitExceededError):
            raise
        except IntegrityError:
            # Handle concurrent race condition: another request already inserted this device
            db.rollback()
            existing = db.query(Device).filter(
                Device.license_id == license_id,
                Device.device_uuid == device_uuid,
            ).first()
            if existing is not None:
                existing.device_name = device_name or existing.device_name
                existing.browser = browser
                if operating_system is not None:
                    existing.operating_system = operating_system
                if extension_version is not None:
                    existing.extension_version = extension_version
                if ip_address is not None:
                    existing.ip_address = ip_address
                if device_fingerprint is not None:
                    existing.device_fingerprint = device_fingerprint
                if existing.is_disabled:
                    existing.token_version += 1
                existing.is_disabled = False
                now = get_current_time()
                existing.last_seen = now
                existing.last_heartbeat_at = now
                existing.last_verified_at = now

                db.commit()
                db.refresh(existing)
                return existing
            raise DatabaseError("Failed to register device due to concurrent conflict.")
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to register device: {exc}") from exc

    @staticmethod
    def get_device(db: Session, device_id: int) -> Device:
        """
        Get device by ID.
        
        Args:
            db: SQLAlchemy database session.
            device_id: Device ID.
            
        Returns:
            Device model instance.
            
        Raises:
            DeviceNotFoundError: If device doesn't exist.
        """
        device = db.query(Device).filter(
            Device.id == device_id
        ).first()
        
        if device is None:
            raise DeviceNotFoundError(f"Device with ID {device_id} not found")
        
        return device

    @staticmethod
    def get_device_by_uuid(
        db: Session,
        license_id: int,
        device_uuid: str
    ) -> Device:
        """
        Get device by UUID for a specific license.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            device_uuid: Device UUID.
            
        Returns:
            Device model instance.
            
        Raises:
            DeviceNotFoundError: If device doesn't exist.
        """
        device = db.query(Device).filter(
            Device.license_id == license_id,
            Device.device_uuid == device_uuid
        ).first()
        
        if not device:
            raise DeviceNotFoundError(
                f"Device '{device_uuid}' not found for license ID {license_id}"
            )
        
        return device

    @staticmethod
    def remove_device(db: Session, device_id: int) -> bool:
        """
        Remove a device from a license.
        
        Args:
            db: SQLAlchemy database session.
            device_id: Device ID.
            
        Returns:
            True if device removed successfully.
            
        Raises:
            DeviceNotFoundError: If device doesn't exist.
            DatabaseError: If database operation fails.
        """
        try:
            device = DeviceService.get_device(db, device_id)
            license_obj = db.query(License).filter(License.id == device.license_id).first()
            
            db.delete(device)
            db.flush()
            
            if license_obj is not None:
                license_obj.activated_device_count = db.query(Device).filter(
                    Device.license_id == license_obj.id
                ).count()
            
            db.commit()
            if license_obj is not None:
                db.refresh(license_obj)
                db.expire(license_obj, ["devices"])
            
            return True
            
        except DeviceNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to remove device: {exc}") from exc

    @staticmethod
    def reset_device_by_uuid(db: Session, license_id: int, device_uuid: str) -> bool:
        """
        Reset (remove) a device by its UUID.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            device_uuid: Device UUID.
            
        Returns:
            True if device reset successfully.
            
        Raises:
            DeviceNotFoundError: If device doesn't exist.
            DatabaseError: If database operation fails.
        """
        try:
            device = DeviceService.get_device_by_uuid(db, license_id, device_uuid)
            return DeviceService.remove_device(db, device.id)
            
        except DeviceNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to reset device: {exc}") from exc

    @staticmethod
    def update_last_seen(db: Session, device_id: int) -> Device:
        """
        Update the last_seen timestamp for a device.
        
        Args:
            db: SQLAlchemy database session.
            device_id: Device ID.
            
        Returns:
            Updated Device model instance.
            
        Raises:
            DeviceNotFoundError: If device doesn't exist.
            DatabaseError: If database operation fails.
        """
        try:
            device = DeviceService.get_device(db, device_id)
            
            now = get_current_time()
            device.last_seen = now
            device.last_heartbeat_at = now
            
            db.commit()
            db.refresh(device)
            
            return device
            
        except DeviceNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to update device last_seen: {exc}") from exc

    @staticmethod
    def update_heartbeat(
        db: Session,
        device_id: int,
        browser: str | None = None,
        operating_system: str | None = None,
        extension_version: str | None = None,
        ip_address: str | None = None,
    ) -> Device:
        """
        Update device heartbeat metadata.
        """
        try:
            device = DeviceService.get_device(db, device_id)

            if device.is_disabled:
                raise OperationNotAllowedError(
                    "Disabled devices cannot send heartbeat updates."
                )

            if browser is not None:
                device.browser = browser
            if operating_system is not None:
                device.operating_system = operating_system
            if extension_version is not None:
                device.extension_version = extension_version
            if ip_address is not None:
                device.ip_address = ip_address

            now = get_current_time()
            device.last_heartbeat_at = now
            device.last_seen = now

            db.commit()
            db.refresh(device)
            return device
        except DeviceNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to update device heartbeat: {exc}") from exc

    @staticmethod
    def update_device_info(
        db: Session,
        device_id: int,
        browser: str | None = None,
        operating_system: str | None = None,
        extension_version: str | None = None,
        device_name: str | None = None,
        ip_address: str | None = None,
        device_fingerprint: str | None = None,
    ) -> Device:
        """
        Update device information.
        
        Args:
            db: SQLAlchemy database session.
            device_id: Device ID.
            browser: New browser name.
            operating_system: New OS name.
            extension_version: New extension version.
            
        Returns:
            Updated Device model instance.
            
        Raises:
            DeviceNotFoundError: If device doesn't exist.
            DatabaseError: If database operation fails.
        """
        try:
            device = DeviceService.get_device(db, device_id)
            
            if browser is not None:
                device.browser = browser
            
            if operating_system is not None:
                device.operating_system = operating_system
            
            if extension_version is not None:
                device.extension_version = extension_version
            
            if device_name is not None:
                device.device_name = device_name
            
            if ip_address is not None:
                device.ip_address = ip_address
            if device_fingerprint is not None:
                device.device_fingerprint = device_fingerprint
            
            device.last_seen = get_current_time()
            
            db.commit()
            db.refresh(device)
            
            return device
            
        except DeviceNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to update device info: {exc}") from exc

    @staticmethod
    def disable_device(db: Session, device_id: int) -> Device:
        try:
            device = DeviceService.get_device(db, device_id)
            if not device.is_disabled:
                device.token_version += 1
            device.is_disabled = True
            device.last_seen = get_current_time()
            db.commit()
            db.refresh(device)
            return device
        except DeviceNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to disable device: {exc}") from exc

    @staticmethod
    def reactivate_device(db: Session, device_id: int) -> Device:
        try:
            device = DeviceService.get_device(db, device_id)
            if device.license.status != LICENSE_STATUS_ACTIVE:
                raise OperationNotAllowedError(
                    f"Cannot reactivate device for license status '{device.license.status}'"
                )
            device.is_disabled = False
            device.last_seen = get_current_time()
            device.last_heartbeat_at = get_current_time()
            db.commit()
            db.refresh(device)
            return device
        except DeviceNotFoundError:
            raise
        except OperationNotAllowedError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to reactivate device: {exc}") from exc

    @staticmethod
    def force_logout_device(db: Session, device_id: int) -> Device:
        return DeviceService.disable_device(db, device_id)

    @staticmethod
    def rename_device(db: Session, device_id: int, device_name: str) -> Device:
        try:
            device = DeviceService.get_device(db, device_id)
            device.device_name = device_name
            db.commit()
            db.refresh(device)
            return device
        except DeviceNotFoundError:
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise DatabaseError(f"Failed to rename device: {exc}") from exc

    @staticmethod
    def get_license_devices(db: Session, license_id: int) -> list[Device]:
        """
        Get all devices for a license.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            
        Returns:
            List of Device model instances.
            
        Raises:
            LicenseNotFoundError: If license doesn't exist.
        """
        license_obj = db.query(License).filter(
            License.id == license_id
        ).first()
        
        if not license_obj:
            raise LicenseNotFoundError(f"License with ID {license_id} not found")
        
        return license_obj.devices

    @staticmethod
    def get_device_count(db: Session, license_id: int) -> int:
        """
        Get number of devices registered for a license.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            
        Returns:
            Number of registered devices.
            
        Raises:
            LicenseNotFoundError: If license doesn't exist.
        """
        return (
            db.query(Device)
            .filter(Device.license_id == license_id)
            .count()
)

    @staticmethod
    def can_register_device(db: Session, license_id: int) -> bool:
        """
        Check if license can register another device.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            
        Returns:
            True if device can be registered, False otherwise.
            
        Raises:
            LicenseNotFoundError: If license doesn't exist.
        """
        license_obj = db.query(License).filter(
            License.id == license_id
        ).first()
        
        if not license_obj:
            raise LicenseNotFoundError(f"License with ID {license_id} not found")
        
        device_count = DeviceService.get_device_count(db, license_id)
        max_devices = license_obj.plan.max_devices
        
        return device_count < max_devices

    @staticmethod
    def get_devices_by_browser(
        db: Session,
        license_id: int,
        browser: str
    ) -> list[Device]:
        """
        Get devices by browser type for a license.
        
        Args:
            db: SQLAlchemy database session.
            license_id: License ID.
            browser: Browser name to filter by.
            
        Returns:
            List of Device model instances.
        """
        return db.query(Device).filter(
            Device.license_id == license_id,
            Device.browser == browser
        ).all()

    @staticmethod
    def list_devices(
        db: Session,
        license_id: int | None = None,
        device_id: int | None = None,
        device_uuid: str | None = None,
        browser: str | None = None,
        operating_system: str | None = None,
        product_name: str | None = None,
        customer_name: str | None = None,
        status: str | None = None,
        query_str: str | None = None,
    ) -> list[Device]:
        """
        List devices with optional filters.

        Args:
            db: SQLAlchemy database session.
            license_id: Optional license ID filter.
            device_id: Optional device ID filter.
            device_uuid: Optional device UUID filter.
            browser: Optional browser filter.
            operating_system: Optional operating system filter.
            product_name: Optional product name filter.
            customer_name: Optional customer name filter.
            status: Optional device status filter.
            query_str: Optional generic search query.

        Returns:
            List of Device model instances.
        """
        query = db.query(Device).join(Device.license).join(License.product).join(License.customer)

        if license_id is not None:
            query = query.filter(Device.license_id == license_id)

        if device_id is not None:
            query = query.filter(Device.id == device_id)

        if device_uuid is not None:
            query = query.filter(Device.device_uuid.ilike(f"%{device_uuid}%"))

        if browser is not None:
            query = query.filter(Device.browser.ilike(f"%{browser}%"))

        if operating_system is not None:
            query = query.filter(Device.operating_system.ilike(f"%{operating_system}%"))

        if product_name is not None:
            query = query.filter(License.product.has(Product.name.ilike(f"%{product_name}%")))

        if customer_name is not None:
            query = query.filter(License.customer.has(Customer.name.ilike(f"%{customer_name}%")))

        if status is not None:
            if status.lower() == "online":
                timeout_seconds = getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SECONDS", 300)
                cutoff = get_current_time() - timedelta(seconds=timeout_seconds)
                query = query.filter(Device.last_heartbeat_at >= cutoff, Device.is_disabled.is_(False))
            elif status.lower() == "offline":
                timeout_seconds = getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SECONDS", 300)
                cutoff = get_current_time() - timedelta(seconds=timeout_seconds)
                query = query.filter(
                    (Device.last_heartbeat_at < cutoff) | (Device.last_heartbeat_at.is_(None)),
                    Device.is_disabled.is_(False),
                )
            elif status.lower() == "disabled":
                query = query.filter(Device.is_disabled.is_(True))

        if query_str is not None:
            like_value = f"%{query_str}%"
            query = query.filter(
                (Device.device_uuid.ilike(like_value)) |
                (Device.browser.ilike(like_value)) |
                (Device.operating_system.ilike(like_value)) |
                (Device.ip_address.ilike(like_value)) |
                (License.license_key.ilike(like_value)) |
                (License.product.has(Product.name.ilike(like_value))) |
                (License.customer.has(Customer.name.ilike(like_value)))
            )

        return query.order_by(Device.last_seen.desc()).all()

    @staticmethod
    def get_device_stats(db: Session) -> dict:
        """
        Get basic device statistics.

        Args:
            db: SQLAlchemy database session.

        Returns:
            Dictionary with device statistics.
        """
        query = db.query(Device)
        total_devices = query.count()

        devices_by_browser = {
            browser: count
            for browser, count in query.with_entities(
                Device.browser,
                func.count(Device.id).label("count"),
            ).group_by(Device.browser).all()
        }

        today = get_current_time().date()
        devices_registered_today = query.filter(
            Device.first_activated_at >= datetime.combine(today, datetime.min.time())
        ).count()

        timeout_seconds = getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SECONDS", 300)
        cutoff = get_current_time() - timedelta(seconds=timeout_seconds)

        online_devices = query.filter(
            Device.last_heartbeat_at >= cutoff,
            Device.is_disabled.is_(False),
        ).count()

        offline_devices = query.filter(
            ((Device.last_heartbeat_at < cutoff) | (Device.last_heartbeat_at.is_(None))) &
            Device.is_disabled.is_(False)
        ).count()

        disabled_devices = query.filter(Device.is_disabled.is_(True)).count()

        yesterday = today - timedelta(days=1)
        devices_registered_yesterday = query.filter(
            Device.first_activated_at >= datetime.combine(yesterday, datetime.min.time()),
            Device.first_activated_at <= datetime.combine(yesterday, datetime.max.time()),
        ).count()

        return {
            "total_devices": total_devices,
            "devices_by_browser": devices_by_browser,
            "browsers": devices_by_browser,
            "devices_registered_today": devices_registered_today,
            "devices_registered_yesterday": devices_registered_yesterday,
            "online_devices": online_devices,
            "offline_devices": offline_devices,
            "disabled_devices": disabled_devices,
        }
