# tests/test_ibkr_client.py
import pytest
from app.ibkr.client import IBKRClient


@pytest.fixture(scope="module")
def client():
    c = IBKRClient(client_id=11)
    yield c
    c.disconnect()


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
    if portfolio:
        item = portfolio[0]
        assert "symbol" in item
        assert "quantity" in item
        assert "avg_cost" in item
        assert "market_value" in item
        assert "unrealized_pnl" in item
