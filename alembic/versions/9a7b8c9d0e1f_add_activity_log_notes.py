"""Add notes column to activity_logs

Revision ID: 9a7b8c9d0e1f
Revises: 8h5f6e8d4g5f
Create Date: 2026-07-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "9a7b8c9d0e1f"
down_revision = "8h5f6e8d4g5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("activity_logs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("activity_logs", schema=None) as batch_op:
        batch_op.drop_column("notes")
