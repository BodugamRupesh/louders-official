"""
End-to-End Customer Deletion Test.
Strictly verifies that:
1. Customer creation persists to database.
2. DELETE API removes customer from database.
3. Database directly confirms record is deleted.
4. Cascaded data (licenses, devices, activity_logs) are completely purged.
5. GET /api/v1/customers list confirms customer is absent.
6. Re-queries and simulated restarts confirm record remains deleted.
7. Authorization is enforced (401 without admin token).
8. Non-existent customer deletion returns 404.
All tests run against isolated sandbox databases and never touch production.
"""

import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
import app.database as app_db
from app.models import Customer, License, Device, ActivityLog, Plan
from app.services.auth_service import AuthService
from app.utils.datetime_utils import get_current_time


@pytest.fixture(autouse=True)
def isolate_db_per_test():
    temp_dir = tempfile.mkdtemp(prefix="louders_delete_test_")
    test_db = os.path.join(temp_dir, "test_del.db").replace("\\", "/")

    prod_seed = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "licenses.db"))
    if os.path.exists(prod_seed):
        shutil.copy2(prod_seed, test_db)

    test_engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False, expire_on_commit=False)

    orig_engine = app_db.engine
    orig_session_local = app_db.SessionLocal
    app_db.engine = test_engine
    app_db.SessionLocal = TestSession

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield TestSession, test_engine

    app.dependency_overrides.pop(get_db, None)
    app_db.engine = orig_engine
    app_db.SessionLocal = orig_session_local
    test_engine.dispose()
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


def test_customer_delete_complete_lifecycle(isolate_db_per_test):
    TestSession, test_engine = isolate_db_per_test
    client = TestClient(app)

    token = AuthService.create_access_token(data={"sub": "hanzoo", "role": "owner", "admin_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. CREATE customer
    create_payload = {
        "name": "DELETE_TEST_CUSTOMER",
        "email": "delete_test_customer@louders.io",
        "phone": "+1555123456",
        "notes": "Testing customer deletion",
    }
    res_create = client.post("/api/v1/customers", headers=headers, json=create_payload)
    assert res_create.status_code == 201, f"Customer creation failed: {res_create.text}"
    cust_id = res_create.json()["data"]["customer"]["id"]
    assert cust_id > 0

    # 2. READ via API
    res_get = client.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["data"]["customer"]["name"] == "DELETE_TEST_CUSTOMER"

    # 3. DIRECT DATABASE VERIFY: Customer exists in database table
    with TestSession() as db:
        db_cust = db.query(Customer).filter(Customer.id == cust_id).first()
        assert db_cust is not None
        assert db_cust.email == "delete_test_customer@louders.io"

    # 4. LIST VERIFY: Appears in customers list
    res_list = client.get("/api/v1/customers", headers=headers)
    assert res_list.status_code == 200
    all_custs = res_list.json()["data"]["customers"]
    assert any(c["id"] == cust_id for c in all_custs)

    # 5. DELETE via API
    res_del = client.delete(f"/api/v1/customers/{cust_id}", headers=headers)
    assert res_del.status_code == 200, f"Delete failed: {res_del.text}"
    del_json = res_del.json()
    assert del_json["success"] is True
    assert del_json["data"]["customer_id"] == cust_id

    # 6. DIRECT DATABASE VERIFY: Customer is ABSOLUTELY GONE from database
    with TestSession() as db:
        db_cust_after = db.query(Customer).filter(Customer.id == cust_id).first()
        assert db_cust_after is None, "Customer still exists in database after delete!"

    # 7. READ via API after delete: 404
    res_get_deleted = client.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert res_get_deleted.status_code == 404

    # 8. LIST VERIFY after delete: Absent from customers list
    res_list_after = client.get("/api/v1/customers", headers=headers)
    assert res_list_after.status_code == 200
    all_custs_after = res_list_after.json()["data"]["customers"]
    assert not any(c["id"] == cust_id for c in all_custs_after)

    # 9. RESTART / REFRESH VERIFY: Remains deleted across a new client / session
    client_new = TestClient(app)
    res_list_restart = client_new.get("/api/v1/customers", headers=headers)
    assert not any(c["id"] == cust_id for c in res_list_restart.json()["data"]["customers"])


def test_customer_delete_with_associated_licenses_and_devices(isolate_db_per_test):
    TestSession, test_engine = isolate_db_per_test
    client = TestClient(app)

    token = AuthService.create_access_token(data={"sub": "hanzoo", "role": "owner", "admin_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create customer
    res_c = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Cust With Licenses", "email": "cust_with_lic@louders.io"}
    )
    assert res_c.status_code == 201
    cid = res_c.json()["data"]["customer"]["id"]

    # 2. Issue license
    res_l = client.post(
        "/api/v1/licenses",
        headers=headers,
        json={"product_id": 1, "customer_id": cid, "plan_id": 1}
    )
    assert res_l.status_code == 200
    lid = res_l.json()["data"]["license"]["id"]
    lkey = res_l.json()["data"]["license"]["license_key"]

    # 3. Activate device
    default_product_key = "lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU"
    res_act = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": default_product_key,
            "license_key": lkey,
            "customer_email": "cust_with_lic@louders.io",
            "device_uuid": "test-del-device-uuid-1",
            "browser": "Chrome",
            "operating_system": "Windows",
            "extension_version": "2.0.0"
        }
    )
    assert res_act.status_code == 200

    # Verify records exist in database
    with TestSession() as db:
        assert db.query(Customer).filter(Customer.id == cid).first() is not None
        assert db.query(License).filter(License.id == lid).first() is not None
        devs = db.query(Device).filter(Device.license_id == lid).all()
        assert len(devs) >= 1
        acts = db.query(ActivityLog).filter(ActivityLog.license_id == lid).all()
        assert len(acts) >= 1

    # 4. DELETE customer
    res_del = client.delete(f"/api/v1/customers/{cid}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 5. DIRECT DATABASE VERIFY: All associated records cleanly removed
    with TestSession() as db:
        assert db.query(Customer).filter(Customer.id == cid).first() is None
        assert db.query(License).filter(License.id == lid).first() is None
        assert db.query(Device).filter(Device.license_id == lid).count() == 0
        assert db.query(ActivityLog).filter(ActivityLog.license_id == lid).count() == 0

    # 6. Verify existing customers (e.g. baseline IDs 1-9) remain untouched
    with TestSession() as db:
        assert db.query(Customer).count() >= 9


def test_customer_delete_security_and_validation(isolate_db_per_test):
    TestSession, test_engine = isolate_db_per_test
    client = TestClient(app)

    # 1. Unauthorized delete without token
    res_unauth = client.delete("/api/v1/customers/1")
    assert res_unauth.status_code == 401

    # 2. Authenticated delete of non-existent customer
    token = AuthService.create_access_token(data={"sub": "hanzoo", "role": "owner", "admin_id": 1})
    headers = {"Authorization": f"Bearer {token}"}
    res_not_found = client.delete("/api/v1/customers/999999", headers=headers)
    assert res_not_found.status_code == 404
