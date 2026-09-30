"""
Pydantic Schemas for LOUD Platform Licensing System.

Includes Create, Update, Response, and Search schemas for all models.
Separate classes for request/response validation.
"""

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.constants import (
    ROLE_SUPPORT,
    PLAN_STATUS_ACTIVE,
    PRODUCT_STATUS_ACTIVE,
)

AdminRole = Literal["owner", "admin", "support"]
BrowserType = Literal["Chrome", "Edge", "Firefox", "Brave", "Opera"]
PlanStatus = Literal["active", "inactive", "retired"]
ProductStatus = Literal["active", "archived", "beta"]
LicenseStatus = Literal["active", "suspended", "revoked", "expired"]
VERSION_PATTERN = r"^\d+\.\d+\.\d+$"
LICENSE_KEY_PATTERN = r"^[A-Za-z0-9-]+$"


# =====================================================================
# ADMIN USER SCHEMAS
# =====================================================================

class AdminUserCreate(BaseModel):
    """Schema for creating a new admin user."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    role: AdminRole = Field(default=ROLE_SUPPORT)


class AdminUserResponse(BaseModel):
    """Schema for admin user response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: AdminRole
    created_at: datetime


class AdminUpdateRequest(BaseModel):
    """Request schema for updating an admin user."""

    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )
    role: Optional[AdminRole] = Field(None, description="owner, admin, or support")


class ChangePasswordRequest(BaseModel):
    """Request schema for changing the current admin password."""

    old_password: str = Field(..., min_length=1)
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )


class ResetPasswordRequest(BaseModel):
    """Schema for resetting another admin password."""

    admin_id: int = Field(..., ge=1)
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )


# =====================================================================
# PLAN SCHEMAS
# =====================================================================

class PlanCreate(BaseModel):
    """Schema for creating a new plan."""
    
    name: str = Field(..., min_length=1, max_length=100)
    duration_days: int = Field(..., ge=1)
    max_devices: int = Field(1, ge=1)
    price: float = Field(0.0, ge=0)
    status: PlanStatus = Field(
        default=PLAN_STATUS_ACTIVE,
)


class PlanUpdate(BaseModel):
    """Schema for updating a plan."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    duration_days: Optional[int] = Field(None, ge=1)
    max_devices: Optional[int] = Field(None, ge=1)
    price: Optional[float] = Field(None, ge=0)
    status: Optional[PlanStatus] = None


class PlanResponse(BaseModel):
    """Schema for plan response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    duration_days: int
    max_devices: int
    price: float
    status: PlanStatus
    created_at: datetime


class PlanStatusUpdate(BaseModel):
    """Schema for plan status updates."""

    status: PlanStatus = Field(..., description="New plan status")


# =====================================================================
# PRODUCT SCHEMAS
# =====================================================================

class ProductCreate(BaseModel):
    """Schema for creating a new product."""
    
    name: str = Field(..., min_length=1, max_length=150)
    slug: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    version: str = Field(
        default="1.0.0",
        pattern=VERSION_PATTERN,
)
    status: ProductStatus = Field(
        default=PRODUCT_STATUS_ACTIVE,
)


class ProductUpdate(BaseModel):
    """Schema for updating a product."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    slug: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    version: Optional[str] = Field(
        None,
        pattern=VERSION_PATTERN,
)
    status: Optional[ProductStatus] = None


class ProductResponse(BaseModel):
    """Schema for product response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    api_key: str
    description: Optional[str] = None
    version: str
    status: ProductStatus
    created_at: datetime


class ProductStatusUpdate(BaseModel):
    """Schema for updating product status."""

    status: ProductStatus = Field(..., description="New product status")


# =====================================================================
# CUSTOMER SCHEMAS
# =====================================================================

class CustomerCreate(BaseModel):
    """Schema for creating a new customer."""

    name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr

    phone: Optional[str] = Field(
        None,
        min_length=10,
        max_length=20,
    )

    notes: Optional[str] = Field(
        None,
        max_length=1000,
    )


class CustomerUpdate(BaseModel):
    """Schema for updating an existing customer."""

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    email: Optional[EmailStr] = None

    phone: Optional[str] = Field(
        None,
        min_length=10,
        max_length=20,
    )

    notes: Optional[str] = Field(
        None,
        max_length=1000,
    )


class CustomerResponse(BaseModel):
    """Schema for customer response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


# =====================================================================
# DEVICE SCHEMAS
# =====================================================================

class DeviceCreate(BaseModel):
    """Schema for registering a new device."""

    device_uuid: str = Field(
        ...,
        min_length=8,
        max_length=255,
    )

    browser: BrowserType

    operating_system: Optional[str] = None
    extension_version: Optional[str] = None


class DeviceResponse(BaseModel):
    """Schema for device response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    license_id: int
    device_uuid: str
    device_fingerprint: Optional[str] = None
    device_name: Optional[str] = None
    browser: BrowserType
    operating_system: Optional[str] = None
    extension_version: Optional[str] = None
    ip_address: Optional[str] = None
    token_version: int
    first_activated_at: datetime
    last_verified_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    last_seen: datetime
    status: str
    license_status: str
    product_name: str
    customer_name: str


class RegisterDeviceRequest(BaseModel):
    """Request schema for device registration."""

    license_id: int = Field(..., ge=1)

    device_uuid: str = Field(
        ...,
        min_length=8,
        max_length=255,
    )

    browser: BrowserType

    operating_system: Optional[str] = None
    extension_version: Optional[str] = None
    device_name: Optional[str] = None
    ip_address: Optional[str] = None

class UpdateDeviceRequest(BaseModel):
    """Request schema for updating device information."""

    browser: Optional[BrowserType] = None
    operating_system: Optional[str] = None
    extension_version: Optional[str] = None
    device_name: Optional[str] = None
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None


class ResetDeviceRequest(BaseModel):
    """Request schema for resetting a device."""

    license_id: int = Field(..., ge=1)
    device_uuid: str = Field(
        ...,
        min_length=8,
        max_length=255,
)


# =====================================================================
# LICENSE SCHEMAS
# =====================================================================

class LicenseCreate(BaseModel):
    """Schema for creating a new license."""

    model_config = ConfigDict(from_attributes=True)

    product_id: int = Field(..., ge=1)
    customer_id: int = Field(..., ge=1)
    plan_id: int = Field(..., ge=1)


class LicenseUpdate(BaseModel):
    """Schema for updating a license."""

    plan_id: Optional[int] = Field(None, ge=1)
    status: Optional[LicenseStatus] = None


class LicenseResponse(BaseModel):
    """Schema for license response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    customer_id: int
    plan_id: int
    license_key: str
    status: LicenseStatus
    created_at: datetime
    expires_at: datetime
    activated_at: Optional[datetime] = None
    last_verified: Optional[datetime] = None
    activated_device_count: int
    devices_online: int
    devices_offline: int
    devices_disabled: int
    last_device_heartbeat_at: Optional[datetime] = None
    remaining_slots: int
    plan_max_devices: int


class LicenseDetailedResponse(BaseModel):
    """Schema for detailed license response with relationships."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    license_key: str
    status: LicenseStatus
    created_at: datetime
    expires_at: datetime
    activated_at: Optional[datetime] = None
    last_verified: Optional[datetime] = None
    activated_device_count: int
    product: ProductResponse
    customer: CustomerResponse
    plan: PlanResponse
    devices: List[DeviceResponse] = Field(default_factory=list)


# =====================================================================
# LICENSE OPERATIONS
# =====================================================================

class LicenseActivate(BaseModel):
    """Schema for activating a license."""

    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
    )

    device_uuid: str = Field(
        ...,
        min_length=8,
        max_length=255,
    )

    browser: BrowserType

    operating_system: Optional[str] = None
    extension_version: Optional[str] = None


class LicenseVerify(BaseModel):
    """Schema for verifying a license."""

    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
    )

    device_uuid: str = Field(
        ...,
        min_length=8,
        max_length=255,
    )

    browser: Optional[BrowserType] = None


class LicenseExtend(BaseModel):
    """Schema for extending a license."""

    model_config = ConfigDict(from_attributes=True)

    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
    )
    plan_id: int = Field(..., ge=1)  # New plan to extend with


class ExtensionActivateRequest(LicenseActivate):
    """Request schema for extension activation."""

    product_api_key: str = Field(
        ...,
        min_length=1,
        description="Product API key supplied by the extension client.",
        example="lp_prod_12345abcdef",
    )
    device_fingerprint: Optional[str] = Field(
        None,
        description="Optional stable device fingerprint supplied by the extension.",
        example="fingerprint-0123456789abcdef",
    )
    customer_email: EmailStr = Field(
        ...,
        description="Customer email as reported by the extension/browser to validate ownership.",
        example="user@example.com",
    )


class ExtensionVerifyRequest(LicenseVerify):
    """Request schema for extension license verification."""

    product_api_key: str = Field(
        ...,
        min_length=1,
        description="Product API key supplied by the extension client.",
        example="lp_prod_12345abcdef",
    )
    extension_token: Optional[str] = Field(
        None,
        description="Optional extension session JWT to validate alongside license checks.",
    )


class ExtensionExtendRequest(BaseModel):
    """Request schema for extension license extension."""

    product_api_key: str = Field(
        ...,
        min_length=1,
        description="Product API key supplied by the extension client.",
        example="lp_prod_12345abcdef",
    )
    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
        example="LP-26-8QX2-KM7P-H9TW",
    )
    plan_id: int = Field(
        ...,
        ge=1,
        example=1,
    )


class LicenseRevoke(BaseModel):
    """Schema for revoking a license."""
    
    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
)
    reason: Optional[str] = None


class LicenseResetDevice(BaseModel):
    """Schema for resetting a license device."""

    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
        pattern=LICENSE_KEY_PATTERN,
    )
    device_uuid: Optional[str] = None


# =====================================================================
# ACTIVITY LOG SCHEMAS
# =====================================================================

class ActivityLogResponse(BaseModel):
    """Schema for activity log response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    license_id: int
    action: str
    ip_address: Optional[str] = None
    browser: Optional[str] = None
    notes: Optional[str] = None
    timestamp: datetime


class ExtensionHeartbeatRequest(BaseModel):
    """Request schema for a device heartbeat update."""

    product_api_key: str = Field(
        ...,
        min_length=1,
        description="Product API key supplied by the extension client.",
        example="lp_prod_12345abcdef",
    )
    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
        example="LP-26-8QX2-KM7P-H9TW",
    )

    device_uuid: str = Field(
        ...,
        min_length=8,
        max_length=255,
        example="device-uuid-abc123",
    )

    browser: BrowserType
    operating_system: Optional[str] = None
    extension_version: Optional[str] = None
    extension_token: Optional[str] = Field(
        None,
        description="Optional extension session JWT token for validation.",
    )

class ExtensionDeactivateRequest(BaseModel):
    """Request schema for deactivating a device."""

    product_api_key: str = Field(
        ...,
        min_length=1,
        description="Product API key supplied by the extension client.",
        example="lp_prod_12345abcdef",
    )
    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
    )

    device_uuid: str = Field(
        ...,
        min_length=8,
        max_length=255,
    )


class LicenseReactivate(BaseModel):
    """Request schema for reactivating a license."""

    license_key: str = Field(
        ...,
        min_length=16,
        max_length=64,
    )

# =====================================================================
# AUTHENTICATION SCHEMAS
# =====================================================================

class AdminLogin(BaseModel):
    """Schema for admin login."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )


class TokenResponse(BaseModel):
    """Schema for token response."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    """Schema for authentication response."""
    
    success: bool
    message: str
    access_token: Optional[str] = None
    token_type: Optional[str] = None


# =====================================================================
# API RESPONSE SCHEMAS
# =====================================================================

class SuccessResponse(BaseModel):
    """Generic success response."""
    
    success: bool = True
    message: str
    data: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Generic error response."""
    
    success: bool = False
    message: str
    error_code: Optional[str] = None


# =====================================================================
# EXTENSION API RESPONSES
# =====================================================================


class ExtensionActivationResponse(BaseModel):
    """Response to extension activation request."""
    
    success: bool
    license_key: str
    extension_token: str
    expires_in_seconds: int
    activated_at: datetime
    expires_at: datetime
    device_id: int
    max_devices: int
    
    model_config = ConfigDict(from_attributes=True)


class ExtensionVerifyResponse(BaseModel):
    """Response to extension verify request."""
    
    success: bool
    license_key: str
    status: str
    activated: bool
    expires_at: datetime
    days_remaining: int
    max_devices: int
    activated_devices: int
    current_device_registered: bool
    
    model_config = ConfigDict(from_attributes=True)


class ExtensionExtendResponse(BaseModel):
    """Response to extend license request."""
    
    success: bool
    license_key: str
    new_expiry_date: datetime
    days_added: int
    expires_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ExtensionErrorResponse(BaseModel):
    """Standardized error response for extension endpoints."""
    
    success: bool = False
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)


class ExtensionHeartbeatResponse(BaseModel):
    """Response to extension heartbeat request."""
    
    success: bool
    license_status: str
    days_remaining: int
    last_checked_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ExtensionDeactivateResponse(BaseModel):
    """Response to extension deactivate request."""
    
    success: bool
    message: str
    license_key: str
    device_uuid: str
    device_removed: bool
    remaining_devices: int
    license_status: str
    
    model_config = ConfigDict(from_attributes=True)