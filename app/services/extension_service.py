"""
Extension Service for LOUD Platform Licensing System.

This service acts as the bridge between browser extension clients and the
existing licensing platform. It orchestrates the current license and device
services instead of reimplementing their business logic.
"""

from __future__ import annotations

from app.utils.datetime_utils import get_current_time
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import (
    DatabaseError,
    DeviceDisabledError,
    DeviceNotFoundError,
    InvalidDataError,
    InvalidProductKeyError,
    InvalidTokenError,
    LicenseExpiredError,
    LicenseNotFoundError,
    LicenseRevokedError,
    LicenseSuspendedError,
    OperationNotAllowedError,
    ProductNotFoundError,
)
from app.models import Product
from app.services.device_service import DeviceService
from app.services.extension_jwt_service import ExtensionJWTService
from app.services.license_service import LicenseService
from app.services.product_service import ProductService
from app.exceptions import LicenseServerException


class ExtensionService:
    """Service for handling browser extension licensing operations."""

    SUPPORTED_BROWSERS: dict[str, str] = {
        "chrome": "Chrome",
        "edge": "Edge",
        "firefox": "Firefox",
        "brave": "Brave",
        "opera": "Opera",
    }

    @staticmethod
    def validate_product_api_key(db: Session, api_key: str) -> Product:
        """Validate a product API key for extension requests."""
        return ProductService.validate_api_key(db, api_key)

    @staticmethod
    def activate_extension(
        db: Session,
        license_key: str,
        device_uuid: str,
        browser: str,
        operating_system: str | None = None,
        extension_version: str | None = None,
        ip_address: str | None = None,
        device_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        """
        Activate a license for an extension device.

        Args:
            db: SQLAlchemy database session.
            license_key: License key supplied by the extension client.
            device_uuid: Unique device identifier.
            browser: Browser name used by the extension.
            operating_system: Optional operating system name.
            extension_version: Optional extension version string.
            ip_address: Optional client IP address for logging.

        Returns:
            Dictionary containing a clean activation payload for the extension.

        Raises:
            InvalidDataError: If the browser is unsupported or the input is invalid.
            LicenseNotFoundError: If the license does not exist.
            LicenseExpiredError: If the license has expired.
            LicenseRevokedError: If the license has been revoked.
            LicenseSuspendedError: If the license is suspended.
            DatabaseError: If the database operation fails.
        """
        browser_name = ExtensionService.validate_browser(browser)

        activation_result = LicenseService.activate_license(
            db,
            license_key=license_key,
            device_uuid=device_uuid,
            browser=browser_name,
            operating_system=operating_system,
            extension_version=extension_version,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
        )

        device_id = activation_result.get("device_id")
        if device_id is None:
            raise LicenseServerException("Activation did not return a device identifier.")

        license_obj = LicenseService.get_license_by_key(db, license_key)
        device = DeviceService.get_device(db, device_id)
        return {
            "success": True,
            "license_status": license_obj.status,
            "expiration": license_obj.expires_at,
            "plan": license_obj.plan.name,
            "customer": license_obj.customer.name,
            "devices_used": activation_result.get("devices_used", 0),
            "devices_allowed": license_obj.plan.max_devices,
            "device_id": device_id,
            "activated_at": activation_result.get("activated_at"),
            "device_token_version": device.token_version,
        }

    @staticmethod
    def _validate_extension_token(
        db: Session,
        extension_token: str | None,
        license_key: str,
        device_uuid: str,
    ) -> None:
        if not extension_token:
            return

        payload = ExtensionJWTService.verify_token(extension_token)
        if payload.license_key != license_key or payload.device_uuid != device_uuid:
            raise InvalidTokenError(
                "Extension token payload does not match the expected device or license."
            )

        license_obj = LicenseService.get_license_by_key(db, license_key)
        device = DeviceService.get_device_by_uuid(db, license_obj.id, device_uuid)

        if payload.token_version != device.token_version:
            raise InvalidTokenError("Extension token has been invalidated.")

    @staticmethod
    def verify_extension(
        db: Session,
        license_key: str,
        device_uuid: str,
        browser: str | None = None,
        ip_address: str | None = None,
        extension_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Verify that a license and device are valid for the extension.

        Args:
            db: SQLAlchemy database session.
            license_key: License key supplied by the extension client.
            device_uuid: Unique device identifier.
            browser: Optional browser string for logging and validation.
            ip_address: Optional client IP address for logging.

        Returns:
            Dictionary with the extension-facing verification payload.

        Raises:
            InvalidDataError: If the browser is unsupported.
            LicenseNotFoundError: If the license does not exist.
            LicenseExpiredError: If the license has expired.
            LicenseRevokedError: If the license has been revoked.
            LicenseSuspendedError: If the license is suspended.
            DeviceNotFoundError: If the device is not registered for the license.
            DatabaseError: If the database operation fails.
        """
        if browser is not None:
            ExtensionService.validate_browser(browser)

        ExtensionService._validate_extension_token(
            db,
            extension_token=extension_token,
            license_key=license_key,
            device_uuid=device_uuid,
        )

        LicenseService.verify_license(
            db,
            license_key=license_key,
            device_uuid=device_uuid,
            browser=browser,
            ip_address=ip_address,
        )

        license_obj = LicenseService.get_license_by_key(db, license_key)
        return {
            "success": True,
            "valid": True,
            "license_key": license_obj.license_key,
            "license_status": license_obj.status,
            "expires_at": license_obj.expires_at,
            "plan": license_obj.plan.name,
            "customer": license_obj.customer.name,
            "devices_used": len(license_obj.devices),
            "devices_allowed": license_obj.plan.max_devices,
            "last_verified": license_obj.last_verified,
        }

    @staticmethod
    def heartbeat(
        db: Session,
        license_key: str,
        device_uuid: str,
        browser: str | None = None,
        operating_system: str | None = None,
        extension_version: str | None = None,
        ip_address: str | None = None,
        extension_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Refresh the device heartbeat and license verification timestamp.

        Args:
            db: SQLAlchemy database session.
            license_key: License key associated with the device.
            device_uuid: Unique device identifier.

        Returns:
            Dictionary containing the current heartbeat state.

        Raises:
            LicenseNotFoundError: If the license does not exist.
            DeviceNotFoundError: If the device is not registered.
            DatabaseError: If the database operation fails.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            device = DeviceService.get_device_by_uuid(
                db,
                license_id=license_obj.id,
                device_uuid=device_uuid,
            )

            ExtensionService._validate_extension_token(
                db,
                extension_token=extension_token,
                license_key=license_key,
                device_uuid=device_uuid,
            )

            DeviceService.update_heartbeat(
                db,
                device.id,
                browser=browser,
                operating_system=operating_system,
                extension_version=extension_version,
                ip_address=ip_address,
            )

            now = get_current_time()
            license_obj.last_verified = now
            db.commit()
            db.refresh(license_obj)

            return {
                "success": True,
                "license_status": license_obj.status,
                "last_verified": license_obj.last_verified,
                "server_timestamp": now,
                "device_uuid": device.device_uuid,
            }
        except (LicenseNotFoundError, DeviceNotFoundError, InvalidTokenError, OperationNotAllowedError, DeviceDisabledError):
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            db.rollback()
            raise DatabaseError(f"Failed to update extension heartbeat: {str(exc)}") from exc

    @staticmethod
    def deactivate_extension(
        db: Session,
        license_key: str,
        device_uuid: str,
    ) -> dict[str, Any]:
        """
        Remove a device from the license and deactivate its extension session.

        Args:
            db: SQLAlchemy database session.
            license_key: License key associated with the device.
            device_uuid: Unique device identifier.

        Returns:
            Dictionary confirming successful deactivation.

        Raises:
            LicenseNotFoundError: If the license does not exist.
            DeviceNotFoundError: If the device is not registered.
            DatabaseError: If the database operation fails.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            device = DeviceService.get_device_by_uuid(
                db,
                license_id=license_obj.id,
                device_uuid=device_uuid,
            )
            removed = DeviceService.remove_device(db, device.id)

            return {
                "success": True,
                "removed": removed,
            }
        except (LicenseNotFoundError, DeviceNotFoundError):
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            db.rollback()
            raise DatabaseError(f"Failed to deactivate extension: {str(exc)}") from exc

    @staticmethod
    def get_extension_status(db: Session, license_key: str) -> dict[str, Any]:
        """
        Retrieve the current license state for an extension client.

        Args:
            db: SQLAlchemy database session.
            license_key: License key to inspect.

        Returns:
            Dictionary with the current extension license status details.

        Raises:
            LicenseNotFoundError: If the license does not exist.
            InvalidDataError: If the license key is invalid.
            DatabaseError: If the database operation fails.
        """
        try:
            license_obj = LicenseService.get_license_by_key(db, license_key)
            return {
                "success": True,
                "license_status": license_obj.status,
                "expires_at": license_obj.expires_at,
                "plan": license_obj.plan.name,
                "product": license_obj.product.name,
                "customer": license_obj.customer.name,
                "max_devices": license_obj.plan.max_devices,
                "used_devices": len(license_obj.devices),
            }
        except LicenseNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            db.rollback()
            raise DatabaseError(f"Failed to fetch extension status: {str(exc)}") from exc

    @staticmethod
    def validate_extension_version(
        extension_version: str | None,
        minimum_version: str | None = None,
    ) -> dict[str, Any]:
        """
        Validate whether an extension version is supported.

        Args:
            extension_version: Version string reported by the extension.
            minimum_version: Optional minimum supported version override.

        Returns:
            Dictionary describing support state and whether an update is required.
        """
        current_version = extension_version.strip() if extension_version else ""
        minimum_supported_version = (
            minimum_version or getattr(settings, "MINIMUM_EXTENSION_VERSION", "1.0.0")
        ).strip()

        current_parts = ExtensionService._parse_version(current_version)
        minimum_parts = ExtensionService._parse_version(minimum_supported_version)

        supported = ExtensionService._is_version_supported(current_parts, minimum_parts)
        return {
            "supported": supported,
            "requires_update": not supported,
            "minimum_version": minimum_supported_version,
            "current_version": current_version,
        }

    @staticmethod
    def validate_browser(browser: str | None) -> str:
        """
        Validate that the browser is supported by the licensing platform.

        Args:
            browser: Browser name to validate.

        Returns:
            Canonical browser name used by the services.

        Raises:
            InvalidDataError: If the browser is missing or unsupported.
        """
        if not browser or not isinstance(browser, str) or not browser.strip():
            raise InvalidDataError("Browser is required")

        normalized = browser.strip().lower()
        if normalized not in ExtensionService.SUPPORTED_BROWSERS:
            supported = ", ".join(ExtensionService.SUPPORTED_BROWSERS.values())
            raise InvalidDataError(
                f"Unsupported browser '{browser}'. Supported browsers: {supported}"
            )

        return ExtensionService.SUPPORTED_BROWSERS[normalized]

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        """Parse a semantic version string into a comparable tuple."""
        if not version:
            return ()

        cleaned = version.strip().lstrip("vV")
        if not cleaned:
            return ()

        parts = []
        for raw_part in cleaned.split("."):
            digits = "".join(char for char in raw_part if char.isdigit())
            parts.append(int(digits) if digits else 0)

        return tuple(parts)

    @staticmethod
    def _is_version_supported(
        current_version: tuple[int, ...],
        minimum_version: tuple[int, ...],
    ) -> bool:
        """Compare two semantic version tuples."""
        if not current_version:
            return False

        max_length = max(len(current_version), len(minimum_version))
        padded_current = current_version + (0,) * (max_length - len(current_version))
        padded_minimum = minimum_version + (0,) * (max_length - len(minimum_version))

        return padded_current >= padded_minimum
