# LOUD Platform - Licensing System & Protected Chrome Extension

Enterprise-grade licensing infrastructure and WebAudio DSP Chrome extension engine.

---

## 🚀 Features

- **FastAPI Licensing Backend**: Multi-product, multi-plan, cryptographic JWT token verification.
- **Admin Dashboard**: Sleek web console to manage Products, Plans, Customers, Licenses, and Device Telemetry.
- **Live Production URL**: `https://louders-official.onrender.com`
- **Chrome Extension (`extension/`)**: Low-latency WebAudio DSP engine with real-time tube warmth, distortion, EQ, compressor, and VST bridge.
- **Maximum Anti-Reverse Engineering**: Hardened with RC4 symmetric string encryption, 100% control flow flattening, and dead-code injection (Chrome MV3 CSP compliant).
- **Offline License Caching**: Encrypted token cache in `chrome.storage.local` with offline grace periods.

---

## 📁 Repository Structure

```text
louders-official/
├── app/                  # FastAPI Licensing Server
│   ├── main.py           # Server entry point with startup auto-recovery
│   ├── models.py         # SQLAlchemy DB models (Product, License, Device, Customer, Plan)
│   ├── routers/          # API routes (extensions, licenses, products, customers, auth)
│   ├── services/         # Business logic and JWT signing
│   ├── static/           # Admin dashboard CSS/JS
│   └── templates/        # Dashboard HTML
├── extension/            # Hardened, 100% encrypted Chrome extension (ready to distribute)
├── scripts/
│   └── build_encrypted.js # Maximum encryption build pipeline
├── generate_license.py   # CLI helper for creating licenses
├── licenses.db           # SQLite database
├── Dockerfile            # Container deployment configuration
└── requirements.txt      # Python dependencies
```

---

## 🔑 Default Production Product

| Parameter | Value |
| :--- | :--- |
| **Product Name** | `LOUD Premium` |
| **Product ID** | `1` |
| **Product API Key** | `lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU` |
| **Production Server** | `https://louders-official.onrender.com` |

---

## 🛠️ Quick Start

### 1. Run the Backend Locally
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open admin console: `http://127.0.0.1:8000`

### 2. Run Tests
```bash
python -m pytest
```

### 3. Generate a Customer License (CLI)
```bash
python generate_license.py --email customer@example.com --plan Lifetime
```

### 4. Re-Encrypt the Chrome Extension
Whenever you update extension source code:
```bash
node scripts/build_encrypted.js
```
This reads your source code, encrypts 100% of strings with RC4, flattens all control flow, and outputs to `extension/`.

---

## 📦 Distributing to Customers

1. Distribute the `extension/` folder (or zipped archive).
2. Customers load it in Chrome via `chrome://extensions` -> **Load unpacked**.
3. Issue a license from your dashboard at `https://louders-official.onrender.com`.
4. The customer activates in the extension popup with their **Email** and **License Key**.
5. The extension stores the license locally and functions seamlessly both online and offline.
