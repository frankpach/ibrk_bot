#!/usr/bin/env python3
"""Migrate data from SQLite to PostgreSQL.

Usage::

    python scripts/migrate_to_postgres.py \
        --sqlite-url sqlite:///ibkr_trader.db \
        --pg-url postgresql://user:pass@localhost/ibkr_trader

    python scripts/migrate_to_postgres.py --dry-run  # prints row counts without writing

Prerequisites::

    alembic upgrade head   # run against PostgreSQL first to create schema
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Type

# Ensure project root is on path when script is invoked directly
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from app.infrastructure.db.base import Base

# Import all models to register them with Base.metadata
from app.infrastructure.db import models  # noqa: F401

# Dynamically discover all mapped models so nothing is missed
MODELS: list[Type[DeclarativeBase]] = [mapper.class_ for mapper in Base.registry.mappers]


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgres://")


def migrate(sqlite_url: str, pg_url: str, dry_run: bool = False) -> dict[str, int]:
    """Migrate all tables from SQLite to PostgreSQL."""
    sqlite_engine = create_engine(sqlite_url)
    pg_engine = create_engine(pg_url)

    counts: dict[str, int] = {}

    with Session(sqlite_engine) as sqlite_session:
        for model in MODELS:
            table_name = model.__tablename__
            try:
                rows = sqlite_session.query(model).all()
            except Exception:
                rows = []

            counts[table_name] = len(rows)
            print(f"{table_name}: {len(rows)} rows {'(dry-run)' if dry_run else 'migrated'}")

            if not dry_run and rows:
                with Session(pg_engine) as pg_session:
                    if _is_postgres(pg_url):
                        pg_session.execute(
                            text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
                        )
                    else:
                        pg_session.execute(text(f"DELETE FROM {table_name}"))
                    for row in rows:
                        data = {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
                        pg_session.add(model(**data))
                    pg_session.commit()

    if not dry_run:
        verify_checksums(sqlite_engine, pg_engine, counts)

    sqlite_engine.dispose()
    pg_engine.dispose()
    return counts


def verify_checksums(sqlite_engine, pg_engine, expected_counts: dict[str, int]) -> None:
    """Verify row counts match after migration."""
    with Session(pg_engine) as pg_session:
        for table_name, expected in expected_counts.items():
            result = pg_session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            assert result == expected, f"Row count mismatch: {table_name} {expected} vs {result}"
            print(f"  {table_name}: {result} rows OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument("--sqlite-url", default="sqlite:///ibkr_trader.db", help="Source SQLite URL")
    parser.add_argument("--pg-url", required=True, help="Target PostgreSQL URL")
    parser.add_argument("--dry-run", action="store_true", help="Print row counts without writing")
    args = parser.parse_args()

    counts = migrate(args.sqlite_url, args.pg_url, dry_run=args.dry_run)
    print("\nMigration summary:")
    for table, count in counts.items():
        print(f"  {table}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
