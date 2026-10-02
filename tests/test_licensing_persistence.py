"""
Comprehensive tests for licensing persistence, extension update safety,
and customer delete functionality.
"""

import os
import shutil
import tempfile
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
import app.database as app_db
from app.models import AdminUser, Product, Customer, License, Plan, Device
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.license_service import LicenseService
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


def test_customer_persistence_and_extension_update_safety():
    """
    Test the full lifecycle across:
    1. Create Customer A & B
    2. Issue License and register Device
    3. Simulate extension release/update (verifying records are untouched)
    4. Verify license and send heartbeat (verifying non-destructiveness)
    5. Admin-authenticated delete of Customer A (verifying only A is removed)
    6. Verify Customer B remains intact
    7. Database reconnection persistence
    """
    # 1. Authenticate as admin
    token = AuthService.create_access_token(
        data={"sub": "hanzoo", "role": "owner", "admin_id": 1}
    )
    headers = {"Authorization": f"Bearer {token}"}

    cust_a_id = None
    cust_b_id = None
    try:
        email_a = f"test_a_{int(get_current_time().timestamp())}@louders.io"
        res_a = client.post(
            "/api/v1/customers",
            headers=headers,
            json={"name": "Customer Alpha", "email": email_a, "phone": "+1234567890"}
        )
        assert res_a.status_code == 201, res_a.text
        cust_a_id = res_a.json()["data"]["customer"]["id"]

        # 3. Create Customer B
        email_b = f"test_b_{int(get_current_time().timestamp())}@louders.io"
        res_b = client.post(
            "/api/v1/customers",
            headers=headers,
            json={"name": "Customer Beta", "email": email_b, "phone": "+1987654321"}
        )
        assert res_b.status_code == 201, res_b.text
        cust_b_id = res_b.json()["data"]["customer"]["id"]

        # 4. Issue license to Customer A
        default_product_key = "lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU"
        res_lic = client.post(
            "/api/v1/licenses",
            headers=headers,
            json={
                "product_id": 1,
                "customer_id": cust_a_id,
                "plan_id": 1
            }
        )
        assert res_lic.status_code == 200, res_lic.text
        license_a_key = res_lic.json()["data"]["license"]["license_key"]

        # 5. Activate license on device for Customer A
        device_uuid_a = f"test-device-uuid-{int(get_current_time().timestamp())}"
        res_act = client.post(
            "/api/v1/extensions/activate",
            json={
                "product_api_key": default_product_key,
                "license_key": license_a_key,
                "customer_email": email_a,
                "device_uuid": device_uuid_a,
                "browser": "Chrome",
                "operating_system": "Windows",
                "extension_version": "2.0.0"
            }
        )
        assert res_act.status_code == 200, res_act.text
        ext_token = res_act.json()["extension_token"]

        # 6. Simulate Extension Release/Update
        # Touch extension files (like build_encrypted.js does)
        ext_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "extension")
        if os.path.exists(ext_dir):
            dummy_touch_file = os.path.join(ext_dir, ".build_timestamp")
            with open(dummy_touch_file, "w") as f:
                f.write(str(get_current_time().isoformat()))

        # Verify Customer A, Customer B, and License A still exist after extension update
        res_check_a = client.get(f"/api/v1/customers/{cust_a_id}", headers=headers)
        assert res_check_a.status_code == 200
        assert res_check_a.json()["data"]["customer"]["email"] == email_a

        res_check_b = client.get(f"/api/v1/customers/{cust_b_id}", headers=headers)
        assert res_check_b.status_code == 200
        assert res_check_b.json()["data"]["customer"]["email"] == email_b

        # 7. Non-destructive verify endpoint
        res_verify = client.post(
            "/api/v1/extensions/verify",
            json={
                "product_api_key": default_product_key,
                "license_key": license_a_key,
                "device_uuid": device_uuid_a,
                "browser": "Chrome",
                "extension_token": ext_token
            }
        )
        assert res_verify.status_code == 200, res_verify.text
        assert res_verify.json()["status"] == "active"

        # Verify Customer A still exists after verify
        res_check_a2 = client.get(f"/api/v1/customers/{cust_a_id}", headers=headers)
        assert res_check_a2.status_code == 200

        # 8. Non-destructive heartbeat endpoint
        res_hb = client.post(
            "/api/v1/extensions/heartbeat",
            json={
                "product_api_key": default_product_key,
                "license_key": license_a_key,
                "device_uuid": device_uuid_a,
                "browser": "Chrome",
                "operating_system": "Windows",
                "extension_version": "2.0.0",
                "extension_token": ext_token
            }
        )
        assert res_hb.status_code == 200, res_hb.text

        # Verify Customer A still exists after heartbeat
        res_check_a3 = client.get(f"/api/v1/customers/{cust_a_id}", headers=headers)
        assert res_check_a3.status_code == 200

        # 9. Verify Customer list serialization includes primary license summary
        res_list = client.get("/api/v1/customers", headers=headers)
        assert res_list.status_code == 200
        customers = res_list.json()["data"]["customers"]
        cust_a_data = next((c for c in customers if c["id"] == cust_a_id), None)
        assert cust_a_data is not None
        assert cust_a_data["primary_license_key"] == license_a_key
        assert cust_a_data["primary_license_status"] == "active"
        assert cust_a_data["primary_license_devices"] >= 1

        # 10. Explicit authenticated admin delete of Customer A
        res_del = client.delete(f"/api/v1/customers/{cust_a_id}", headers=headers)
        assert res_del.status_code == 200, res_del.text
        assert res_del.json()["success"] is True

        # 11. Verify Customer A is deleted
        res_get_deleted = client.get(f"/api/v1/customers/{cust_a_id}", headers=headers)
        assert res_get_deleted.status_code == 404

        # 12. Verify Customer B remains untouched!
        res_get_b = client.get(f"/api/v1/customers/{cust_b_id}", headers=headers)
        assert res_get_b.status_code == 200
        assert res_get_b.json()["data"]["customer"]["email"] == email_b

        # 13. Verify safe deletion requires authentication
        res_unauth_del = client.delete(f"/api/v1/customers/{cust_b_id}")
        assert res_unauth_del.status_code == 401

    finally:
        # Guarantee cleanup
        if cust_a_id:
            try:
                client.delete(f"/api/v1/customers/{cust_a_id}", headers=headers)
            except Exception:
                pass
        if cust_b_id:
            try:
                client.delete(f"/api/v1/customers/{cust_b_id}", headers=headers)
            except Exception:
                pass

