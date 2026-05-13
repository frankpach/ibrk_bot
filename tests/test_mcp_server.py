# tests/test_mcp_server.py
import sys
from unittest.mock import patch, MagicMock
import pytest


def make_response(data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = data
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    return mock


def _import_mcp_server():
    """Force reimport so patches are applied before module loads."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("app.mcp.server"):
            del sys.modules[mod]
    from app.mcp.server import get_price, get_account, get_portfolio, get_signals, get_patterns, preview_order, place_order
    return get_price, get_account, get_portfolio, get_signals, get_patterns, preview_order, place_order


@patch("httpx.get")
def test_get_price_calls_correct_endpoint(mock_get):
    mock_get.return_value = make_response({"symbol": "AAPL", "market_price": 287.64})
    get_price, *_ = _import_mcp_server()
    result = get_price("aapl")
    mock_get.assert_called_once_with("http://127.0.0.1:8088/price/AAPL", timeout=30.0)
    assert result["market_price"] == 287.64


@patch("httpx.get")
def test_get_price_uppercases_symbol(mock_get):
    mock_get.return_value = make_response({"symbol": "MSFT", "market_price": 420.0})
    get_price, *_ = _import_mcp_server()
    get_price("msft")
    mock_get.assert_called_once_with("http://127.0.0.1:8088/price/MSFT", timeout=30.0)


@patch("httpx.get")
def test_get_account_returns_data(mock_get):
    mock_get.return_value = make_response({"net_liquidation": 1000000.0, "buying_power": 500000.0})
    _, get_account, *_ = _import_mcp_server()
    result = get_account()
    assert result["net_liquidation"] == 1000000.0


@patch("httpx.get")
def test_get_portfolio_returns_list(mock_get):
    mock_get.return_value = make_response([])
    _, _, get_portfolio, *_ = _import_mcp_server()
    result = get_portfolio()
    assert isinstance(result, list)


@patch("httpx.get")
def test_get_signals_returns_list(mock_get):
    mock_get.return_value = make_response([{"symbol": "AAPL", "strength": "STRONG"}])
    _, _, _, get_signals, *_ = _import_mcp_server()
    result = get_signals()
    assert result[0]["strength"] == "STRONG"


@patch("httpx.get")
def test_get_patterns_uppercases_symbol(mock_get):
    mock_get.return_value = make_response([])
    _, _, _, _, get_patterns, *_ = _import_mcp_server()
    get_patterns("aapl")
    mock_get.assert_called_once_with("http://127.0.0.1:8088/patterns/AAPL", timeout=30.0)


@patch("httpx.post")
def test_preview_order_sends_correct_payload(mock_post):
    mock_post.return_value = make_response({"approved": True, "recommended_units": 3})
    _, _, _, _, _, preview_order, _ = _import_mcp_server()
    result = preview_order("aapl", "buy", "mkt", 0.025, 0.06)
    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload["symbol"] == "AAPL"
    assert payload["action"] == "BUY"
    assert payload["order_type"] == "MKT"
    assert payload["stop_loss_pct"] == 0.025


@patch("httpx.post")
def test_place_order_sends_correct_payload(mock_post):
    mock_post.return_value = make_response({"status": "placed", "order_id": "123"})
    _, _, _, _, _, _, place_order = _import_mcp_server()
    result = place_order("AAPL", "BUY", "MKT", 0.025, 0.06)
    call_args = mock_post.call_args
    payload = call_args[1]["json"]
    assert payload["symbol"] == "AAPL"
    assert payload["stop_loss_pct"] == 0.025
    assert result["status"] == "placed"


@patch("httpx.post")
def test_place_order_returns_rejection_when_403(mock_post):
    rejection = {"approved": False, "reasons": ["Symbol FAKE is not allowed"]}
    mock_post.return_value = make_response(rejection, status_code=403)
    _, _, _, _, _, _, place_order = _import_mcp_server()
    result = place_order("FAKE", "BUY", "MKT", 0.025, 0.06)
    assert result["approved"] is False


@patch("httpx.get")
def test_get_error_when_server_not_running(mock_get):
    import httpx as httpx_module
    mock_get.side_effect = httpx_module.ConnectError("Connection refused")
    get_price, *_ = _import_mcp_server()
    result = get_price("AAPL")
    assert "error" in result
    assert "not running" in result["error"]
