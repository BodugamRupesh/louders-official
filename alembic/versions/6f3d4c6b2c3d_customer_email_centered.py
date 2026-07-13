"""Switch customer identity from Discord username to unique email.

Revision ID: 6f3d4c6b2c3d
Revises: bf0cadda44c7
Create Date: 2026-07-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "6f3d4c6b2c3d"
down_revision = "bf0cadda44c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.drop_index("ix_customers_discord_username")
        batch_op.drop_column("discord_username")
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=150),
            nullable=False,
            existing_nullable=True,
        )
        batch_op.create_unique_constraint("uq_customers_email", ["email"])


def downgrade() -> None:
    with op.batch_alter_table("customers", schema=None) as batch_op:
        batch_op.drop_constraint("uq_customers_email", type_="unique")
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=150),
            nullable=True,
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("discord_username", sa.String(length=100), nullable=True))
        batch_op.create_index("ix_customers_discord_username", ["discord_username"], unique=False)
