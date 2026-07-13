"""
Shared constants for the LOUD Platform Licensing System.
"""

# ==========================================================
# Admin Roles
# ==========================================================

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_SUPPORT = "support"

ADMIN_ROLES = (
    ROLE_OWNER,
    ROLE_ADMIN,
    ROLE_SUPPORT,
)

# ==========================================================
# Plan Status
# ==========================================================

PLAN_STATUS_ACTIVE = "active"
PLAN_STATUS_INACTIVE = "inactive"
PLAN_STATUS_RETIRED = "retired"

PLAN_STATUSES = (
    PLAN_STATUS_ACTIVE,
    PLAN_STATUS_INACTIVE,
    PLAN_STATUS_RETIRED,
)

# ==========================================================
# Product Status
# ==========================================================

PRODUCT_STATUS_ACTIVE = "active"
PRODUCT_STATUS_ARCHIVED = "archived"
PRODUCT_STATUS_BETA = "beta"

PRODUCT_STATUSES = (
    PRODUCT_STATUS_ACTIVE,
    PRODUCT_STATUS_ARCHIVED,
    PRODUCT_STATUS_BETA,
)

# ==========================================================
# License Status
# ==========================================================

LICENSE_STATUS_ACTIVE = "active"
LICENSE_STATUS_SUSPENDED = "suspended"
LICENSE_STATUS_REVOKED = "revoked"
LICENSE_STATUS_EXPIRED = "expired"

LICENSE_STATUSES = (
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_SUSPENDED,
    LICENSE_STATUS_REVOKED,
    LICENSE_STATUS_EXPIRED,
)

# ==========================================================
# Extension Error Codes
# ==========================================================

from enum import Enum


class ExtensionErrorCode(str, Enum):
    """Standardized error codes for extension responses."""
    
    # Authentication & Authorization
    INVALID_PRODUCT_KEY = "INVALID_PRODUCT_KEY"
    INVALID_LICENSE = "INVALID_LICENSE"
    INVALID_DEVICE = "INVALID_DEVICE"
    UNAUTHORIZED_DEVICE = "UNAUTHORIZED_DEVICE"
    
    # Token errors
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_MISSING = "TOKEN_MISSING"
    
    # License errors
    LICENSE_EXPIRED = "LICENSE_EXPIRED"
    LICENSE_REVOKED = "LICENSE_REVOKED"
    LICENSE_SUSPENDED = "LICENSE_SUSPENDED"
    LICENSE_NOT_ACTIVATED = "LICENSE_NOT_ACTIVATED"
    
    # Device errors
    DEVICE_LIMIT_REACHED = "DEVICE_LIMIT_REACHED"
    DEVICE_NOT_REGISTERED = "DEVICE_NOT_REGISTERED"
    DEVICE_LIMIT_EXCEEDED = "DEVICE_LIMIT_EXCEEDED"
    
    # Validation errors
    PRODUCT_MISMATCH = "PRODUCT_MISMATCH"
    INVALID_REQUEST = "INVALID_REQUEST"
    
    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"