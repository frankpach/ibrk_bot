# tests/test_issue008_sqlalchemy_alembic.py
"""Tests for Issue 008: SQLAlchemy Models, Alembic y Repositorios."""
from __future__ import annotations

import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (
    TradeModel,
    SignalModel,
    SymbolConfigModel,
    ControlSettingModel,
    AuditLogModel,
    BackgroundJobModel,
)


class TestNoLegacyImports:
    def test_zero_app_imports_from_database_py(self):
        """grep -r 'from app.db.database import' app/ must return 0 results."""
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_dir = os.path.join(project_root, "app")
        count = 0
        for root, _dirs, files in os.walk(app_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    if "from app.db.database import" in content or "import app.db.database" in content:
                        count += 1
                        print(f"FOUND: {path}")
                except Exception:
                    pass
        assert count == 0, f"Found {count} files in app/ still importing from app.db.database"


class TestAlembic:
    def test_upgrade_head_from_empty_db(self, tmp_path):
        """alembic upgrade head from empty DB creates schema in <5s."""
        db_path = tmp_path / "test.db"
        url = f"sqlite:///{db_path}"
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        engine = create_engine(url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "trades" in tables
        assert "signals" in tables
        assert "control_settings" in tables
        assert "background_jobs" in tables

    def test_downgrade_base_clears_db(self, tmp_path):
        """alembic downgrade base drops all tables."""
        db_path = tmp_path / "test.db"
        url = f"sqlite:///{db_path}"
        subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "downgrade", "base"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        engine = create_engine(url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "trades" not in tables
        assert "signals" not in tables
        # alembic_version may remain — that's fine
        assert all(t == "alembic_version" for t in tables)

    def test_upgrade_twice_is_idempotent(self, tmp_path):
        """Running upgrade head twice must not error."""
        db_path = tmp_path / "test.db"
        url = f"sqlite:///{db_path}"
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "-x", f"sqlalchemy.url={url}", "upgrade", "head"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, result.stderr


class TestModelsInMemory:
    def test_create_all_tables_in_memory(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = {
            "trades", "signals", "patterns", "symbol_config", "decisions",
            "audit_log", "control_settings", "active_symbols", "alerts",
            "feature_snapshots", "symbol_parameters", "candidate_decisions",
            "watchlist_scores", "position_snapshots", "account_snapshots",
            "news_cache", "scanner_results", "analysis_reports",
            "daily_watchlist", "market_permissions", "background_jobs",
        }
        assert expected.issubset(set(tables))

    def test_trade_crud_in_memory(self):
        from sqlalchemy.orm import Session
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            trade = TradeModel(
                symbol="AAPL", action="BUY", quantity=10.0,
                entry_price=150.0, stop_loss_price=145.0,
                take_profit_price=160.0, stop_loss_pct=0.025,
                take_profit_pct=0.06, signal_strength="STRONG",
                status="OPEN", opened_at="2026-05-14T12:00:00",
            )
            session.add(trade)
            session.commit()
            assert trade.id is not None

        with Session(engine) as session:
            row = session.query(TradeModel).filter_by(status="OPEN").first()
            assert row is not None
            assert row.symbol == "AAPL"

    def test_control_setting_crud_in_memory(self):
        from sqlalchemy.orm import Session
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            setting = ControlSettingModel(
                key="max_risk_pct", value="0.015",
                updated_at="2026-05-14T12:00:00",
            )
            session.add(setting)
            session.commit()

        with Session(engine) as session:
            row = session.query(ControlSettingModel).filter_by(key="max_risk_pct").first()
            assert row is not None
            assert row.value == "0.015"

    def test_audit_log_insert_in_memory(self):
        from sqlalchemy.orm import Session
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            log = AuditLogModel(
                event_type="test", occurred_at="2026-05-14T12:00:00",
            )
            session.add(log)
            session.commit()
            assert log.id is not None

    def test_background_job_insert_in_memory(self):
        from sqlalchemy.orm import Session
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            job = BackgroundJobModel(
                job_id="test-uuid", job_type="llm-analysis",
                status="pending", created_at="2026-05-14T12:00:00",
            )
            session.add(job)
            session.commit()
            assert session.query(BackgroundJobModel).filter_by(job_id="test-uuid").first() is not None
