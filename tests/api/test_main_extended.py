# tests/api/test_main_extended.py
import sys
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _fresh_client():
    for mod in list(sys.modules.keys()):
        if "app.api.main" in mod:
            del sys.modules[mod]
    from app.api.main import app
    return TestClient(app)


def _mock_account():
    return {"net_liquidation": 10000.0, "buying_power": 5000.0}


def _mock_portfolio():
    return []


# ---- Price endpoints ----

def test_get_price_success():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 150.0}
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/price/AAPL")
        assert resp.status_code == 200
        assert resp.json()["market_price"] == 150.0


def test_get_price_forbidden():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/price/FAKE")
        assert resp.status_code == 403


def test_get_price_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/price/AAPL")
        assert resp.status_code == 500


def test_get_price_free_success():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 150.0}
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/price/free/FAKE")
        assert resp.status_code == 200


def test_get_price_free_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/price/free/FAKE")
        assert resp.status_code == 500


# ---- Account / Portfolio error paths ----

def test_get_account_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_account.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/account")
        assert resp.status_code == 500


def test_get_portfolio_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_portfolio.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/portfolio")
        assert resp.status_code == 500


# ---- Orders preview ----

def test_orders_preview_sell():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.return_value = _mock_account()
        mock.get_portfolio.return_value = _mock_portfolio()
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/orders/preview", json={
            "symbol": "AAPL", "action": "SELL", "quantity": 1,
            "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "SELL"
        assert data["stop_loss_price"] > data["current_price"]


def test_orders_preview_price_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/orders/preview", json={
            "symbol": "AAPL", "action": "BUY", "quantity": 1,
            "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
        })
        assert resp.status_code == 500
        assert "price" in resp.json()["detail"].lower()


def test_orders_preview_account_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/orders/preview", json={
            "symbol": "AAPL", "action": "BUY", "quantity": 1,
            "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
        })
        assert resp.status_code == 500
        assert "account" in resp.json()["detail"].lower()


def test_orders_preview_portfolio_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.return_value = _mock_account()
        mock.get_portfolio.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/orders/preview", json={
            "symbol": "AAPL", "action": "BUY", "quantity": 1,
            "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
        })
        assert resp.status_code == 500
        assert "portfolio" in resp.json()["detail"].lower()


# ---- Orders place ----

def test_orders_place_success():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.return_value = _mock_account()
        mock.get_portfolio.return_value = _mock_portfolio()
        MockClient.return_value = mock
        client = _fresh_client()
        from app.risk.validator import ValidationResult
        with patch("app.api.main.validate_order", return_value=ValidationResult(approved=True, reasons=[])), \
             patch("app.config.settings.REQUIRE_HUMAN_APPROVAL", False), \
             patch("app.config.settings.PAPER_TRADING_ONLY", True), \
             patch("app.risk.lmt_orders.calculate_limit_price", return_value=99.5), \
             patch("app.ibkr.dedup.PreflightChecker") as MockPreflight, \
             patch("app.ibkr.dedup.get_deduplicator") as mock_dedup_get, \
             patch("app.notifications.order_monitor.OrderExecutionMonitor.place_and_monitor") as mock_place, \
             patch("app.db.database.insert_trade") as mock_insert:
            mock_preflight = MagicMock()
            mock_preflight.check.return_value = MagicMock(ok=True, reason=None)
            MockPreflight.return_value = mock_preflight
            from app.ibkr.dedup import OrderDeduplicator
            mock_dedup_get.return_value = OrderDeduplicator()
            mock_place.return_value = MagicMock(success=True, order_id="123", status="FILLED", fill_price=100.0, filled_quantity=1, reason=None)
            resp = client.post("/orders/place", json={
                "symbol": "AAPL", "action": "BUY", "quantity": 1,
                "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "placed"
            mock_insert.assert_called_once()


def test_orders_place_validation_fail():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.return_value = _mock_account()
        mock.get_portfolio.return_value = _mock_portfolio()
        MockClient.return_value = mock
        client = _fresh_client()
        from app.risk.validator import ValidationResult
        with patch("app.api.main.validate_order", return_value=ValidationResult(approved=False, reasons=["risk"])):
            resp = client.post("/orders/place", json={
                "symbol": "AAPL", "action": "BUY", "quantity": 1,
                "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
            })
            assert resp.status_code == 403


# ---- Close position ----

def test_close_position_success():
    trade = MagicMock()
    trade.symbol = "AAPL"
    trade.action = "BUY"
    trade.quantity = 10
    trade.entry_price = 100.0
    trade.id = 1
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 105.0}
        mock.place_order.return_value = {"order_id": "999"}
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.db.database.get_open_trades", return_value=[trade]), \
             patch("app.db.database.close_trade") as mock_close, \
             patch("app.ibkr.dedup.get_deduplicator") as mock_dedup_get, \
             patch("app.ibkr.dedup.PreflightChecker") as MockPreflight, \
             patch("app.ibkr.fill_tracker.get_fill_price_fallback", return_value=105.0):
            mock_preflight = MagicMock()
            mock_preflight.check.return_value = MagicMock(ok=True, reason=None)
            MockPreflight.return_value = mock_preflight
            from app.ibkr.dedup import OrderDeduplicator
            mock_dedup_get.return_value = OrderDeduplicator()
            resp = client.post("/orders/close/AAPL")
            assert resp.status_code == 200
            assert resp.json()["status"] == "closed"
            mock_close.assert_called_once()


# ---- Close all positions ----

def test_close_all_positions_with_trades():
    trade = MagicMock()
    trade.symbol = "AAPL"
    trade.action = "BUY"
    trade.quantity = 10
    trade.entry_price = 100.0
    trade.id = 1
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 105.0}
        mock.place_order.return_value = {"order_id": "999"}
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.db.database.get_open_trades", return_value=[trade]), \
             patch("app.db.database.close_trade") as mock_close, \
             patch("app.ibkr.dedup.get_deduplicator") as mock_dedup_get, \
             patch("app.ibkr.dedup.PreflightChecker") as MockPreflight, \
             patch("app.ibkr.fill_tracker.get_fill_price_fallback", return_value=105.0):
            mock_preflight = MagicMock()
            mock_preflight.check.return_value = MagicMock(ok=True, reason=None)
            MockPreflight.return_value = mock_preflight
            from app.ibkr.dedup import OrderDeduplicator
            mock_dedup_get.return_value = OrderDeduplicator()
            resp = client.post("/orders/close-all")
            assert resp.status_code == 200
            assert resp.json()["closed"] == 1
            mock_close.assert_called_once()


# ---- Dashboard ----

def test_dashboard():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.api.dashboard.render_dashboard_html", return_value="<html>ok</html>"):
            resp = client.get("/dashboard")
            assert resp.status_code == 200
            assert "html" in resp.text


# ---- Backtest ----

def test_backtest_success():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_account.return_value = {"net_liquidation": 1000.0}
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.backtest.engine.run_backtest", return_value={"sharpe": 1.5}), \
             patch("app.backtest.reporter.format_api", return_value={"sharpe": 1.5}):
            resp = client.get("/backtest/AAPL?days=30")
            assert resp.status_code == 200
            assert resp.json()["sharpe"] == 1.5


def test_backtest_forbidden():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/backtest/FAKE")
        assert resp.status_code == 403


def test_backtest_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_account.return_value = {"net_liquidation": 1000.0}
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.backtest.engine.run_backtest", side_effect=Exception("fail")):
            resp = client.get("/backtest/AAPL?days=30")
            assert resp.status_code == 500


# ---- Candidate analysis ----

def test_candidate_analysis():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {"score": 85}
        with patch("app.analysis.pipeline.AnalysisPipeline.run", return_value=mock_result):
            resp = client.get("/candidate-analysis/AAPL")
            assert resp.status_code == 200
            assert resp.json()["score"] == 85


def test_candidate_analysis_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.analysis.pipeline.AnalysisPipeline.run", side_effect=Exception("fail")):
            resp = client.get("/candidate-analysis/AAPL")
            assert resp.status_code == 500


# ---- Single indicator ----

def test_single_indicator_success():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.llm.agent.get_data_layer") as mock_dl, \
             patch("app.analysis.indicators.compute_single_indicator", return_value=50.0):
            mock_data = MagicMock()
            mock_data.get_ohlcv.return_value = MagicMock(empty=False)
            mock_dl.return_value = mock_data
            resp = client.get("/analysis/indicator/AAPL/RSI")
            assert resp.status_code == 200
            assert resp.json()["value"] == 50.0


def test_single_indicator_no_data():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.llm.agent.get_data_layer") as mock_dl:
            mock_data = MagicMock()
            mock_data.get_ohlcv.return_value = None
            mock_dl.return_value = mock_data
            resp = client.get("/analysis/indicator/AAPL/RSI")
            assert resp.status_code == 404


# ---- Executions error ----

def test_executions_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_executions.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/executions")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


# ---- Commission report ----

def test_commission_report():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_commissions.return_value = {"total": 10.0}
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/account/commission-report")
        assert resp.status_code == 200
        assert resp.json()["total"] == 10.0


def test_commission_report_error():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_commissions.side_effect = Exception("fail")
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/account/commission-report")
        assert resp.status_code == 200
        assert "error" in resp.json()


# ---- Proposals / Approve ----

def test_get_proposals():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.db.database.get_pending_proposals", return_value=[{"symbol": "NFLX"}]):
            resp = client.get("/symbols/proposals")
            assert resp.status_code == 200
            assert resp.json()[0]["symbol"] == "NFLX"


def test_approve_symbol():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.db.database.approve_symbol") as mock_approve:
            resp = client.post("/symbols/approve/NFLX")
            assert resp.status_code == 200
            assert resp.json()["status"] == "approved"
            mock_approve.assert_called_once()


# ---- System status with no controller ----

def test_system_status_no_controller():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_account.return_value = {"net_liquidation": 1000.0}
        MockClient.return_value = mock
        client = _fresh_client()
        with patch("app.system.controller.get_controller", side_effect=RuntimeError("not init")):
            resp = client.get("/system/status")
            assert resp.status_code == 200
            assert resp.json()["mode"] == "paper"


# ---- Orders place human approval timeout ----

def test_orders_place_human_reject():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.return_value = _mock_account()
        mock.get_portfolio.return_value = _mock_portfolio()
        MockClient.return_value = mock
        client = _fresh_client()
        from app.risk.validator import ValidationResult
        with patch("app.api.main.validate_order", return_value=ValidationResult(approved=True, reasons=[])), \
             patch("app.config.settings.REQUIRE_HUMAN_APPROVAL", True), \
             patch("app.notifications.telegram.request_approval", return_value=False):
            resp = client.post("/orders/place", json={
                "symbol": "AAPL", "action": "BUY", "quantity": 1,
                "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
            })
            assert resp.status_code == 403


# ---- Orders place preflight fail ----

def test_orders_place_preflight_fail():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.return_value = _mock_account()
        mock.get_portfolio.return_value = _mock_portfolio()
        MockClient.return_value = mock
        client = _fresh_client()
        from app.risk.validator import ValidationResult
        with patch("app.api.main.validate_order", return_value=ValidationResult(approved=True, reasons=[])), \
             patch("app.config.settings.REQUIRE_HUMAN_APPROVAL", False), \
             patch("app.config.settings.PAPER_TRADING_ONLY", True), \
             patch("app.ibkr.dedup.PreflightChecker") as MockPreflight, \
             patch("app.ibkr.dedup.get_deduplicator") as mock_dedup_get:
            mock_preflight = MagicMock()
            mock_preflight.check.return_value = MagicMock(ok=False, reason="market closed")
            MockPreflight.return_value = mock_preflight
            from app.ibkr.dedup import OrderDeduplicator
            mock_dedup_get.return_value = OrderDeduplicator()
            resp = client.post("/orders/place", json={
                "symbol": "AAPL", "action": "BUY", "quantity": 1,
                "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
            })
            assert resp.status_code == 403


# ---- Orders place dedup block ----

def test_orders_place_dedup_block():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_stock_price.return_value = {"market_price": 100.0}
        mock.get_account.return_value = _mock_account()
        mock.get_portfolio.return_value = _mock_portfolio()
        MockClient.return_value = mock
        client = _fresh_client()
        from app.risk.validator import ValidationResult
        with patch("app.api.main.validate_order", return_value=ValidationResult(approved=True, reasons=[])), \
             patch("app.config.settings.REQUIRE_HUMAN_APPROVAL", False), \
             patch("app.config.settings.PAPER_TRADING_ONLY", True), \
             patch("app.ibkr.dedup.PreflightChecker") as MockPreflight, \
             patch("app.ibkr.dedup.get_deduplicator") as mock_dedup_get:
            mock_preflight = MagicMock()
            mock_preflight.check.return_value = MagicMock(ok=True, reason=None)
            MockPreflight.return_value = mock_preflight
            dedup = MagicMock()
            dedup.is_duplicate.return_value = True
            mock_dedup_get.return_value = dedup
            resp = client.post("/orders/place", json={
                "symbol": "AAPL", "action": "BUY", "quantity": 1,
                "order_type": "MKT", "stop_loss_pct": 0.02, "take_profit_pct": 0.04,
            })
            assert resp.status_code == 429
