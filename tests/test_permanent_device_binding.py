"""
Mandatory Isolated Regression Tests for Permanent Device Binding Model.

Business Rule:
1 LICENSE = 1 CUSTOMER EMAIL = 1 DEVICE UUID
(Permanent Device Binding)

Invariants Tested:
1. First activation with UUID A → SUCCESS
2. Same email + same license + UUID A → SUCCESS
3. Same email + same license + UUID B → REJECT
4. Different email + same license + UUID A → REJECT
5. Different email + same license + UUID B → REJECT
6. Same UUID repeated activation → idempotent SUCCESS
7. UUID B cannot replace UUID A
8. Verify with UUID A → SUCCESS
9. Verify with UUID B → REJECT
10. Heartbeat with UUID A → SUCCESS
11. Heartbeat with UUID B → REJECT
12. Deactivate UUID A → MUST NOT automatically allow UUID B
13. Concurrent first activation (UUID A & UUID B) → only ONE binds successfully
14. Expired license → REJECT
15. Revoked license → REJECT
16. Suspended license → REJECT
17. Wrong customer email → REJECT
18. Existing customer/license relationships remain intact
"""

import os
import shutil
import tempfile
import threading
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import Customer, License, Device, Product, Plan
from app.utils.datetime_utils import get_current_time
from app.main import app


@pytest.fixture
def binding_test_context():
    """Provides a completely isolated SQLite database sandbox."""
    temp_dir = tempfile.mkdtemp(prefix="louders_perm_binding_test_")
    test_db = os.path.join(temp_dir, "test_binding.db").replace("\\", "/")

    engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    # Seed test product, plan, and customers
    with TestingSessionLocal() as db:
        prod = Product(
            id=10,
            name="LOUD Binding Product",
            slug="loud-binding-product",
            version="1.0.0",
            api_key="lp_test_product_api_key_perm",
            status="active",
        )
        plan = Plan(
            id=10,
            name="Single Device Plan",
            duration_days=30,
            max_devices=1,
            price=29.0,
            status="active",
        )
        cust_a = Customer(
            id=201,
            name="Owner Alice",
            email="owner@gmail.com",
            phone="+1111111111",
        )
        cust_b = Customer(
            id=202,
            name="Intruder Bob",
            email="intruder@gmail.com",
            phone="+2222222222",
        )
        db.add_all([prod, plan, cust_a, cust_b])
        db.commit()

        # License strictly owned by Owner Alice
        lic = License(
            id=101,
            product_id=prod.id,
            customer_id=cust_a.id,
            plan_id=plan.id,
            license_key="LP-PERM-AAAA-BBBB-1111",
            status="active",
            bound_device_uuid=None,
            expires_at=get_current_time() + timedelta(days=30),
        )
        db.add(lic)
        db.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "engine": engine,
        "session_maker": TestingSessionLocal,
        "product_key": "lp_test_product_api_key_perm",
        "license_key": "LP-PERM-AAAA-BBBB-1111",
        "owner_email": "owner@gmail.com",
        "other_email": "intruder@gmail.com",
        "device_a": "DEVICE-UUID-AAA-111",
        "device_b": "DEVICE-UUID-BBB-222",
        "license_id": 101,
    }

    app.dependency_overrides.pop(get_db, None)
    engine.dispose()
    shutil.rmtree(temp_dir, ignore_errors=True)


# 1. First activation with UUID A → SUCCESS
def test_1_first_activation_uuid_a_success(binding_test_context):
    c = binding_test_context["client"]
    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
            "operating_system": "Windows",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "extension_token" in data

    # Verify bound in database
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        assert lic.bound_device_uuid == binding_test_context["device_a"]


# 2. Same email + same license + UUID A → SUCCESS
def test_2_same_email_same_license_uuid_a_success(binding_test_context):
    c = binding_test_context["client"]
    # First activation
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Subsequent activation
    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# 3. Same email + same license + UUID B → REJECT
def test_3_same_email_same_license_uuid_b_rejected(binding_test_context):
    c = binding_test_context["client"]
    # Activate UUID A
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Attempt activate UUID B with same owner email
    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_b"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 403
    assert "permanently bound" in resp.text.lower() or "limit" in resp.text.lower()


# 4. Different email + same license + UUID A → REJECT
def test_4_different_email_same_license_uuid_a_rejected(binding_test_context):
    c = binding_test_context["client"]
    # Activate UUID A
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Different email attempting UUID A
    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["other_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 403
    assert "does not match" in resp.text.lower()


# 5. Different email + same license + UUID B → REJECT
def test_5_different_email_same_license_uuid_b_rejected(binding_test_context):
    c = binding_test_context["client"]
    # Activate UUID A
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Different email attempting UUID B
    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["other_email"],
            "device_uuid": binding_test_context["device_b"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 403


# 6. Same UUID repeated activation → idempotent SUCCESS
def test_6_same_uuid_repeated_activation_is_idempotent(binding_test_context):
    c = binding_test_context["client"]
    payload = {
        "product_api_key": binding_test_context["product_key"],
        "license_key": binding_test_context["license_key"],
        "customer_email": binding_test_context["owner_email"],
        "device_uuid": binding_test_context["device_a"],
        "browser": "Chrome",
    }
    r1 = c.post("/api/v1/extensions/activate", json=payload)
    r2 = c.post("/api/v1/extensions/activate", json=payload)
    r3 = c.post("/api/v1/extensions/activate", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200

    # Ensure exactly 1 device row in DB
    with binding_test_context["session_maker"]() as db:
        devs = db.query(Device).filter(Device.license_id == binding_test_context["license_id"]).all()
        assert len(devs) == 1


# 7. UUID B cannot replace UUID A
def test_7_uuid_b_cannot_replace_uuid_a(binding_test_context):
    c = binding_test_context["client"]
    # Activate UUID A
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Repeated attempts by UUID B
    for _ in range(3):
        resp = c.post(
            "/api/v1/extensions/activate",
            json={
                "product_api_key": binding_test_context["product_key"],
                "license_key": binding_test_context["license_key"],
                "customer_email": binding_test_context["owner_email"],
                "device_uuid": binding_test_context["device_b"],
                "browser": "Chrome",
            },
        )
        assert resp.status_code == 403

    # Confirm UUID A is still bound
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        assert lic.bound_device_uuid == binding_test_context["device_a"]


# 8. Verify with UUID A → SUCCESS
def test_8_verify_with_uuid_a_success(binding_test_context):
    c = binding_test_context["client"]
    act_resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    token = act_resp.json()["extension_token"]

    ver_resp = c.post(
        "/api/v1/extensions/verify",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
            "extension_token": token,
        },
    )
    assert ver_resp.status_code == 200
    assert ver_resp.json()["success"] is True
    assert ver_resp.json()["current_device_registered"] is True


# 9. Verify with UUID B → REJECT
def test_9_verify_with_uuid_b_rejected(binding_test_context):
    c = binding_test_context["client"]
    # Activate UUID A
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Verify with UUID B
    ver_resp = c.post(
        "/api/v1/extensions/verify",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "device_uuid": binding_test_context["device_b"],
            "browser": "Chrome",
        },
    )
    assert ver_resp.status_code in (400, 404)


# 10. Heartbeat with UUID A → SUCCESS
def test_10_heartbeat_with_uuid_a_success(binding_test_context):
    c = binding_test_context["client"]
    act_resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    token = act_resp.json()["extension_token"]

    hb_resp = c.post(
        "/api/v1/extensions/heartbeat",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
            "extension_token": token,
        },
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["success"] is True


# 11. Heartbeat with UUID B → REJECT
def test_11_heartbeat_with_uuid_b_rejected(binding_test_context):
    c = binding_test_context["client"]
    # Activate UUID A
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Heartbeat with UUID B
    hb_resp = c.post(
        "/api/v1/extensions/heartbeat",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "device_uuid": binding_test_context["device_b"],
            "browser": "Chrome",
        },
    )
    assert hb_resp.status_code in (400, 404)


# 12. Deactivate UUID A → MUST NOT automatically allow UUID B
def test_12_deactivate_uuid_a_does_not_allow_uuid_b(binding_test_context):
    c = binding_test_context["client"]
    # Activate UUID A
    c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    # Deactivate UUID A
    deact_resp = c.post(
        "/api/v1/extensions/deactivate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "device_uuid": binding_test_context["device_a"],
        },
    )
    assert deact_resp.status_code == 200

    # Ensure bound_device_uuid was NOT cleared
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        assert lic.bound_device_uuid == binding_test_context["device_a"]

    # Now attempt activation with UUID B → MUST BE REJECTED
    act_b = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_b"],
            "browser": "Chrome",
        },
    )
    assert act_b.status_code == 403
    assert "permanently bound" in act_b.text.lower() or "limit" in act_b.text.lower()


# 13. Concurrent first activation: UUID A and UUID B, only ONE binds successfully
def test_13_concurrent_first_activation_only_one_wins(binding_test_context):
    c = binding_test_context["client"]
    results = []

    def activate_device(dev_uuid):
        r = c.post(
            "/api/v1/extensions/activate",
            json={
                "product_api_key": binding_test_context["product_key"],
                "license_key": binding_test_context["license_key"],
                "customer_email": binding_test_context["owner_email"],
                "device_uuid": dev_uuid,
                "browser": "Chrome",
            },
        )
        results.append((dev_uuid, r.status_code))

    t1 = threading.Thread(target=activate_device, args=(binding_test_context["device_a"],))
    t2 = threading.Thread(target=activate_device, args=(binding_test_context["device_b"],))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    status_codes = [sc for _, sc in results]
    assert 200 in status_codes, f"At least one must succeed: {results}"
    assert 403 in status_codes or len([sc for sc in status_codes if sc == 200]) == 1

    # Exactly one device is bound in DB
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        assert lic.bound_device_uuid in (binding_test_context["device_a"], binding_test_context["device_b"])
        devs = db.query(Device).filter(Device.license_id == binding_test_context["license_id"]).all()
        assert len(devs) == 1


# 14. Expired license → REJECT
def test_14_expired_license_rejected(binding_test_context):
    c = binding_test_context["client"]
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        lic.expires_at = get_current_time() - timedelta(days=1)
        db.commit()

    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code in (400, 403)
    assert "expired" in resp.text.lower()


# 15. Revoked license → REJECT
def test_15_revoked_license_rejected(binding_test_context):
    c = binding_test_context["client"]
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        lic.status = "revoked"
        db.commit()

    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code in (400, 403)
    assert "revoked" in resp.text.lower()


# 16. Suspended license → REJECT
def test_16_suspended_license_rejected(binding_test_context):
    c = binding_test_context["client"]
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        lic.status = "suspended"
        db.commit()

    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": binding_test_context["owner_email"],
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code in (400, 403)
    assert "suspended" in resp.text.lower()


# 17. Wrong customer email → REJECT
def test_17_wrong_customer_email_rejected(binding_test_context):
    c = binding_test_context["client"]
    resp = c.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": binding_test_context["product_key"],
            "license_key": binding_test_context["license_key"],
            "customer_email": "random_wrong@example.com",
            "device_uuid": binding_test_context["device_a"],
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 403
    assert "does not match" in resp.text.lower()


# 18. Existing customer/license relationships remain intact
def test_18_existing_customer_license_relationships_remain_intact(binding_test_context):
    with binding_test_context["session_maker"]() as db:
        lic = db.query(License).filter(License.id == binding_test_context["license_id"]).first()
        assert lic.customer_id == 201
        assert lic.customer.email == "owner@gmail.com"
        assert lic.plan.max_devices == 1
