from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text
)

from app.database import Base


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)

    # License Information
    license_key = Column(String(64), unique=True, nullable=False, index=True)

    plan = Column(String(50), nullable=False)

    is_active = Column(Boolean, default=True)

    # Customer Information
    customer_name = Column(String(100), nullable=False)

    discord_username = Column(String(100), nullable=True)

    email = Column(String(150), nullable=True)

    # Device Lock
    device_id = Column(String(255), nullable=True)

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)

    expires_at = Column(DateTime, nullable=False)

    last_verified = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)