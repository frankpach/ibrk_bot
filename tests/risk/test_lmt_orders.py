# tests/risk/test_lmt_orders.py
from app.risk.lmt_orders import calculate_limit_price, is_fill_expected


def test_limit_price_buy():
    price = calculate_limit_price(100.0, "BUY", slippage_buffer_pct=0.005)
    assert price == 100.5


def test_limit_price_sell():
    price = calculate_limit_price(100.0, "SELL", slippage_buffer_pct=0.005)
    assert price == 99.5


def test_fill_expected_buy():
    assert is_fill_expected(100.0, 101.0, "BUY")
    assert not is_fill_expected(102.0, 101.0, "BUY")


def test_fill_expected_sell():
    assert is_fill_expected(102.0, 101.0, "SELL")
    assert not is_fill_expected(100.0, 101.0, "SELL")
