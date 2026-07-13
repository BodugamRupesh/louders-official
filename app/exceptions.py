"""
Custom Exceptions for LOUD Platform Licensing System.

All services raise these exceptions instead of returning None or error codes.
This enables clean error handling in routers.
"""


class LicenseServerException(Exception):
    """Base exception for all licensing system errors."""

    pass


class ResourceNotFoundError(LicenseServerException):
    """Raised when a requested resource cannot be found."""

    pass


class ValidationException(LicenseServerException):
    """Raised when request or business data is invalid."""

    pass


class AuthenticationException(LicenseServerException):
    """Raised when authentication fails."""

    pass


class AuthorizationException(LicenseServerException):
    """Raised when authorization fails."""

    pass


class DatabaseException(LicenseServerException):
    """Raised when a database operation fails."""

    pass


class BusinessRuleException(LicenseServerException):
    """Raised when a business rule is violated."""

    pass


class ProductNotFoundError(ResourceNotFoundError):
    """Raised when a product is not found."""

    pass


class CustomerNotFoundError(ResourceNotFoundError):
    """Raised when a customer is not found."""

    pass


class LicenseNotFoundError(ResourceNotFoundError):
    """Raised when a license is not found."""

    pass


class DeviceNotFoundError(ResourceNotFoundError):
    """Raised when a device is not found."""

    pass


class PlanNotFoundError(ResourceNotFoundError):
    """Raised when a plan is not found."""

    pass


class AdminUserNotFoundError(ResourceNotFoundError):
    """Raised when an admin user is not found."""

    pass


class LicenseExpiredError(BusinessRuleException):
    """Raised when trying to verify an expired license."""

    pass


class LicenseRevokedError(BusinessRuleException):
    """Raised when trying to use a revoked license."""

    pass


class LicenseSuspendedError(BusinessRuleException):
    """Raised when trying to verify a suspended license."""

    pass


class DeviceLimitExceededError(BusinessRuleException):
    """Raised when device limit for a license is exceeded."""

    pass


class InvalidProductKeyError(ValidationException):
    """Raised when product API key is invalid or missing."""

    pass


class InvalidCredentialsError(AuthenticationException):
    """Raised when admin credentials are invalid."""

    pass


class UnauthorizedAdminError(AuthorizationException):
    """Raised when admin doesn't have required role."""

    pass


class InvalidTokenError(AuthenticationException):
    """Raised when JWT token is invalid or expired."""

    pass


class DuplicateProductError(ValidationException):
    """Raised when trying to create product with duplicate slug or api_key."""

    pass


class DuplicateCustomerError(ValidationException):
    """Raised when trying to create customer with a duplicate email."""

    pass


class DuplicateAdminError(ValidationException):
    """Raised when trying to create admin with duplicate username."""

    pass


class InvalidLicenseKeyFormatError(ValidationException):
    """Raised when license key format is invalid."""

    pass


class OperationNotAllowedError(BusinessRuleException):
    """Raised when an operation is not allowed on the license (e.g., revoke already revoked)."""

    pass


class InvalidDataError(ValidationException):
    """Raised when provided data is invalid."""

    pass


class DeviceDisabledError(InvalidDataError):
    """Raised when a device has been disabled and cannot perform the requested operation."""

    pass


class PlanInUseException(InvalidDataError, BusinessRuleException):
    """Raised when a plan is referenced by existing licenses and cannot be deleted."""

    pass


class DatabaseError(DatabaseException):
    """Raised when database operation fails."""

    pass
