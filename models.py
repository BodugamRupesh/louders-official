from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from database import Base


class License(Base):
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, index=True)

    # License
    license_key = Column(String, unique=True, index=True, nullable=False)

    # Customer
    customer_name = Column(String, nullable=True)
    discord_username = Column(String, nullable=True)
    email = Column(String, nullable=True)

    # Plan
    plan = Column(String, default="Monthly")

    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_verified = Column(DateTime, nullable=True)

    # Device
    device_id = Column(String, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Admin notes
    notes = Column(String, nullable=True)