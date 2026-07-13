"""Add license_key and activation tracking fields to licenses table.

Revision ID: 8h5f6e8d4g5f
Revises: 7g4e5d7c3f4e
Create Date: 2026-07-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "8h5f6e8d4g5f"
down_revision = "7g4e5d7c3f4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("licenses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("license_key", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("activated_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("activated_device_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.create_unique_constraint("uq_licenses_license_key", ["license_key"])
        batch_op.create_index("ix_licenses_license_key", ["license_key"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("licenses", schema=None) as batch_op:
        batch_op.drop_index("ix_licenses_license_key")
        batch_op.drop_constraint("uq_licenses_license_key", type_="unique")
        batch_op.drop_column("activated_device_count")
        batch_op.drop_column("activated_at")
        batch_op.drop_column("license_key")
