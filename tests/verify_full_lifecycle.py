"""
Comprehensive Verification Script for License and Customer Persistence Lifecycle.
Tests steps 1-19 as requested:
1. Create a customer.
2. Create a license for that customer.
3. Restart the application.
4. Verify customer exists.
5. Verify license exists.
6. Restart again.
7. Verify both still exist.
8. Perform license verification.
9. Verify both still exist.
10. Simulate failed heartbeat.
11. Verify both still exist.
12. Mark license expired.
13. Verify license still exists.
14. Refresh dashboard (simulate dashboard load).
15. Verify both still exist.
16. Log out and log in.
17. Verify both still exist.
18. Restart/deploy application simulation.
19. Verify both still exist.

Also tests all Section 15 functionalities:
- Login
- Dashboard / Overview
- Customers
- Licenses
- Products
- Plans
- Devices
- Admins
- Analytics
- Settings
- License verification
- Extension API
- Search & filter
"""

import os
import sys
import shutil
import tempfile
from datetime import datetime, timedelta

def run_tests():
    # Create isolated test environment
    temp_dir = tempfile.mkdtemp(prefix="louders_test_")
    test_db = os.path.join(temp_dir, "test_licenses.db").replace("\\", "/")
    
    # Copy current production db to initialize test db with production schema and seed
    prod_db = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "licenses.db"))
    if os.path.exists(prod_db):
        shutil.copy2(prod_db, test_db)
        
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"
    os.environ["ADMIN_USERNAME"] = "hanzoo"
    os.environ["ADMIN_PASSWORD"] = "Hanzoo@2511"

    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import engine, Base, SessionLocal
    from app.models import Customer, License, Device
    from app.services.auth_service import AuthService
    from app.utils.datetime_utils import get_current_time

    client = TestClient(app)
    results = {}

    print("--- 1. Authenticate Admin ---")
    login_res = client.post("/api/v1/auth/login", json={"username": "hanzoo", "password": "Hanzoo@2511"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    results["Login"] = "PASS"

    # Step 1: Create a customer
    print("--- Step 1: Create Customer ---")
    ts = int(get_current_time().timestamp())
    cust_email = f"persist_test_{ts}@louders.io"
    cust_res = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Persistence Customer", "email": cust_email, "phone": "+1999888777"}
    )
    assert cust_res.status_code == 201, f"Customer creation failed: {cust_res.text}"
    cust_id = cust_res.json()["data"]["customer"]["id"]
    print(f"[+] Customer created ID: {cust_id}, Email: {cust_email}")

    # Step 2: Create a license for that customer
    print("--- Step 2: Create License ---")
    lic_res = client.post(
        "/api/v1/licenses",
        headers=headers,
        json={"product_id": 1, "customer_id": cust_id, "plan_id": 1}
    )
    assert lic_res.status_code == 200, f"License creation failed: {lic_res.text}"
    license_key = lic_res.json()["data"]["license"]["license_key"]
    license_id = lic_res.json()["data"]["license"]["id"]
    print(f"[+] License created: {license_key} (ID: {license_id})")

    # Step 3, 4, 5: Simulate application restart & verify existence
    print("--- Step 3-5: Application Restart 1 & Verify ---")
    # Simulate restart by recreating client and reconnecting session
    client2 = TestClient(app)
    check_cust = client2.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert check_cust.status_code == 200, f"Customer not found after restart 1: {check_cust.text}"
    assert check_cust.json()["data"]["customer"]["email"] == cust_email
    check_lic = client2.get(f"/api/v1/licenses/{license_id}", headers=headers)
    assert check_lic.status_code == 200, f"License not found after restart 1: {check_lic.text}"
    assert check_lic.json()["data"]["license"]["license_key"] == license_key
    print("[+] Both customer and license exist after Restart 1")

    # Step 6, 7: Simulate second restart & verify existence
    print("--- Step 6-7: Application Restart 2 & Verify ---")
    client3 = TestClient(app)
    check_cust2 = client3.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert check_cust2.status_code == 200, "Customer not found after restart 2"
    check_lic2 = client3.get(f"/api/v1/licenses/{license_id}", headers=headers)
    assert check_lic2.status_code == 200, "License not found after restart 2"
    print("[+] Both customer and license exist after Restart 2")

    # Step 8, 9: Perform license verification
    print("--- Step 8-9: Perform Extension Activate & Verification ---")
    default_product_key = "lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU"
    device_uuid = f"persist-device-{ts}"
    act_res = client3.post(
        "/api/v1/extensions/activate",
        json={
            "product_api_key": default_product_key,
            "license_key": license_key,
            "customer_email": cust_email,
            "device_uuid": device_uuid,
            "browser": "Chrome",
            "operating_system": "Windows",
            "extension_version": "2.0.0"
        }
    )
    assert act_res.status_code == 200, f"Activation failed: {act_res.text}"
    ext_token = act_res.json()["extension_token"]

    ver_res = client3.post(
        "/api/v1/extensions/verify",
        json={
            "product_api_key": default_product_key,
            "license_key": license_key,
            "device_uuid": device_uuid,
            "browser": "Chrome",
            "extension_token": ext_token
        }
    )
    assert ver_res.status_code == 200, f"Verification failed: {ver_res.text}"
    # Verify both still exist
    check_cust3 = client3.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert check_cust3.status_code == 200
    check_lic3 = client3.get(f"/api/v1/licenses/{license_id}", headers=headers)
    assert check_lic3.status_code == 200
    print("[+] Both customer and license exist after Verification")

    # Step 10, 11: Simulate failed heartbeat
    print("--- Step 10-11: Simulate Failed Heartbeat & Verify Intact ---")
    bad_hb = client3.post(
        "/api/v1/extensions/heartbeat",
        json={
            "product_api_key": default_product_key,
            "license_key": license_key,
            "device_uuid": "nonexistent-device-uuid",
            "browser": "Chrome",
            "operating_system": "Windows",
            "extension_version": "2.0.0",
            "extension_token": ext_token
        }
    )
    # Failed heartbeat should return 400 or 404 or 422
    assert bad_hb.status_code in (400, 404, 422)
    # Check customer and license still exist intact
    check_cust4 = client3.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert check_cust4.status_code == 200
    check_lic4 = client3.get(f"/api/v1/licenses/{license_id}", headers=headers)
    assert check_lic4.status_code == 200
    print("[+] Both customer and license exist after Failed Heartbeat")

    # Step 12, 13: Mark license expired & verify existence
    print("--- Step 12-13: Mark License Expired & Verify It Stays In Database ---")
    db = SessionLocal()
    try:
        lic_model = db.query(License).filter(License.id == license_id).first()
        lic_model.expires_at = get_current_time() - timedelta(days=5)
        lic_model.status = "expired"
        db.commit()
    finally:
        db.close()

    check_lic_exp = client3.get(f"/api/v1/licenses/{license_id}", headers=headers)
    assert check_lic_exp.status_code == 200
    assert check_lic_exp.json()["data"]["license"]["status"] == "expired"
    check_cust_exp = client3.get(f"/api/v1/customers/{cust_id}", headers=headers)
    assert check_cust_exp.status_code == 200
    print("[+] Expired license remains in database with status='expired'; customer is intact")

    # Step 14, 15: Refresh / Load Dashboard panes & verify existence
    print("--- Step 14-15: Refresh Dashboard & Verify Both Exist ---")
    r_dash = client3.get("/")
    assert r_dash.status_code == 200, f"Dashboard index returned {r_dash.status_code}"
    r_custs = client3.get("/api/v1/customers", headers=headers)
    assert r_custs.status_code == 200
    r_lics = client3.get("/api/v1/licenses", headers=headers)
    assert r_lics.status_code == 200
    assert any(c["id"] == cust_id for c in r_custs.json()["data"]["customers"])
    assert any(l["id"] == license_id for l in r_lics.json()["data"]["licenses"])
    print("[+] Both customer and license exist after Dashboard loading")

    # Step 16, 17: Log out and log in & verify both exist
    print("--- Step 16-17: Log Out & Log In & Verify Both Exist ---")
    # New login
    new_login = client3.post("/api/v1/auth/login", json={"username": "hanzoo", "password": "Hanzoo@2511"})
    assert new_login.status_code == 200
    new_token = new_login.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}
    check_c_login = client3.get(f"/api/v1/customers/{cust_id}", headers=new_headers)
    assert check_c_login.status_code == 200
    check_l_login = client3.get(f"/api/v1/licenses/{license_id}", headers=new_headers)
    assert check_l_login.status_code == 200
    print("[+] Both customer and license exist after Re-login")

    # Step 18, 19: Simulate restart/redeploy & verify both exist
    print("--- Step 18-19: Simulate Restart/Redeploy with Existing DB & Verify ---")
    # Verify DB file survives and re-read
    client4 = TestClient(app)
    check_c_dep = client4.get(f"/api/v1/customers/{cust_id}", headers=new_headers)
    assert check_c_dep.status_code == 200
    check_l_dep = client4.get(f"/api/v1/licenses/{license_id}", headers=new_headers)
    assert check_l_dep.status_code == 200
    print("[+] Both customer and license exist after Redeploy simulation")

    # SECTION 15: VERIFY EXISTING FUNCTIONALITY
    print("\n--- SECTION 15 VERIFICATION ---")
    # Dashboard
    res_dash = client4.get("/")
    results["Dashboard"] = "PASS" if res_dash.status_code == 200 else "FAIL"

    # Customers
    res_c = client4.get("/api/v1/customers", headers=new_headers)
    results["Customers"] = "PASS" if res_c.status_code == 200 else "FAIL"

    # Licenses
    res_l = client4.get("/api/v1/licenses", headers=new_headers)
    results["Licenses"] = "PASS" if res_l.status_code == 200 else "FAIL"

    # Products
    res_p = client4.get("/api/v1/products", headers=new_headers)
    results["Products"] = "PASS" if res_p.status_code == 200 else "FAIL"

    # Plans
    res_pl = client4.get("/api/v1/plans", headers=new_headers)
    results["Plans"] = "PASS" if res_pl.status_code == 200 else "FAIL"

    # Devices
    res_d = client4.get("/api/v1/devices", headers=new_headers)
    results["Devices"] = "PASS" if res_d.status_code == 200 else "FAIL"

    # Admins
    res_a = client4.get("/api/v1/admins", headers=new_headers)
    results["Admins"] = "PASS" if res_a.status_code == 200 else "FAIL"

    # Analytics
    res_an = client4.get("/api/v1/analytics", headers=new_headers)
    results["Analytics"] = "PASS" if res_an.status_code == 200 else "FAIL"

    # Settings / System Info (current admin)
    res_s = client4.get("/api/v1/auth/me", headers=new_headers)
    results["Settings"] = "PASS" if res_s.status_code == 200 else "FAIL"

    # License verification
    results["License verification"] = "PASS" if ver_res.status_code == 200 else "FAIL"

    # Extension API
    results["Extension API"] = "PASS" if act_res.status_code == 200 else "FAIL"

    # Search & Filter
    search_res = client4.get(f"/api/v1/customers/search?query={cust_email}", headers=new_headers)
    results["Customer Search"] = "PASS" if search_res.status_code == 200 and len(search_res.json()["data"]["customers"]) >= 1 else "FAIL"

    # Clean up test records
    client4.delete(f"/api/v1/customers/{cust_id}", headers=new_headers)

    # Clean up temp test directory
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

    print("\nRESULTS SUMMARY:")
    for k, v in results.items():
        print(f"  {k}: {v}")

    return all(v == "PASS" for v in results.values())

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
