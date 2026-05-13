# tests/api/test_endpoints.py
import sys
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _fresh_client():
    for mod in list(sys.modules.keys()):
        if "app.api.main" in mod:
            del sys.modules[mod]
    from app.api.main import app
    return TestClient(app)


def test_health():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


def test_get_account():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.get_account.return_value = {"net_liquidation": 1000.0}
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/account")
        assert resp.status_code == 200
        assert resp.json()["net_liquidation"] == 1000.0


def test_get_portfolio():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.get_portfolio.return_value = [{"symbol": "AAPL"}]
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/portfolio")
        assert resp.status_code == 200
        assert resp.json()[0]["symbol"] == "AAPL"


def test_allowed_symbols():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/allowed-symbols")
        assert resp.status_code == 200
        assert "symbols" in resp.json()


def test_propose_symbol():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/symbols/propose", json={"symbol": "NFLX", "reason": "test"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_approval"


def test_get_signals():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/signals")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_get_trades():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/trades")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_get_executions():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.get_executions.return_value = [{"symbol": "AAPL"}]
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/executions")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1


def test_get_patterns():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/patterns/AAPL")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def _mock_controller():
    ctrl = MagicMock()
    ctrl.status.return_value = {
        "paused": False, "mode": "paper", "circuit_breaker_threshold": "5%"
    }

    def _set_mode(mode: str):
        if mode not in ("paper", "live"):
            raise ValueError(f"Invalid mode: {mode}")
        ctrl.mode = mode

    ctrl.set_mode = _set_mode
    return ctrl


def test_system_status():
    with patch("app.ibkr.client.IBKRClient") as MockClient, \
         patch("app.system.controller.get_controller", return_value=_mock_controller()):
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        mock.get_account.return_value = {"net_liquidation": 1000.0}
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/system/status")
        assert resp.status_code == 200
        assert "open_positions" in resp.json()


def test_system_pause_resume():
    with patch("app.ibkr.client.IBKRClient") as MockClient, \
         patch("app.system.controller.get_controller", return_value=_mock_controller()):
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/system/pause")
        assert resp.status_code == 200
        resp = client.post("/system/resume")
        assert resp.status_code == 200


def test_system_mode():
    with patch("app.ibkr.client.IBKRClient") as MockClient, \
         patch("app.system.controller.get_controller", return_value=_mock_controller()):
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/system/mode/paper")
        assert resp.status_code == 200
        resp = client.post("/system/mode/invalid")
        assert resp.status_code == 400


def test_get_closed_trades():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/trades/closed")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_close_position_not_found():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/orders/close/FAKE")
        assert resp.status_code == 404


def test_close_all_positions_empty():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.post("/orders/close-all")
        assert resp.status_code == 200
        assert resp.json()["closed"] == 0


def test_universe_watchlist():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/universe/watchlist")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_candidate_decisions():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/candidate-decisions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_symbol_parameters():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/symbol-parameters/AAPL")
        assert resp.status_code == 200
        assert "momentum_mult" in resp.json()


def test_market_permissions():
    with patch("app.ibkr.client.IBKRClient") as MockClient:
        mock = MagicMock()
        mock.ib.isConnected.return_value = True
        MockClient.return_value = mock
        client = _fresh_client()
        resp = client.get("/market-permissions")
        assert resp.status_code in (200, 503)
