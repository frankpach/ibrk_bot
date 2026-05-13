# tests/test_ibkr_client.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture
def client():
    """Return a mocked IBKRClient that never touches the network."""
    from app.ibkr.client import IBKRClient
    with patch("app.ibkr.client.IB") as MockIB:
        mock_ib = MagicMock()
        mock_ib.isConnected.return_value = True
        mock_ib.accountSummaryAsync = AsyncMock(return_value=[
            MagicMock(tag="NetLiquidation", value="100000.00", currency="USD"),
            MagicMock(tag="BuyingPower", value="200000.00", currency="USD"),
            MagicMock(tag="CashBalance", value="50000.00", currency="USD"),
        ])
        mock_ib.portfolio.return_value = [
            MagicMock(contract=MagicMock(symbol="AAPL"), position=10.0, averageCost=150.0, marketValue=1600.0, unrealizedPNL=100.0),
        ]
        MockIB.return_value = mock_ib
        c = IBKRClient(client_id=11)
        c.ib = mock_ib
        yield c


def test_get_account_returns_expected_keys(client):
    account = client.get_account()
    assert "net_liquidation" in account
    assert "buying_power" in account
    assert "cash_balance" in account
    assert "currency" in account


def test_get_account_values_are_numeric(client):
    account = client.get_account()
    assert isinstance(account["net_liquidation"], float)
    assert account["net_liquidation"] > 0


def test_get_portfolio_returns_list(client):
    portfolio = client.get_portfolio()
    assert isinstance(portfolio, list)


def test_get_portfolio_item_keys(client):
    portfolio = client.get_portfolio()
    assert len(portfolio) > 0
    item = portfolio[0]
    assert "symbol" in item
    assert "quantity" in item
    assert "avg_cost" in item
    assert "market_value" in item
    assert "unrealized_pnl" in item
