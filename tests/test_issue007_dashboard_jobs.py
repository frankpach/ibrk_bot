# tests/test_issue007_dashboard_jobs.py
"""Tests for Issue 007: Dashboard Read Models y Background Jobs."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.db.compat import get_connection
from app.application.services.job_runner import BackgroundJobRunner, set_global_runner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_global_runner():
    """Ensure no stale global runner leaks between tests."""
    set_global_runner(None)
    yield
    set_global_runner(None)


@pytest.fixture
def client():
    os.environ["API_CONTROL_KEY"] = "test-control-key"
    os.environ["API_ADMIN_KEY"] = "test-admin-key"
    import app.config.settings as settings_mod
    import importlib
    importlib.reload(settings_mod)
    import app.infrastructure.db.compat as db_mod
    db_mod.DB_PATH = getattr(settings_mod, "DB_PATH", db_mod.DB_PATH)
    from app.api.main import app
    with TestClient(app) as c:
        yield c
    os.environ.pop("API_CONTROL_KEY", None)
    os.environ.pop("API_ADMIN_KEY", None)


@pytest.fixture
def seed_dashboard_db():
    """Seed minimal data for DashboardDataQuery tests."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO trades (symbol, action, quantity, entry_price, stop_loss_price, take_profit_price, stop_loss_pct, take_profit_pct, signal_strength, status, opened_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("AAPL", "BUY", 10.0, 150.0, 145.0, 160.0, 0.025, 0.06, "STRONG", "OPEN", now)
    )
    conn.execute(
        "INSERT OR REPLACE INTO trades (symbol, action, quantity, entry_price, stop_loss_price, take_profit_price, stop_loss_pct, take_profit_pct, signal_strength, status, opened_at, closed_at, exit_price, exit_reason, pnl_usd, pnl_pct) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("MSFT", "BUY", 5.0, 300.0, 290.0, 320.0, 0.025, 0.06, "MEDIUM", "CLOSED", now, now, 310.0, "TAKE PROFIT", 50.0, 0.033)
    )
    conn.execute(
        "INSERT OR REPLACE INTO signals (symbol, strength, rsi, macd, volume_ratio, created_at) VALUES (?,?,?,?,?,?)",
        ("NVDA", "STRONG", 65.0, 0.5, 2.1, now)
    )
    conn.execute(
        "INSERT OR REPLACE INTO account_snapshots (date, net_liquidation, buying_power, daily_pnl_usd, daily_pnl_pct, created_at) VALUES (?,?,?,?,?,?)",
        (now[:10], 10000.0, 5000.0, 100.0, 0.01, now)
    )
    conn.execute(
        "INSERT OR REPLACE INTO news_cache (symbol, headline, provider, sentiment, fetched_at) VALUES (?,?,?,?,?)",
        ("AAPL", "Test headline", "Reuters", "positive", now)
    )
    conn.execute(
        "INSERT OR REPLACE INTO scanner_results (scan_type, symbol, name, change_pct, volume_ratio, fetched_at) VALUES (?,?,?,?,?,?)",
        ("most_active", "TSLA", "Tesla Inc", 2.5, 3.0, now)
    )
    conn.execute(
        "INSERT OR REPLACE INTO daily_watchlist (date, symbol, score, signal_strength, change_pct, reason, added_at) VALUES (?,?,?,?,?,?,?)",
        (now[:10], "AMD", 75.0, "STRONG", 1.5, "Momentum", now)
    )
    conn.execute(
        "INSERT OR REPLACE INTO symbol_config (symbol, approved, created_at) VALUES (?,?,?)",
        ("AAPL", 1, now)
    )
    conn.commit()
    conn.close()
    yield
    # cleanup
    conn = get_connection()
    conn.execute("DELETE FROM trades")
    conn.execute("DELETE FROM signals")
    conn.execute("DELETE FROM account_snapshots")
    conn.execute("DELETE FROM news_cache")
    conn.execute("DELETE FROM scanner_results")
    conn.execute("DELETE FROM daily_watchlist")
    conn.execute("DELETE FROM symbol_config WHERE symbol='AAPL'")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# DashboardDataQuery tests
# ---------------------------------------------------------------------------

class TestDashboardDataQuery:
    def test_returns_expected_keys(self, seed_dashboard_db):
        from app.infrastructure.db.read_models.dashboard_query import DashboardDataQuery
        query = DashboardDataQuery()
        result = query.execute()
        assert "status" in result
        assert "open_trades" in result
        assert "closed_trades" in result
        assert "signals" in result
        assert "news" in result
        assert "scanner" in result
        assert "daily_watchlist" in result
        assert "symbols_universe" in result
        assert "ib_connected" in result

    def test_open_trades_populated(self, seed_dashboard_db):
        from app.infrastructure.db.read_models.dashboard_query import DashboardDataQuery
        result = DashboardDataQuery().execute()
        assert len(result["open_trades"]) >= 1
        assert result["open_trades"][0]["symbol"] == "AAPL"

    def test_closed_trades_limited(self, seed_dashboard_db):
        from app.infrastructure.db.read_models.dashboard_query import DashboardDataQuery
        result = DashboardDataQuery().execute()
        assert len(result["closed_trades"]) <= 8

    def test_status_has_mode(self, seed_dashboard_db):
        from app.infrastructure.db.read_models.dashboard_query import DashboardDataQuery
        result = DashboardDataQuery().execute()
        assert "mode" in result["status"]

    def test_no_write_imports(self):
        """DashboardDataQuery must not import write use cases."""
        import inspect
        from app.infrastructure.db.read_models import dashboard_query as mod
        source = inspect.getsource(mod)
        assert "UpdateControlSettingUseCase" not in source
        assert "PauseSystemUseCase" not in source
        assert "insert_trade" not in source


# ---------------------------------------------------------------------------
# BackgroundJobRunner tests
# ---------------------------------------------------------------------------

class TestBackgroundJobRunner:
    def test_submit_returns_job_id(self):
        runner = BackgroundJobRunner(max_workers=2)
        job_id = runner.submit("test", lambda: {"ok": True})
        assert isinstance(job_id, str)
        assert len(job_id) == 36  # uuid4
        runner.shutdown(wait=True)

    def test_job_transitions_to_success(self):
        runner = BackgroundJobRunner(max_workers=2)
        job_id = runner.submit("test", lambda: {"ok": True})
        # wait for completion
        for _ in range(50):
            job = runner.get_job(job_id)
            if job["status"] in ("success", "failed"):
                break
            time.sleep(0.05)
        job = runner.get_job(job_id)
        assert job["status"] == "success"
        assert job["result"]["ok"] is True
        runner.shutdown(wait=True)

    def test_job_transitions_to_failed(self):
        runner = BackgroundJobRunner(max_workers=2)
        job_id = runner.submit("test", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        for _ in range(50):
            job = runner.get_job(job_id)
            if job["status"] in ("success", "failed"):
                break
            time.sleep(0.05)
        job = runner.get_job(job_id)
        assert job["status"] == "failed"
        assert "boom" in job["error"]
        runner.shutdown(wait=True)

    def test_job_times_out(self):
        runner = BackgroundJobRunner(max_workers=2)
        def slow_fn():
            time.sleep(5)
            return {"ok": True}
        job_id = runner.submit("test", slow_fn, timeout_seconds=1)
        for _ in range(80):
            job = runner.get_job(job_id)
            if job["status"] == "failed":
                break
            time.sleep(0.05)
        job = runner.get_job(job_id)
        assert job["status"] == "failed"
        assert "timeout" in job["error"].lower()
        runner.shutdown(wait=True)

    def test_list_jobs_filters(self):
        runner = BackgroundJobRunner(max_workers=2)
        jid1 = runner.submit("llm-analysis", lambda: {"ok": True})
        jid2 = runner.submit("backtest", lambda: {"ok": True})
        time.sleep(0.1)
        jobs = runner.list_jobs(job_type="llm-analysis")
        assert len(jobs) >= 1
        assert all(j["job_type"] == "llm-analysis" for j in jobs)
        runner.shutdown(wait=True)


# ---------------------------------------------------------------------------
# Jobs API tests
# ---------------------------------------------------------------------------

class TestJobsAPI:
    def test_post_llm_analysis_returns_job_id(self, client):
        from app.application.services.job_runner import BackgroundJobRunner, set_global_runner
        runner = BackgroundJobRunner(max_workers=2)
        set_global_runner(runner)
        try:
            resp = client.post("/jobs/llm-analysis", json={"symbol": "AAPL"})
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
            assert isinstance(data["job_id"], str)
        finally:
            runner.shutdown(wait=True)
            set_global_runner(None)

    def test_post_backtest_returns_job_id(self, client):
        from app.application.services.job_runner import BackgroundJobRunner, set_global_runner
        runner = BackgroundJobRunner(max_workers=2)
        set_global_runner(runner)
        try:
            resp = client.post("/jobs/backtest", json={"symbol": "AAPL", "days": 30})
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
        finally:
            runner.shutdown(wait=True)
            set_global_runner(None)

    def test_get_job_reflects_status(self, client):
        from app.application.services.job_runner import BackgroundJobRunner, set_global_runner
        runner = BackgroundJobRunner(max_workers=2)
        set_global_runner(runner)
        try:
            resp = client.post("/jobs/llm-analysis", json={"symbol": "AAPL"})
            job_id = resp.json()["job_id"]
            resp2 = client.get(f"/jobs/{job_id}")
            assert resp2.status_code == 200
            data = resp2.json()
            assert data["job_id"] == job_id
            assert data["status"] in ("pending", "running", "success", "failed")
        finally:
            runner.shutdown(wait=True)
            set_global_runner(None)

    def test_get_jobs_list(self, client):
        from app.application.services.job_runner import BackgroundJobRunner, set_global_runner
        runner = BackgroundJobRunner(max_workers=2)
        set_global_runner(runner)
        try:
            client.post("/jobs/llm-analysis", json={"symbol": "AAPL"})
            resp = client.get("/jobs?type=llm-analysis")
            assert resp.status_code == 200
            data = resp.json()
            assert "jobs" in data
        finally:
            runner.shutdown(wait=True)
            set_global_runner(None)

    def test_candidate_analysis_returns_job_id(self, client):
        from app.application.services.job_runner import BackgroundJobRunner, set_global_runner
        runner = BackgroundJobRunner(max_workers=2)
        set_global_runner(runner)
        try:
            resp = client.get("/candidate-analysis/AAPL")
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
        finally:
            runner.shutdown(wait=True)
            set_global_runner(None)

    def test_backtest_endpoint_returns_job_id(self, client):
        from app.application.services.job_runner import BackgroundJobRunner, set_global_runner
        runner = BackgroundJobRunner(max_workers=2)
        set_global_runner(runner)
        try:
            resp = client.get("/backtest/AAPL?days=30")
            assert resp.status_code == 200
            data = resp.json()
            assert "job_id" in data
        finally:
            runner.shutdown(wait=True)
            set_global_runner(None)


# ---------------------------------------------------------------------------
# Dashboard data endpoint performance contract
# ---------------------------------------------------------------------------

class TestDashboardDataEndpoint:
    def test_dashboard_data_returns_200(self, client, seed_dashboard_db):
        resp = client.get("/dashboard/data")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_dashboard_data_has_required_keys(self, client, seed_dashboard_db):
        resp = client.get("/dashboard/data")
        data = resp.json()
        for key in ("status", "open_trades", "closed_trades", "signals", "patterns",
                    "position_snapshots", "learning", "account_history", "latest_account",
                    "news", "scanner", "symbols_universe", "ib_connected", "earnings_warnings", "daily_watchlist"):
            assert key in data, f"Missing key: {key}"
