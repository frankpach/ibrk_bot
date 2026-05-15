# tests/test_issue009_postgresql.py
"""Tests for Issue 009: PostgreSQL migration and dual backend support."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.infrastructure.db.base import Base
from app.infrastructure.db.engine import get_engine, get_database_url, reset_engine, _is_postgres
from app.infrastructure.db.models import (
    TradeModel,
    SignalModel,
    SymbolConfigModel,
    AuditLogModel,
    ControlSettingModel,
)


class TestEngineFactory:
    def test_default_url_uses_sqlite(self):
        url = get_database_url()
        assert url.startswith("sqlite:///")

    def test_database_url_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        url = get_database_url()
        assert url == "postgresql://user:pass@localhost/db"

    def test_is_postgres_detects_postgresql(self):
        assert _is_postgres("postgresql://localhost/db")
        assert _is_postgres("postgres://localhost/db")
        assert not _is_postgres("sqlite:///db.sqlite")

    def test_get_engine_sqlite_in_memory(self):
        reset_engine()
        engine = get_engine("sqlite:///:memory:")
        assert engine is not None
        reset_engine()

    def test_get_engine_caches_same_instance(self):
        reset_engine()
        e1 = get_engine("sqlite:///:memory:")
        e2 = get_engine("sqlite:///:memory:")
        assert e1 is e2
        reset_engine()


class TestMigrationScripts:
    def test_migrate_script_exists(self):
        assert os.path.exists("scripts/migrate_to_postgres.py")
        assert os.path.exists("scripts/verify_migration.py")

    def test_migrate_dry_run_on_empty_sqlite(self, tmp_path):
        """Dry-run against empty SQLite should complete without error."""
        db_path = tmp_path / "empty.db"
        sqlite_url = f"sqlite:///{db_path}"
        pg_url = "sqlite:///:memory:"  # SQLite stand-in for PostgreSQL in CI

        result = subprocess.run(
            [
                sys.executable,
                "scripts/migrate_to_postgres.py",
                "--sqlite-url",
                sqlite_url,
                "--pg-url",
                pg_url,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "dry-run" in result.stdout

    def test_migrate_with_data_and_verify(self, tmp_path):
        """Migrate real data and verify counts match."""
        db_path = tmp_path / "source.db"
        target_path = tmp_path / "target.db"
        sqlite_url = f"sqlite:///{db_path}"
        pg_url = f"sqlite:///{target_path}"  # file-based stand-in for PostgreSQL in CI

        # Seed SQLite
        sqlite_engine = create_engine(sqlite_url)
        Base.metadata.create_all(sqlite_engine)
        with Session(sqlite_engine) as s:
            s.add(
                TradeModel(
                    symbol="AAPL",
                    action="BUY",
                    quantity=10.0,
                    entry_price=150.0,
                    stop_loss_price=145.0,
                    take_profit_price=160.0,
                    stop_loss_pct=0.025,
                    take_profit_pct=0.06,
                    signal_strength="STRONG",
                    status="OPEN",
                    opened_at="2026-05-14T12:00:00",
                )
            )
            s.add(SignalModel(symbol="AAPL", strength="STRONG", created_at="2026-05-14T12:00:00"))
            s.add(SymbolConfigModel(symbol="AAPL", created_at="2026-05-14T12:00:00"))
            s.commit()

        # Create schema on target (simulates "alembic upgrade head" against PostgreSQL)
        target_engine = create_engine(pg_url)
        Base.metadata.create_all(target_engine)
        target_engine.dispose()

        # Migrate
        result = subprocess.run(
            [
                sys.executable,
                "scripts/migrate_to_postgres.py",
                "--sqlite-url",
                sqlite_url,
                "--pg-url",
                pg_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr

        # Verify
        result2 = subprocess.run(
            [
                sys.executable,
                "scripts/verify_migration.py",
                "--sqlite-url",
                sqlite_url,
                "--pg-url",
                pg_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result2.returncode == 0, result2.stderr
        assert "trades: 1 rows" in result2.stdout


class TestParametrizedBackend:
    @pytest.fixture(params=["sqlite", "postgres"])
    def engine(self, request):
        if request.param == "postgres":
            pg_url = os.environ.get("TEST_PG_URL")
            if not pg_url:
                pytest.skip("TEST_PG_URL not set")
            engine = create_engine(pg_url)
        else:
            engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        yield engine
        Base.metadata.drop_all(engine)
        engine.dispose()

    def test_trade_crud(self, engine):
        with Session(engine) as session:
            trade = TradeModel(
                symbol="TSLA",
                action="BUY",
                quantity=5.0,
                entry_price=200.0,
                stop_loss_price=190.0,
                take_profit_price=220.0,
                stop_loss_pct=0.05,
                take_profit_pct=0.10,
                signal_strength="MEDIUM",
                status="OPEN",
                opened_at="2026-05-14T12:00:00",
            )
            session.add(trade)
            session.commit()
            assert trade.id is not None

        with Session(engine) as session:
            row = session.query(TradeModel).filter_by(symbol="TSLA").first()
            assert row is not None
            assert row.action == "BUY"

    def test_signal_crud(self, engine):
        with Session(engine) as session:
            signal = SignalModel(
                symbol="MSFT", strength="WEAK", created_at="2026-05-14T12:00:00"
            )
            session.add(signal)
            session.commit()
            assert signal.id is not None

        with Session(engine) as session:
            row = session.query(SignalModel).filter_by(symbol="MSFT").first()
            assert row is not None
