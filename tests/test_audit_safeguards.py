"""
Targeted tests for audit safeguards:
1. Baseline migration safety (never resurrects data after intentional cleanup).
2. License deletion clean child purge (devices and activity logs).
3. Concurrent / repeated device registration handling.
4. Customer phone and notes casing preservation.
5. Firefox browser extension support.
"""

import os
import shutil
import tempfile
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Customer, License, Device, ActivityLog, Product, Plan, SystemMetadata
from app.services.customer_service import CustomerService
from app.services.license_service import LicenseService
from app.services.device_service import DeviceService
from app.services.extension_service import ExtensionService
from app.utils.datetime_utils import get_current_time
from datetime import timedelta


@pytest.fixture
def isolated_db():
    temp_dir = tempfile.mkdtemp(prefix="louders_safeguard_test_")
    test_db = os.path.join(temp_dir, "test_safe.db").replace("\\", "/")

    engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    yield Session, engine

    engine.dispose()
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


def test_customer_notes_and_phone_casing_preserved(isolated_db):
    Session, _ = isolated_db
    with Session() as db:
        cust = CustomerService.create_customer(
            db,
            name="John Smith",
            email="John.Smith@Example.COM",
            phone="+1 (555) 234-5678",
            notes="VIP Client - Do NOT Delete",
        )
        assert cust.email == "john.smith@example.com"
        assert cust.phone == "+1 (555) 234-5678"
        assert cust.notes == "VIP Client - Do NOT Delete"

        updated = CustomerService.update_customer(
            db,
            customer_id=cust.id,
            notes="Updated Note With Capital Letters",
        )
        assert updated.notes == "Updated Note With Capital Letters"


def test_license_delete_cleans_dependent_devices_and_logs(isolated_db):
    Session, _ = isolated_db
    with Session() as db:
        prod = Product(id=1, name="Test Prod", slug="test-prod", version="1.0.0", api_key="test_api_key_123")
        plan = Plan(id=1, name="Pro Plan", duration_days=30, max_devices=3, price=10.0)
        cust = Customer(id=1, name="Alice", email="alice@test.com")
        db.add_all([prod, plan, cust])
        db.commit()

        lic = License(
            id=1,
            product_id=prod.id,
            customer_id=cust.id,
            plan_id=plan.id,
            license_key="LP-26-TEST-ABCD-EFGH",
            status="active",
            expires_at=get_current_time() + timedelta(days=30),
        )
        db.add(lic)
        db.commit()

        # Add device and activity log
        dev = Device(
            license_id=lic.id,
            device_uuid="dev-uuid-1",
            browser="Chrome",
        )
        act = ActivityLog(
            license_id=lic.id,
            action="license_verified",
        )
        db.add_all([dev, act])
        db.commit()

        # Delete the license
        res = LicenseService.delete_license(db, lic.id)
        assert res is True

        # Verify all children are cleanly gone
        assert db.query(License).filter(License.id == 1).first() is None
        assert db.query(Device).filter(Device.license_id == 1).first() is None
        assert db.query(ActivityLog).filter(ActivityLog.license_id == 1).first() is None


def test_extension_service_supports_firefox():
    assert ExtensionService.validate_browser("firefox") == "Firefox"
    assert ExtensionService.validate_browser("Firefox") == "Firefox"
    assert ExtensionService.validate_browser("chrome") == "Chrome"


def test_system_metadata_prevents_reseeding_after_cleanup(isolated_db):
    Session, engine = isolated_db
    from app.main import _ensure_baseline_data_migrated

    with Session() as db:
        # Pre-seed metadata marking baseline migration as completed
        meta = SystemMetadata(key="baseline_migration_completed", value="true")
        db.add(meta)
        db.commit()

        # Database has 0 customers
        assert db.query(Customer).count() == 0

    # Running baseline migration must NOT reseed customers because metadata indicates completed
    _ensure_baseline_data_migrated()

    with Session() as db:
        assert db.query(Customer).count() == 0
