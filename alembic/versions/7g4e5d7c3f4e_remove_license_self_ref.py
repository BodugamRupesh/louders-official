"""Remove self-referencing license_id from licenses table.

Revision ID: 7g4e5d7c3f4e
Revises: 6f3d4c6b2c3d
Create Date: 2026-07-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "7g4e5d7c3f4e"
down_revision = "6f3d4c6b2c3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("licenses", schema=None) as batch_op:
        batch_op.drop_index("ix_licenses_license_id")
        batch_op.drop_column("license_id")


def downgrade() -> None:
    with op.batch_alter_table("licenses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("license_id", sa.Integer(), nullable=False))
        batch_op.create_foreign_key(
            None,
            "licenses",
            ["license_id"],
            ["id"],
            ondelete="CASCADE"
        )
        batch_op.create_index("ix_licenses_license_id", ["license_id"], unique=False)
