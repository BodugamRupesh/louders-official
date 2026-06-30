import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import License


class LicenseService:

    @staticmethod
    def generate_license_key():

        parts = []

        for _ in range(4):
            parts.append(secrets.token_hex(2).upper())

        return "LOUD-PRO-" + "-".join(parts)

    @staticmethod
    def create_license(db: Session, data):

        key = LicenseService.generate_license_key()

        expiry = datetime.utcnow() + timedelta(days=data.days)

        license_obj = License(
            license_key=key,
            customer_name=data.customer_name,
            discord_username=data.discord_username,
            email=data.email,
            plan=data.plan,
            notes=data.notes,
            expires_at=expiry,
            is_active=True
        )

        db.add(license_obj)
        db.commit()
        db.refresh(license_obj)

        return license_obj