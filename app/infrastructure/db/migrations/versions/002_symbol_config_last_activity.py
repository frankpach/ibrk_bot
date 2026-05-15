"""Add last_activity_at to symbol_config

Revision ID: 002
Revises: 001_initial_schema
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("symbol_config") as batch_op:
        batch_op.add_column(
            sa.Column("last_activity_at", sa.Text, nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("symbol_config") as batch_op:
        batch_op.drop_column("last_activity_at")
