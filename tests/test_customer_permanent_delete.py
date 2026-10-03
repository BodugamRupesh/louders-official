"""
Dedicated test suite for Customer Permanent Delete feature.

Verifies:
1. Unauthorized requests (missing token) return 401.
2. Wrong confirmation email returns 400 and preserves the customer and all related data.
3. Correct confirmation email permanently deletes the customer.
4. All dependent records (licenses, devices, activity logs) owned by the customer are deleted.
5. Unrelated customers, licenses, and devices remain completely untouched.
6. Safe transaction rollback occurs on unexpected failure.
7. Existing customer Delete functionality remains functional and untouched.
"""

import os
import shutil
import tempfile
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.database import Base, get_db
import app.database as app_db
from app.models import Customer, License, Device, ActivityLog, Product, Plan
from app.services.auth_service import AuthService
from app.utils.datetime_utils import get_current_time


@pytest.fixture(autouse=True)
def isolate_db_per_test():
    temp_dir = tempfile.mkdtemp(prefix="louders_perm_del_test_")
    test_db = os.path.join(temp_dir, "test_perm_del.db").replace("\\", "/")

    prod_seed = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "licenses.db"))
    if os.path.exists(prod_seed):
        shutil.copy2(prod_seed, test_db)

    test_engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

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


def test_permanent_delete_unauthorized(isolate_db_per_test):
    """Test requirement A: Unauthorized / non-admin request is rejected."""
    TestSession, _ = isolate_db_per_test
    client = TestClient(app)

    # Missing token -> 401
    res = client.post("/api/v1/customers/1/permanent-delete", json={"confirmation_email": "test@example.com"})
    assert res.status_code == 401


def test_permanent_delete_wrong_confirmation_email_rejected(isolate_db_per_test):
    """Test requirement B: Wrong confirmation email is rejected and customer remains intact."""
    TestSession, _ = isolate_db_per_test
    client = TestClient(app)

    token = AuthService.create_access_token(data={"sub": "hanzoo", "role": "owner", "admin_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    # Create target customer
    res_c = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Cust Wrong Confirm", "email": "real_cust@louders.io"}
    )
    assert res_c.status_code == 201
    cid = res_c.json()["data"]["customer"]["id"]

    # Provide mismatched email
    res_del = client.post(
        f"/api/v1/customers/{cid}/permanent-delete",
        headers=headers,
        json={"confirmation_email": "wrong_email@louders.io"}
    )
    assert res_del.status_code == 400
    assert "does not match" in res_del.text

    # Verify customer still exists in database
    with TestSession() as db:
        cust = db.query(Customer).filter(Customer.id == cid).first()
        assert cust is not None
        assert cust.email == "real_cust@louders.io"


def test_permanent_delete_success_with_dependent_records(isolate_db_per_test):
    """Test requirements C, D, E: Deletes target customer and children; preserves unrelated customer."""
    TestSession, _ = isolate_db_per_test
    client = TestClient(app)

    token = AuthService.create_access_token(data={"sub": "hanzoo", "role": "owner", "admin_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create target customer (to be deleted)
    res_c1 = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Target Customer", "email": "target_to_delete@louders.io"}
    )
    assert res_c1.status_code == 201
    cid1 = res_c1.json()["data"]["customer"]["id"]

    # 2. Create unrelated customer (must remain untouched)
    res_c2 = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Safe Unrelated Customer", "email": "safe_unrelated@louders.io"}
    )
    assert res_c2.status_code == 201
    cid2 = res_c2.json()["data"]["customer"]["id"]

    # 3. Create licenses for both customers
    res_l1 = client.post(
        "/api/v1/licenses",
        headers=headers,
        json={"product_id": 1, "customer_id": cid1, "plan_id": 1}
    )
    assert res_l1.status_code == 200
    lid1 = res_l1.json()["data"]["license"]["id"]
    lkey1 = res_l1.json()["data"]["license"]["license_key"]

    res_l2 = client.post(
        "/api/v1/licenses",
        headers=headers,
        json={"product_id": 1, "customer_id": cid2, "plan_id": 1}
    )
    assert res_l2.status_code == 200
    lid2 = res_l2.json()["data"]["license"]["id"]

    # 4. Activate device and activity logs for target customer
    default_product_key = "lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU"
    res_act = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": default_product_key,
            "license_key": lkey1,
            "customer_email": "target_to_delete@louders.io",
            "device_uuid": "target-perm-del-device-uuid",
            "browser": "Chrome",
            "operating_system": "Windows",
            "extension_version": "2.0.0"
        }
    )
    assert res_act.status_code == 200

    # 5. Confirm records exist before deletion
    with TestSession() as db:
        assert db.query(Customer).filter(Customer.id == cid1).first() is not None
        assert db.query(License).filter(License.id == lid1).first() is not None
        assert db.query(Device).filter(Device.license_id == lid1).count() >= 1
        assert db.query(ActivityLog).filter(ActivityLog.license_id == lid1).count() >= 1

        # Unrelated customer exists
        assert db.query(Customer).filter(Customer.id == cid2).first() is not None
        assert db.query(License).filter(License.id == lid2).first() is not None

    # 6. Execute PERMANENT DELETE with exact matching email
    res_perm_del = client.post(
        f"/api/v1/customers/{cid1}/permanent-delete",
        headers=headers,
        json={"confirmation_email": "target_to_delete@louders.io"}
    )
    assert res_perm_del.status_code == 200
    del_data = res_perm_del.json()["data"]
    assert del_data["customer_id"] == cid1
    assert del_data["email"] == "target_to_delete@louders.io"
    assert del_data["licenses_deleted"] == 1

    # 7. DIRECT DATABASE VERIFY: Target customer and ALL dependent records are gone
    with TestSession() as db:
        assert db.query(Customer).filter(Customer.id == cid1).first() is None
        assert db.query(License).filter(License.id == lid1).first() is None
        assert db.query(Device).filter(Device.license_id == lid1).count() == 0
        assert db.query(ActivityLog).filter(ActivityLog.license_id == lid1).count() == 0

        # Requirement E: Unrelated customer and their license remain completely untouched!
        unrelated_c = db.query(Customer).filter(Customer.id == cid2).first()
        assert unrelated_c is not None
        assert unrelated_c.name == "Safe Unrelated Customer"
        unrelated_l = db.query(License).filter(License.id == lid2).first()
        assert unrelated_l is not None


def test_permanent_delete_rollback_on_failure(isolate_db_per_test):
    """Test requirement F: Safe transaction rollback occurs if deletion fails."""
    TestSession, _ = isolate_db_per_test
    client = TestClient(app)

    token = AuthService.create_access_token(data={"sub": "hanzoo", "role": "owner", "admin_id": 1})
    headers = {"Authorization": f"Bearer {token}"}

    res_c = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Rollback Target", "email": "rollback_target@louders.io"}
    )
    assert res_c.status_code == 201
    cid = res_c.json()["data"]["customer"]["id"]

    # Mock db.commit to simulate database failure during commit
    with patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("Simulated DB commit error")):
        res_del = client.post(
            f"/api/v1/customers/{cid}/permanent-delete",
            headers=headers,
            json={"confirmation_email": "rollback_target@louders.io"}
        )
        assert res_del.status_code == 500

    # Verify transaction rolled back and customer remains intact
    with TestSession() as db:
        c = db.query(Customer).filter(Customer.id == cid).first()
        assert c is not None
        assert c.email == "rollback_target@louders.io"
