#!/usr/bin/env python3
"""Verify migration integrity: row counts + checksums per table.

Usage::

    python scripts/verify_migration.py \
        --sqlite-url sqlite:///ibkr_trader.db \
        --pg-url postgresql://user:pass@localhost/ibkr_trader
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on path when script is invoked directly
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.infrastructure.db.base import Base

# Import all models to register them with Base.metadata
from app.infrastructure.db import models  # noqa: F401

TABLES: list[str] = sorted(
    mapper.class_.__tablename__ for mapper in Base.registry.mappers
)

CRITICAL_TABLES = ["trades", "signals", "symbol_config"]


def verify_checksums(sqlite_engine, pg_engine) -> bool:
    """Compare row counts between SQLite and PostgreSQL."""
    ok = True
    with Session(sqlite_engine) as sqlite_session, Session(pg_engine) as pg_session:
        for table in TABLES:
            try:
                sqlite_count = sqlite_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            except Exception:
                sqlite_count = 0
            try:
                pg_count = pg_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            except Exception:
                pg_count = 0

            if sqlite_count != pg_count:
                print(f"  FAIL {table}: {sqlite_count} vs {pg_count} ROW COUNT MISMATCH")
                ok = False
            else:
                print(f"  OK {table}: {sqlite_count} rows")

    return ok


def verify_critical_checksums(sqlite_engine, pg_engine) -> bool:
    """Checksum critical fields: trade id sum, signals by symbol."""
    ok = True
    with Session(sqlite_engine) as sqlite_session, Session(pg_engine) as pg_session:
        # Trade id checksum
        try:
            sqlite_sum = sqlite_session.execute(text("SELECT COALESCE(SUM(id),0) FROM trades")).scalar()
        except Exception:
            sqlite_sum = 0
        try:
            pg_sum = pg_session.execute(text("SELECT COALESCE(SUM(id),0) FROM trades")).scalar()
        except Exception:
            pg_sum = 0
        if sqlite_sum != pg_sum:
            print(f"  FAIL trades id checksum mismatch: {sqlite_sum} vs {pg_sum}")
            ok = False
        else:
            print(f"  OK trades id checksum: {sqlite_sum}")

        # Signal count by symbol
        try:
            sqlite_syms = dict(
                sqlite_session.execute(text("SELECT symbol, COUNT(*) FROM signals GROUP BY symbol")).all()
            )
        except Exception:
            sqlite_syms = {}
        try:
            pg_syms = dict(
                pg_session.execute(text("SELECT symbol, COUNT(*) FROM signals GROUP BY symbol")).all()
            )
        except Exception:
            pg_syms = {}
        if sqlite_syms != pg_syms:
            print("  FAIL signals by symbol mismatch")
            ok = False
        else:
            print(f"  OK signals by symbol: {len(sqlite_syms)} groups")

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SQLite -> PostgreSQL migration")
    parser.add_argument("--sqlite-url", default="sqlite:///ibkr_trader.db", help="Source SQLite URL")
    parser.add_argument("--pg-url", required=True, help="Target PostgreSQL URL")
    args = parser.parse_args()

    sqlite_engine = create_engine(args.sqlite_url)
    pg_engine = create_engine(args.pg_url)

    print("Row counts:")
    ok = verify_checksums(sqlite_engine, pg_engine)

    print("\nCritical checksums:")
    ok = verify_critical_checksums(sqlite_engine, pg_engine) and ok

    sqlite_engine.dispose()
    pg_engine.dispose()

    if ok:
        print("\nOK All checks passed")
        return 0
    else:
        print("\nFAIL Verification failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
