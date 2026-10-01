"""
Database Models for LOUD Platform Licensing System.

Includes models for Products, Customers, Licenses, Devices, Admin Users, and Activity Logs.
All models use SQLAlchemy with proper relationships and foreign keys.
"""

import secrets
from datetime import datetime, timedelta
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.config import settings
from app.database import Base
from app.constants import (
    LICENSE_STATUS_ACTIVE,
    PLAN_STATUS_ACTIVE,
    PRODUCT_STATUS_ACTIVE,
    ROLE_SUPPORT,
)
from app.utils.datetime_utils import get_current_time


def generate_product_api_key():
    """Generate unique product API key."""
    return f"lp_{secrets.token_urlsafe(32)}"


class AdminUser(Base):
    """Admin User Model - manages platform administrators."""
    
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    
    username = Column(String(100), unique=True, nullable=False, index=True)
    
    password_hash = Column(String(255), nullable=False)
    
    role = Column(String(50), default="support")  # owner, admin, support
    
    created_at = Column(
        DateTime,
        nullable=False,  # CRITICAL: Must not be nullable
        server_default=func.now(),  # Database-side default for new rows
    )


class Plan(Base):
    """Plan Model - represents subscription/licensing plans."""
    
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    
    duration_days = Column(Integer, nullable=False)  # Duration of plan in days
    
    max_devices = Column(Integer, default=1)  # Number of devices allowed per license
    
    price = Column(Float, default=0.0)  # Price in USD
    
    status = Column(String(50), default="active")  # active, inactive, retired
    
    created_at = Column(
        DateTime,
        nullable=False,  # CRITICAL: Must not be nullable
        server_default=func.now(),  # Database-side default for new rows
    )
    
    # Relationships
    licenses = relationship(
        "License",
        back_populates="plan"
    )


class Product(Base):
    """Product Model - represents software products in the platform."""
    
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    
    name = Column(String(150), nullable=False, index=True)
    
    slug = Column(String(150), unique=True, nullable=False, index=True)
    
    api_key = Column(String(255), unique=True, nullable=False, index=True, default=generate_product_api_key)
    
    description = Column(Text, nullable=True)
    
    version = Column(String(50), default="1.0.0")
    
    status = Column(String(50), default="active")  # active, archived, beta
    
    created_at = Column(
        DateTime,
        nullable=False,  # CRITICAL: Must not be nullable
        server_default=func.now(),  # Database-side default for new rows
    )
    
    # Relationships
    licenses = relationship(
        "License",
        back_populates="product",
        cascade="all, delete-orphan"
    )


class Customer(Base):
    """Customer Model - represents end users/customers."""
    
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    
    name = Column(String(150), nullable=False, index=True)
    
    email = Column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )
    
    phone = Column(String(20), nullable=True)
    
    notes = Column(Text, nullable=True)
    
    created_at = Column(
        DateTime,
        nullable=False,  # CRITICAL: Must not be nullable
        server_default=func.now(),  # Database-side default for new rows
    )
    
    # Relationships
    licenses = relationship(
        "License",
        back_populates="customer",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class License(Base):
    """License Model - represents issued licenses to customers."""
    
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)
    
    product_id = Column(
        Integer,
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    
    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )
    
    plan_id = Column(
        Integer,
        ForeignKey("plans.id"),
        nullable=False,
        index=True
    )

    license_key = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    status = Column(
        String(50),
        default=LICENSE_STATUS_ACTIVE,
        index=True,
    )  # active, suspended, revoked, expired
    
    created_at = Column(
        DateTime,
        nullable=False,  # CRITICAL: Must not be nullable
        server_default=func.now(),  # Database-side default for new rows
    )
    
    expires_at = Column(DateTime, nullable=False)
    
    activated_at = Column(DateTime, nullable=True)
    
    last_verified = Column(DateTime, nullable=True)
    
    activated_device_count = Column(Integer, default=0)
    
    # Relationships
    product = relationship("Product", back_populates="licenses")
    
    customer = relationship("Customer", back_populates="licenses")
    
    plan = relationship("Plan", back_populates="licenses", lazy="selectin")
    
    devices = relationship(
        "Device",
        back_populates="license",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    
    @property
    def devices_online(self) -> int:
        timeout_seconds = getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SECONDS", 300)
        cutoff = get_current_time() - timedelta(seconds=timeout_seconds)
        return sum(
            1
            for device in self.devices
            if not device.is_disabled and device.last_heartbeat_at is not None and device.last_heartbeat_at >= cutoff
        )

    @property
    def devices_offline(self) -> int:
        timeout_seconds = getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SECONDS", 300)
        cutoff = get_current_time() - timedelta(seconds=timeout_seconds)
        return sum(
            1
            for device in self.devices
            if not device.is_disabled and (device.last_heartbeat_at is None or device.last_heartbeat_at < cutoff)
        )

    @property
    def devices_disabled(self) -> int:
        return sum(1 for device in self.devices if device.is_disabled)

    @property
    def last_device_heartbeat_at(self):
        heartbeat_times = [device.last_heartbeat_at for device in self.devices if device.last_heartbeat_at]
        return max(heartbeat_times) if heartbeat_times else None

    @property
    def remaining_slots(self) -> int:
        max_devices = self.plan.max_devices if self.plan else 0
        return max(max_devices - len(self.devices), 0)

    @property
    def plan_max_devices(self) -> int:
        return self.plan.max_devices if self.plan else 0

    activity_logs = relationship(
        "ActivityLog",
        back_populates="license",
        cascade="all, delete-orphan"
    )


class Device(Base):
    __tablename__ = "devices"

    __table_args__ = (
        UniqueConstraint(
            "license_id",
            "device_uuid",
            name="uq_license_device",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    license_id = Column(
        Integer,
        ForeignKey("licenses.id"),
        nullable=False,
        index=True,
    )

    device_uuid = Column(String(255), nullable=False, index=True)
    device_fingerprint = Column(String(255), nullable=True, index=True)
    device_name = Column(String(255), nullable=True)
    browser = Column(String(50), nullable=False)  # Chrome, Edge, Firefox, etc.
    operating_system = Column(String(50), nullable=True)  # Windows, Mac, Linux
    extension_version = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    token_version = Column(Integer, nullable=False, default=0)
    first_activated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    last_verified_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    is_disabled = Column(Boolean, nullable=False, default=False)
    last_seen = Column(
        DateTime,
        nullable=False,  # CRITICAL: Must not be nullable
        server_default=func.now(),  # Database-side default for new rows
    )

    # Relationships
    license = relationship("License", back_populates="devices")

    @property
    def status(self) -> str:
        if self.is_disabled:
            return "disabled"

        if not self.last_heartbeat_at:
            return "offline"

        timeout_seconds = getattr(settings, "DEVICE_OFFLINE_TIMEOUT_SECONDS", 300)
        now = get_current_time()
        if now - self.last_heartbeat_at <= timedelta(seconds=timeout_seconds):
            return "online"

        return "offline"

    @property
    def license_status(self) -> str:
        return self.license.status if self.license is not None else "unknown"

    @property
    def product_name(self) -> str:
        return self.license.product.name if self.license is not None else "unknown"

    @property
    def customer_name(self) -> str:
        return self.license.customer.name if self.license is not None else "unknown"


class ActivityLog(Base):
    """Activity Log Model - tracks all license and device activities."""
    
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    license_id = Column(
        Integer,
        ForeignKey("licenses.id"),
        nullable=False,
        index=True
    )
    
    action = Column(String(100), nullable=False)  # activate, verify, extend, revoke, reset_device
    
    ip_address = Column(String(45), nullable=True)
    
    browser = Column(String(50), nullable=True)
    
    notes = Column(Text, nullable=True)
    
    timestamp = Column(
        DateTime,
        nullable=False,  # CRITICAL: Must not be nullable
        server_default=func.now(),  # Database-side default for new rows
        index=True,
    )
    
    # Relationships
    license = relationship("License", back_populates="activity_logs")