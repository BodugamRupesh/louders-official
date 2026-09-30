"""
LOUD Platform - License Generator CLI Helper
Easily generate and inspect licenses locally or via your deployed Render server.
"""

import sys
import argparse
import requests
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Product, Customer, Plan, License
from app.services.license_service import LicenseService

def generate_locally(customer_email: str, customer_name: str, plan_name: str, product_name: str = "LOUD Premium"):
    db: Session = SessionLocal()
    try:
        # 1. Product
        product = db.query(Product).filter(Product.name == product_name).first()
        if not product:
            product = db.query(Product).first()
            if not product:
                print("[-] Error: No product found in database. Seed database first.")
                return

        # 2. Plan
        plan = db.query(Plan).filter(Plan.name.ilike(plan_name)).first()
        if not plan:
            print(f"[-] Warning: Plan '{plan_name}' not found. Available plans: Trial, Weekly, Monthly, Lifetime, Ultra")
            plan = db.query(Plan).filter(Plan.name.ilike("Lifetime")).first() or db.query(Plan).first()

        # 3. Customer
        customer = db.query(Customer).filter(Customer.email == customer_email.lower().strip()).first()
        if not customer:
            from app.services.customer_service import CustomerService
            customer = CustomerService.create_customer(
                db=db,
                name=customer_name or customer_email.split('@')[0],
                email=customer_email.lower().strip()
            )
            print(f"[+] Created new customer: {customer.name} ({customer.email}) [ID: {customer.id}]")
        else:
            print(f"[+] Found existing customer: {customer.name} ({customer.email}) [ID: {customer.id}]")

        # 4. Create License
        license_obj = LicenseService.create_license(
            db=db,
            product_id=product.id,
            customer_id=customer.id,
            plan_id=plan.id
        )

        print("\n" + "=" * 55)
        print("          NEW LICENSE GENERATED SUCCESSFULLY          ")
        print("=" * 55)
        print(f" Product:       {product.name}")
        print(f" Product API:   {product.api_key}")
        print(f" Customer:      {customer.email}")
        print(f" Plan:          {plan.name} ({plan.duration_days} days, max {plan.max_devices} devices)")
        print(f" License Key:   {license_obj.license_key}")
        print(f" Expiry Date:   {license_obj.expires_at}")
        print("=" * 55)
        print("\nUse the Customer Email and License Key to activate the extension!\n")

    except Exception as exc:
        db.rollback()
        print(f"[-] Error creating license: {exc}")
    finally:
        db.close()

def generate_via_api(server_url: str, admin_user: str, admin_pass: str, customer_email: str, customer_name: str, plan_id: int = 4, product_id: int = 1):
    base_url = server_url.rstrip("/")
    session = requests.Session()

    print(f"[*] Connecting to {base_url}...")
    # Login (requires JSON payload)
    login_res = session.post(
        f"{base_url}/api/v1/auth/login",
        json={"username": admin_user, "password": admin_pass},
        timeout=25
    )
    if login_res.status_code != 200:
        print(f"[-] Admin login failed ({login_res.status_code}): {login_res.text}")
        return

    token = login_res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Search or create customer
    cust_res = session.get(f"{base_url}/api/v1/customers/search?query={customer_email}", headers=headers)
    cust_id = None
    if cust_res.status_code == 200:
        customers = cust_res.json().get("data", {}).get("customers", [])
        for c in customers:
            if c.get("email", "").lower() == customer_email.lower():
                cust_id = c.get("id")
                break

    if not cust_id:
        create_cust_res = session.post(
            f"{base_url}/api/v1/customers",
            headers=headers,
            json={"name": customer_name or customer_email.split('@')[0], "email": customer_email}
        )
        if create_cust_res.status_code not in (200, 201):
            print(f"[-] Customer creation failed: {create_cust_res.text}")
            return
        cust_id = create_cust_res.json().get("data", {}).get("customer", {}).get("id")
        print(f"[+] Created customer ID: {cust_id}")
    else:
        print(f"[+] Found existing customer ID: {cust_id}")

    # Create license
    lic_res = session.post(
        f"{base_url}/api/v1/licenses",
        headers=headers,
        json={"product_id": product_id, "customer_id": cust_id, "plan_id": plan_id}
    )
    if lic_res.status_code not in (200, 201):
        print(f"[-] License creation failed: {lic_res.text}")
        return

    lic_data = lic_res.json().get("data", {}).get("license", {})
    print("\n" + "=" * 55)
    print("      REMOTE LICENSE GENERATED VIA API (RENDER)      ")
    print("=" * 55)
    print(f" Server:        {base_url}")
    print(f" Customer:      {customer_email}")
    print(f" License Key:   {lic_data.get('license_key')}")
    print(f" Expiry Date:   {lic_data.get('expires_at')}")
    print(f" Status:        {lic_data.get('status')}")
    print("=" * 55)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate LOUD licenses")
    parser.add_argument("--email", required=True, help="Customer email")
    parser.add_argument("--name", default="", help="Customer name")
    parser.add_argument("--plan", default="Lifetime", help="Plan name (Trial, Weekly, Monthly, Lifetime)")
    parser.add_argument("--render-url", default="", help="Render deployment URL (e.g. https://my-app.onrender.com)")
    parser.add_argument("--admin-user", default="hanzoo", help="Admin username")
    parser.add_argument("--admin-pass", default="Hanzoo@2511", help="Admin password")

    args = parser.parse_args()

    if args.render_url:
        plan_map = {"trial": 1, "weekly": 2, "monthly": 3, "lifetime": 4, "ultra": 5}
        pid = plan_map.get(args.plan.lower(), 4)
        generate_via_api(args.render_url, args.admin_user, args.admin_pass, args.email, args.name, plan_id=pid)
    else:
        generate_locally(args.email, args.name, args.plan)
