"""
Tests specifically validating the 8 test requirements for License Device Count.
"""

import os
import shutil
import tempfile
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
import app.database as app_db
from app.models import AdminUser, Product, Customer, License, Plan, Device
from app.services.auth_service import AuthService
from app.utils.datetime_utils import get_current_time


@pytest.fixture(autouse=True)
def isolate_test_database():
    """
    Isolate test database using the temporary sandbox pattern from verify_full_lifecycle.py.
    Ensures that test execution never reads or writes from the live production database.
    """
    temp_dir = tempfile.mkdtemp(prefix="louders_test_")
    test_db = os.path.join(temp_dir, "test_licenses.db").replace("\\", "/")

    # Copy current production db to initialize test db with production schema and seed
    prod_db = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "licenses.db"))
    if os.path.exists(prod_db):
        shutil.copy2(prod_db, test_db)

    orig_db_url = os.environ.get("DATABASE_URL")
    orig_admin_user = os.environ.get("ADMIN_USERNAME")
    orig_admin_pass = os.environ.get("ADMIN_PASSWORD")

    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["ADMIN_USERNAME"] = "hanzoo"
    os.environ["ADMIN_PASSWORD"] = "Hanzoo@2511"

    test_engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    orig_engine = app_db.engine
    orig_session_local = app_db.SessionLocal
    app_db.engine = test_engine
    app_db.SessionLocal = TestSessionLocal

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield

    app.dependency_overrides.pop(get_db, None)
    app_db.engine = orig_engine
    app_db.SessionLocal = orig_session_local
    test_engine.dispose()

    if orig_db_url is not None:
        os.environ["DATABASE_URL"] = orig_db_url
    else:
        os.environ.pop("DATABASE_URL", None)

    if orig_admin_user is not None:
        os.environ["ADMIN_USERNAME"] = orig_admin_user
    else:
        os.environ.pop("ADMIN_USERNAME", None)

    if orig_admin_pass is not None:
        os.environ["ADMIN_PASSWORD"] = orig_admin_pass
    else:
        os.environ.pop("ADMIN_PASSWORD", None)

    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


client = TestClient(app)


def test_device_count_full_lifecycle():
    token = AuthService.create_access_token(
        data={"sub": "hanzoo", "role": "owner", "admin_id": 1}
    )
    headers = {"Authorization": f"Bearer {token}"}
    default_product_key = "lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU"

    # Step 0: Create Customer with Multi-device Plan (Plan 1 is max 1 or we can check plans)
    plans_res = client.get("/api/v1/plans", headers=headers)
    assert plans_res.status_code == 200
    plans = plans_res.json()["data"]["plans"]
    
    # Pick or create a plan with at least 2 max_devices
    multi_plan = next((p for p in plans if p["max_devices"] >= 2), None)
    if not multi_plan:
        plan_create = client.post(
            "/api/v1/plans",
            headers=headers,
            json={
                "product_id": 1,
                "name": f"Multi Device Plan {int(get_current_time().timestamp())}",
                "duration_days": 30,
                "max_devices": 3,
                "price": 99.0,
            }
        )
        assert plan_create.status_code == 200, plan_create.text
        plan_id = plan_create.json()["data"]["plan"]["id"]
    else:
        plan_id = multi_plan["id"]

    cust_email = f"dev_count_test_{int(get_current_time().timestamp())}@louders.io"
    cust_res = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Device Count User", "email": cust_email, "phone": "+100000000"}
    )
    assert cust_res.status_code == 201
    cust_id = cust_res.json()["data"]["customer"]["id"]

    try:
        # TEST 1 — New license: Create a license. Expected: Devices: 0 before activation
        lic_res = client.post(
            "/api/v1/licenses",
            headers=headers,
            json={"product_id": 1, "customer_id": cust_id, "plan_id": plan_id}
        )
        assert lic_res.status_code == 200
        license_key = lic_res.json()["data"]["license"]["license_key"]
        lic_id = lic_res.json()["data"]["license"]["id"]

        # Check list endpoint
        list_res = client.get("/api/v1/licenses", headers=headers)
        assert list_res.status_code == 200
        lic_in_list = next((l for l in list_res.json()["data"]["licenses"] if l["id"] == lic_id), None)
        assert lic_in_list is not None
        assert lic_in_list["activated_device_count"] == 0, f"Expected 0, got {lic_in_list['activated_device_count']}"

        # TEST 2 — Activate on Device A: Expected Devices: 1
        device_a_uuid = f"device-a-{int(get_current_time().timestamp())}"
        act_res = client.post(
            "/api/v1/extensions/activate",
            json={
                "product_api_key": default_product_key,
                "license_key": license_key,
                "customer_email": cust_email,
                "device_uuid": device_a_uuid,
                "browser": "Chrome",
                "operating_system": "Windows",
                "extension_version": "2.0.0"
            }
        )
        assert act_res.status_code == 200, act_res.text
        act_data = act_res.json()
        assert act_data["success"] is True
        ext_token_a = act_data["extension_token"]

        # Admin panel check
        list_res = client.get("/api/v1/licenses", headers=headers)
        lic_in_list = next((l for l in list_res.json()["data"]["licenses"] if l["id"] == lic_id), None)
        assert lic_in_list is not None
        assert lic_in_list["activated_device_count"] == 1, f"Expected 1 device, got {lic_in_list['activated_device_count']}"

        # TEST 3 — Refresh: Reload admin page/endpoint. Expected: Devices: 1 persists
        refresh_res = client.get("/api/v1/licenses", headers=headers)
        lic_refreshed = next((l for l in refresh_res.json()["data"]["licenses"] if l["id"] == lic_id), None)
        assert lic_refreshed["activated_device_count"] == 1

        # Also check single get endpoint
        single_res = client.get(f"/api/v1/licenses/{lic_id}", headers=headers)
        assert single_res.status_code == 200
        assert single_res.json()["data"]["license"]["activated_device_count"] == 1

        # TEST 4 — Verify again & Heartbeat from Device A: Expected: Devices: 1 (not 2)
        ver_res = client.post(
            "/api/v1/extensions/verify",
            json={
                "product_api_key": default_product_key,
                "license_key": license_key,
                "device_uuid": device_a_uuid,
                "browser": "Chrome",
                "extension_token": ext_token_a
            }
        )
        assert ver_res.status_code == 200
        assert ver_res.json()["activated_devices"] == 1

        hb_res = client.post(
            "/api/v1/extensions/heartbeat",
            json={
                "product_api_key": default_product_key,
                "license_key": license_key,
                "device_uuid": device_a_uuid,
                "browser": "Chrome",
                "operating_system": "Windows",
                "extension_version": "2.0.0",
                "extension_token": ext_token_a
            }
        )
        assert hb_res.status_code == 200

        # Verify device count is still 1
        list_res = client.get("/api/v1/licenses", headers=headers)
        lic_in_list = next((l for l in list_res.json()["data"]["licenses"] if l["id"] == lic_id), None)
        assert lic_in_list["activated_device_count"] == 1, f"Expected 1, got {lic_in_list['activated_device_count']}"

        # TEST 5 — Second device: Activate Device B. Expected: Devices: 2
        device_b_uuid = f"device-b-{int(get_current_time().timestamp())}"
        act_b_res = client.post(
            "/api/v1/extensions/activate",
            json={
                "product_api_key": default_product_key,
                "license_key": license_key,
                "customer_email": cust_email,
                "device_uuid": device_b_uuid,
                "browser": "Edge",
                "operating_system": "Windows",
                "extension_version": "2.0.0"
            }
        )
        assert act_b_res.status_code == 200, act_b_res.text
        assert act_b_res.json()["success"] is True

        # Check list endpoint
        list_res = client.get("/api/v1/licenses", headers=headers)
        lic_in_list = next((l for l in list_res.json()["data"]["licenses"] if l["id"] == lic_id), None)
        assert lic_in_list["activated_device_count"] == 2, f"Expected 2, got {lic_in_list['activated_device_count']}"

        # TEST 6 — Refresh again: Expected: Devices: 2 persists
        refresh_res = client.get("/api/v1/licenses", headers=headers)
        lic_refreshed = next((l for l in refresh_res.json()["data"]["licenses"] if l["id"] == lic_id), None)
        assert lic_refreshed["activated_device_count"] == 2

        # TEST 7 — Deactivation: Deactivate Device A using existing deactivation endpoint. Expected: Devices: 1
        deact_res = client.post(
            "/api/v1/extensions/deactivate",
            json={
                "product_api_key": default_product_key,
                "license_key": license_key,
                "device_uuid": device_a_uuid,
            }
        )
        assert deact_res.status_code == 200, deact_res.text
        assert deact_res.json()["success"] is True

        list_res = client.get("/api/v1/licenses", headers=headers)
        lic_in_list = next((l for l in list_res.json()["data"]["licenses"] if l["id"] == lic_id), None)
        assert lic_in_list["activated_device_count"] == 1, f"Expected 1 after deactivation, got {lic_in_list['activated_device_count']}"

        # TEST 8 — Existing licenses: Test licenses created previously (e.g. License 20)
        # License 20 has 3 devices in devices table
        list_res = client.get("/api/v1/licenses", headers=headers)
        lic_20 = next((l for l in list_res.json()["data"]["licenses"] if l["id"] == 20), None)
        if lic_20:
            assert lic_20["activated_device_count"] == 3, f"Expected 3 for license 20, got {lic_20['activated_device_count']}"

        # License 21 device count matches devices table
        lic_21 = next((l for l in list_res.json()["data"]["licenses"] if l["id"] == 21), None)
        if lic_21:
            with app_db.engine.connect() as conn:
                dev_count = conn.execute(text("SELECT COUNT(*) FROM devices WHERE license_id = 21")).scalar()
            assert lic_21["activated_device_count"] == dev_count, f"Expected {dev_count} for license 21, got {lic_21['activated_device_count']}"

    finally:
        # Cleanup test customer
        try:
            client.delete(f"/api/v1/customers/{cust_id}", headers=headers)
        except Exception:
            pass
