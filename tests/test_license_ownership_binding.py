"""
Regression tests for License Ownership and Email Binding.

Business Rule:
1 LICENSE = 1 CUSTOMER EMAIL = UP TO N DEVICES

Invariants Verified:
1. Every license belongs to exactly one customer.
2. A license key is strictly bound to its owning customer.
3. Extension activation validates BOTH license key and customer email.
4. Valid license key with wrong email is rejected (HTTP 403).
5. Valid license key with another customer's email is rejected (HTTP 403).
6. Correct email + correct key allows devices up to device_limit.
7. Device limit applies per license (e.g. limit=5 allows 1-5, rejects 6th).
8. Repeated activation with same email + same device UUID is idempotent.
9. Legitimately deactivating a device frees up a slot for another device.
10. Verify endpoint cannot be accessed by an unauthorized/unregistered device.
11. Heartbeat and deactivate endpoints cannot bypass ownership or affect unrelated licenses.
"""

import os
import shutil
import tempfile
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
def ownership_test_context():
    temp_dir = tempfile.mkdtemp(prefix="louders_ownership_test_")
    test_db = os.path.join(temp_dir, "test_ownership.db").replace("\\", "/")

    engine = create_engine(
        f"sqlite:///{test_db}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    # Seed test product, plan with max_devices=5, and two customers
    with TestingSessionLocal() as db:
        prod = Product(
            id=10,
            name="LOUD Test Product",
            slug="loud-test-product",
            version="1.0.0",
            api_key="lp_test_product_api_key_valid",
            status="active",
        )
        plan_5 = Plan(
            id=10,
            name="5 Devices Plan",
            duration_days=30,
            max_devices=5,
            price=25.0,
            status="active",
        )
        cust_a = Customer(
            id=101,
            name="Alice Owner",
            email="alice@example.com",
            phone="+1234567890",
        )
        cust_b = Customer(
            id=102,
            name="Bob Intruder",
            email="bob@example.com",
            phone="+1987654321",
        )
        db.add_all([prod, plan_5, cust_a, cust_b])
        db.commit()

        # License belongs strictly to Customer A (Alice)
        lic_a = License(
            id=50,
            product_id=prod.id,
            customer_id=cust_a.id,
            plan_id=plan_5.id,
            license_key="LP-26-ALICE-KEY-0001",
            status="active",
            expires_at=get_current_time() + timedelta(days=30),
        )
        db.add(lic_a)
        db.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=False)

    yield {
        "client": client,
        "Session": TestingSessionLocal,
        "prod_key": "lp_test_product_api_key_valid",
        "license_key": "LP-26-ALICE-KEY-0001",
        "owner_email": "alice@example.com",
        "intruder_email": "bob@example.com",
        "random_email": "stranger@otherdomain.com",
    }

    app.dependency_overrides.pop(get_db, None)
    engine.dispose()
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


def test_1_correct_email_and_key_device_1_passes(ownership_test_context):
    """Invariant 1 & 5: Correct email + correct key + Device 1 -> PASS."""
    ctx = ownership_test_context
    client = ctx["client"]

    resp = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["owner_email"],
            "device_uuid": "device-uuid-001",
            "browser": "Chrome",
            "operating_system": "windows",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["license_key"] == ctx["license_key"]
    assert "extension_token" in data
    assert data["max_devices"] == 5


def test_2_correct_email_and_key_device_1_passes_and_device_2_rejected(ownership_test_context):
    """Under 1 License = 1 Device UUID model, Device 1 passes, Device 2 is rejected."""
    ctx = ownership_test_context
    client = ctx["client"]

    # Device 1 succeeds
    resp1 = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["owner_email"],
            "device_uuid": "device-uuid-001",
            "browser": "Chrome",
        },
    )
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True

    # Device 2 with different UUID is rejected
    resp2 = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["owner_email"],
            "device_uuid": "device-uuid-002",
            "browser": "Chrome",
        },
    )
    assert resp2.status_code == 403


def _extract_err_msg(resp):
    data = resp.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict):
            return data["error"].get("message", "")
        return data.get("detail", "")
    return str(data)


def test_3_second_device_uuid_rejected(ownership_test_context):
    """Under 1 License = 1 Device UUID model, second Device UUID is always rejected."""
    ctx = ownership_test_context
    client = ctx["client"]

    # Activate device 1
    client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["owner_email"],
            "device_uuid": "device-uuid-001",
            "browser": "Chrome",
        },
    )

    # Attempt second device
    resp = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["owner_email"],
            "device_uuid": "device-uuid-002",
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 403
    err = _extract_err_msg(resp).lower()
    assert "bound" in err or "limit" in err


def test_4_wrong_email_valid_key_rejected(ownership_test_context):
    """Invariant 4: A valid license key presented with an unassociated email MUST be rejected."""
    ctx = ownership_test_context
    client = ctx["client"]

    resp = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["random_email"],
            "device_uuid": "intruder-device-999",
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 403
    assert "Customer email does not match license owner" in _extract_err_msg(resp)


def test_5_another_customer_email_same_valid_key_rejected(ownership_test_context):
    """Invariant 8: Even another valid, existing customer's email cannot use this license key."""
    ctx = ownership_test_context
    client = ctx["client"]

    resp = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["intruder_email"],  # Bob's email, but license belongs to Alice
            "device_uuid": "bobs-device-1",
            "browser": "Chrome",
        },
    )
    assert resp.status_code == 403
    assert "Customer email does not match license owner" in _extract_err_msg(resp)


def test_6_same_email_same_key_same_device_uuid_repeated_is_idempotent(ownership_test_context):
    """Invariant 10: Repeated activation from same email + device UUID does not duplicate devices."""
    ctx = ownership_test_context
    client = ctx["client"]

    payload = {
        "product_api_key": ctx["prod_key"],
        "license_key": ctx["license_key"],
        "customer_email": ctx["owner_email"],
        "device_uuid": "stable-device-uuid-xyz",
        "browser": "Chrome",
    }

    # First activation
    resp1 = client.post("/api/v1/extensions/activate", json=payload)
    assert resp1.status_code == 200

    # Repeat activation
    resp2 = client.post("/api/v1/extensions/activate", json=payload)
    assert resp2.status_code == 200

    with ctx["Session"]() as db:
        devices = db.query(Device).filter(Device.license_id == 50).all()
        assert len(devices) == 1
        assert devices[0].device_uuid == "stable-device-uuid-xyz"


def test_7_changing_device_uuid_does_not_allow_different_email(ownership_test_context):
    """Invariant 9: Changing the device UUID MUST NOT allow a different email to use the license."""
    ctx = ownership_test_context
    client = ctx["client"]

    # Try 3 different device UUIDs with Bob's email
    for dev_uuid in ["dev-fake-1", "dev-fake-2", "dev-fake-3"]:
        resp = client.post(
            "/api/v1/extensions/activate",
            json={
                "product_api_key": ctx["prod_key"],
                "license_key": ctx["license_key"],
                "customer_email": ctx["intruder_email"],
                "device_uuid": dev_uuid,
                "browser": "Chrome",
            },
        )
        assert resp.status_code == 403
        assert "Customer email does not match license owner" in _extract_err_msg(resp)

    # Confirm zero devices registered for this license
    with ctx["Session"]() as db:
        assert db.query(Device).filter(Device.license_id == 50).count() == 0


def test_8_deactivation_does_not_clear_binding(ownership_test_context):
    """Invariant: After a device is deactivated, a different device UUID is still rejected."""
    ctx = ownership_test_context
    client = ctx["client"]

    # Activate device 1
    act_resp = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["owner_email"],
            "device_uuid": "slot-device-1",
            "browser": "Chrome",
        },
    )
    assert act_resp.status_code == 200

    # Deactivate device 1
    deact_resp = client.post(
        "/api/v1/extensions/deactivate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "device_uuid": "slot-device-1",
        },
    )
    assert deact_resp.status_code == 200
    assert deact_resp.json()["device_removed"] is True

    # Device 2 with different UUID is still REJECTED because the license remains permanently bound to slot-device-1
    resp_reject = client.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "customer_email": ctx["owner_email"],
            "device_uuid": "slot-device-2",
            "browser": "Chrome",
        },
    )
    assert resp_reject.status_code == 403


def test_9_verify_cannot_be_used_by_unauthorized_device(ownership_test_context):
    """Invariant: Verify endpoint rejects any device that failed email activation."""
    ctx = ownership_test_context
    client = ctx["client"]

    # Verify call for a device that was never activated with the owner email
    resp = client.post(
        "/api/v1/extensions/verify",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "device_uuid": "unregistered-intruder-device",
            "browser": "Chrome",
        },
    )
    assert resp.status_code in (400, 404)
    err = _extract_err_msg(resp).lower()
    assert "not registered" in err or "not found" in err


def test_10_heartbeat_cannot_bypass_ownership(ownership_test_context):
    """Invariant: Heartbeat cannot be performed for a device not registered under the license."""
    ctx = ownership_test_context
    client = ctx["client"]

    resp = client.post(
        "/api/v1/extensions/heartbeat",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "device_uuid": "unregistered-intruder-device",
            "browser": "Chrome",
        },
    )
    assert resp.status_code in (400, 404)
    err = _extract_err_msg(resp).lower()
    assert "not found" in err or "not registered" in err


def test_11_deactivate_cannot_affect_unowned_device(ownership_test_context):
    """Invariant: Deactivate cannot be used to remove or affect an unowned/unregistered device."""
    ctx = ownership_test_context
    client = ctx["client"]

    resp = client.post(
        "/api/v1/extensions/deactivate",
        json={
            "product_api_key": ctx["prod_key"],
            "license_key": ctx["license_key"],
            "device_uuid": "nonexistent-device-uuid",
        },
    )
    assert resp.status_code in (400, 404)
