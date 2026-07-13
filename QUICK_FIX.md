# QUICK REFERENCE - SQLAlchemy Timestamp Fix

## 🔴 THE PROBLEM

```
POST /api/v1/products → Error
pydantic_core.ValidationError:
  ProductResponse.created_at
    Input should be a valid datetime
    input_value=None
```

**Why:** Database schema was created WITHOUT `DEFAULT CURRENT_TIMESTAMP`. When you insert a product, SQLite inserts NULL instead of the current time.

---

## ✅ THE SOLUTION (3 Steps)

### **Step 1: Run Alembic migration**
```bash
alembic upgrade head
```

This adds `DEFAULT CURRENT_TIMESTAMP` to the database.

### **Step 2: Restart application**
```bash
Ctrl+C  # Stop server
uvicorn app.main:app --reload  # Start with debug logging
```

### **Step 3: Test**
```bash
# Create a product
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"name":"Test","slug":"test","description":"test"}'
```

**Expected terminal output:**
```
[DEBUG] Product after refresh: {..., 'created_at': datetime.datetime(...), ...}
[SUCCESS] ✓ created_at populated from database default: 2026-07-06 12:34:56.789012
```

✅ **Done!** Your API will now return valid `created_at` timestamps.

---

## 📊 WHAT WAS FIXED

| Component | Issue | Fix |
|-----------|-------|-----|
| **Database** | NO DEFAULT CURRENT_TIMESTAMP | New Alembic migration adds it |
| **Models** | Implicit `server_default` | Made explicit: `nullable=False, server_default=func.now()` |
| **Logging** | No visibility into the problem | Added debug output to `create_product()` |

---

## 🔍 HOW TO VERIFY

### Check terminal shows success:
```
[SUCCESS] ✓ created_at populated from database default: ...
```

### Check database has DEFAULT:
```bash
sqlite3 instance/app.db ".schema products"
# Should show: created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
```

### Check API returns valid timestamp:
```bash
curl http://localhost:8000/api/v1/products \
  -H "Authorization: Bearer TOKEN" \
  | jq '.data.products[0].created_at'
# Should show: "2026-07-06T12:34:56.789012" (NOT null)
```

---

## 📁 FILES CHANGED

1. **`alembic/versions/2_fix_created_at_defaults.py`** - NEW migration file
2. **`app/models.py`** - Updated all timestamp columns
3. **`app/services/product_service.py`** - Added debug logging

---

## ⏱️ CLEANUP (Optional)

After verifying it works, remove debug print statements from `app/services/product_service.py`:

Find these lines and delete them:
```python
print(f"[DEBUG] Product before commit: ...")
print(f"[DEBUG] Product after commit: ...")
print(f"[DEBUG] Product after refresh: ...")
if product.created_at is None:
    print(f"[ERROR] ⚠️  CRITICAL: ...")
else:
    print(f"[SUCCESS] ✓ ...")
```

---

## 🚨 IF IT DOESN'T WORK

| Symptom | Solution |
|---------|----------|
| Still seeing `[ERROR] created_at is STILL NULL` | Migration didn't apply: `alembic current` → `alembic upgrade head` |
| `alembic upgrade head` fails | Check migration syntax: `alembic/versions/2_fix_created_at_defaults.py` |
| Database still shows NULL | Delete DB and re-migrate: `rm instance/app.db && alembic upgrade head` |
| API still returns null | Restart application and verify migration applied |

---

## 📝 ROOT CAUSE (Technical)

The original Alembic migration created this:
```python
sa.Column("created_at", sa.DateTime(), nullable=True),  # ❌ NO DEFAULT!
```

SQLite created:
```sql
CREATE TABLE products (
    created_at DATETIME DEFAULT NULL
)
```

When you insert, SQLite stores NULL. The SQLAlchemy model's `server_default=func.now()` only applies to NEW code, not existing databases.

**Fix:** New migration adds the database-level DEFAULT.

---

## ✨ END RESULT

After applying the fix:

✅ `POST /api/v1/products` works  
✅ `created_at` is populated with current timestamp  
✅ Pydantic validation passes  
✅ API returns valid datetime in response  
✅ All other models (customers, licenses, etc.) also get proper timestamps  

**No workarounds needed. Database enforces the default at the storage level.**
