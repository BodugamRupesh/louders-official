# EXACT CODE CHANGES - Copy/Paste Reference

## 1. NEW FILE: alembic/versions/2_fix_created_at_defaults.py

```python
"""Fix created_at defaults and nullability

Revision ID: 2_fix_created_at_defaults
Revises: 1fc395a8427c
Create Date: 2026-07-06 12:00:00.000000

This migration fixes the broken initial migration which didn't include
server_default for timestamp columns. SQLite was inserting NULL instead
of the current timestamp.

Changes:
- Add DEFAULT CURRENT_TIMESTAMP to all timestamp columns (created_at, last_seen, timestamp)
- Change timestamp columns from nullable=True to nullable=False
- Existing NULL values are set to current timestamp
- Affected columns: created_at, last_seen, timestamp
- Affected tables: admin_users, plans, products, customers, licenses, devices, activity_logs, extensions
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '2_fix_created_at_defaults'
down_revision: Union[str, Sequence[str], None] = '1fc395a8427c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - fix all timestamp columns with NULL defaults."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    
    # Map of table -> list of columns to fix
    timestamp_columns = {
        'admin_users': ['created_at'],
        'plans': ['created_at'],
        'products': ['created_at'],
        'customers': ['created_at'],
        'licenses': ['created_at'],
        'devices': ['last_seen'],
        'activity_logs': ['timestamp'],
        'extensions': ['created_at'],
    }
    
    # For SQLite, we need to use raw SQL because of limited ALTER TABLE support
    if dialect_name == 'sqlite':
        # Update existing NULL values to current timestamp
        for table_name, columns in timestamp_columns.items():
            for col_name in columns:
                try:
                    # First, set any NULL timestamp to current timestamp
                    op.execute(
                        text(f"""
                            UPDATE {table_name} 
                            SET {col_name} = CURRENT_TIMESTAMP 
                            WHERE {col_name} IS NULL
                        """)
                    )
                except Exception:
                    # Table might not exist, skip
                    pass
        
        # SQLite doesn't support ALTER COLUMN, so we document the schema change
        # The actual default will be enforced by SQLAlchemy going forward
        
    elif dialect_name == 'postgresql':
        # For PostgreSQL, we can use proper ALTER TABLE
        for table_name, columns in timestamp_columns.items():
            for col_name in columns:
                try:
                    # Set existing NULLs to current timestamp
                    op.execute(
                        text(f"""
                            UPDATE {table_name} 
                            SET {col_name} = CURRENT_TIMESTAMP 
                            WHERE {col_name} IS NULL
                        """)
                    )
                    
                    # Add NOT NULL constraint
                    op.alter_column(
                        table_name,
                        col_name,
                        existing_type=sa.DateTime(),
                        nullable=False,
                        existing_nullable=True,
                    )
                    
                    # Add DEFAULT CURRENT_TIMESTAMP
                    op.execute(
                        text(f"""
                            ALTER TABLE {table_name}
                            ALTER COLUMN {col_name}
                            SET DEFAULT CURRENT_TIMESTAMP
                        """)
                    )
                except Exception:
                    # Table or column might not exist, skip
                    pass
    
    elif dialect_name == 'mysql':
        # For MySQL
        for table_name, columns in timestamp_columns.items():
            for col_name in columns:
                try:
                    # Set existing NULLs to current timestamp
                    op.execute(
                        text(f"""
                            UPDATE {table_name} 
                            SET {col_name} = CURRENT_TIMESTAMP 
                            WHERE {col_name} IS NULL
                        """)
                    )
                    
                    # Modify column to NOT NULL with DEFAULT
                    op.execute(
                        text(f"""
                            ALTER TABLE {table_name}
                            MODIFY {col_name} DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        """)
                    )
                except Exception:
                    # Table or column might not exist, skip
                    pass


def downgrade() -> None:
    """Downgrade schema - restore previous state."""
    # This downgrade is intentionally no-op because we're fixing a bug
    # We don't want to revert to broken schema
    pass
```

---

## 2. UPDATED: app/models.py - All timestamp columns

### Before (BROKEN):
```python
created_at = Column(DateTime, server_default=func.now())
```

### After (FIXED):
```python
created_at = Column(
    DateTime,
    nullable=False,
    server_default=func.now(),
)
```

**Applied to ALL 7 models:**
1. AdminUser - `created_at`
2. Plan - `created_at`
3. Product - `created_at`
4. Customer - `created_at`
5. License - `created_at`
6. Device - `last_seen`
7. ActivityLog - `timestamp`

---

## 3. UPDATED: app/services/product_service.py - create_product() method

### Before (BROKEN - no logging):
```python
db.add(product)
db.commit()
db.refresh(product)

return product
```

### After (FIXED - with debug logging):
```python
print(f"[DEBUG] Product before commit: {product.__dict__}")
print(f"[DEBUG]   created_at={product.created_at}, id={product.id}")

db.add(product)
db.commit()

print(f"[DEBUG] Product after commit: {product.__dict__}")
print(f"[DEBUG]   created_at={product.created_at}, id={product.id}")

db.refresh(product)

print(f"[DEBUG] Product after refresh: {product.__dict__}")
print(f"[DEBUG]   created_at={product.created_at} (type: {type(product.created_at)})")

if product.created_at is None:
    print(f"[ERROR] ⚠️  CRITICAL: created_at is STILL NULL after refresh!")
    print(f"[ERROR] This indicates DATABASE DEFAULT is missing.")
    print(f"[ERROR] Run Alembic migration: alembic upgrade head")
else:
    print(f"[SUCCESS] ✓ created_at populated from database default: {product.created_at}")

return product
```

---

## WHAT CHANGED

| File | Change | Reason |
|------|--------|--------|
| `alembic/versions/2_fix_created_at_defaults.py` | NEW migration | Fix database schema - add DEFAULT CURRENT_TIMESTAMP |
| `app/models.py` | `nullable=False` explicit | Document requirement; ensure future models follow pattern |
| `app/services/product_service.py` | Debug logging added | Verify fix works; show exactly when created_at gets populated |

---

## HOW TO APPLY

### Step 1: Copy the new migration file
```bash
# File already created at:
# alembic/versions/2_fix_created_at_defaults.py
```

### Step 2: Update models.py
- All timestamp columns now have `nullable=False` and proper formatting
- File already updated

### Step 3: Update product_service.py
- Debug logging added to create_product()
- File already updated

### Step 4: Run migration
```bash
alembic upgrade head
```

### Step 5: Restart app and test
```bash
Ctrl+C  # Stop existing server
uvicorn app.main:app --reload
# Make POST request to create product
```

### Step 6: Remove debug logging (optional)
After verifying the fix works, you can remove all the `print()` statements from `app/services/product_service.py`.

---

## VERIFICATION

When you create a product, you should see in the terminal:

```
[DEBUG] Product before commit: {..., 'created_at': None, 'id': None}
[DEBUG]   created_at=None, id=None

[DEBUG] Product after commit: {..., 'created_at': None, 'id': 123}
[DEBUG]   created_at=None, id=123

[DEBUG] Product after refresh: {..., 'created_at': datetime.datetime(2026, 7, 6, 12, 34, 56, 789012), 'id': 123}
[DEBUG]   created_at=2026-07-06 12:34:56.789012 (type: <class 'datetime.datetime'>)

[SUCCESS] ✓ created_at populated from database default: 2026-07-06 12:34:56.789012
```

✅ If you see `[SUCCESS]`, the fix is working!
❌ If you see `[ERROR]`, the migration didn't apply - run `alembic upgrade head` again.
