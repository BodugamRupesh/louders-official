"""Add device_fingerprint to devices table.

Revision ID: a1b2c3d4e5f6
Revises: 9a7b8c9d0e1f
Create Date: 2026-07-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "9a7b8c9d0e1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("device_fingerprint", sa.String(length=255), nullable=True))
        batch_op.create_index("ix_devices_device_fingerprint", ["device_fingerprint"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_index("ix_devices_device_fingerprint")
        batch_op.drop_column("device_fingerprint")
