"""001_initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

from app.infrastructure.db.base import Base

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables from SQLAlchemy models."""
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Drop all tables."""
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        op.execute("PRAGMA foreign_keys=OFF")
        tables = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        ).fetchall()
        for (table_name,) in tables:
            op.execute(f"DROP TABLE IF EXISTS {table_name}")
        op.execute("PRAGMA foreign_keys=ON")
    else:
        # PostgreSQL generic drop via metadata (slower but portable)
        from app.infrastructure.db.base import Base
        Base.metadata.drop_all(conn)
