from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# -------------------------
# License Creation
# -------------------------

class LicenseCreate(BaseModel):
    customer_name: str
    discord_username: Optional[str] = None
    email: Optional[EmailStr] = None
    plan: str
    days: int
    notes: Optional[str] = None


# -------------------------
# Activation
# -------------------------

class LicenseActivate(BaseModel):
    license_key: str
    device_id: str


# -------------------------
# Verification
# -------------------------

class LicenseVerify(BaseModel):
    license_key: str
    device_id: str


# -------------------------
# Extend License
# -------------------------

class LicenseExtend(BaseModel):
    license_key: str
    days: int


# -------------------------
# Reset Device
# -------------------------

class DeviceReset(BaseModel):
    license_key: str


# -------------------------
# Revoke License
# -------------------------

class LicenseRevoke(BaseModel):
    license_key: str


# -------------------------
# Search
# -------------------------

class LicenseSearch(BaseModel):
    query: str


# -------------------------
# Response
# -------------------------

class LicenseResponse(BaseModel):
    success: bool
    message: str
    license_key: Optional[str] = None
    expires_at: Optional[datetime] = None


# -------------------------
# Admin Login
# -------------------------

class AdminLogin(BaseModel):
    username: str
    password: str