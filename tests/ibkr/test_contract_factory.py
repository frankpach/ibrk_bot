import pytest
from ib_insync import Stock, Future, Forex, Contract

from app.ibkr.contract_factory import (
    build_contract,
    get_what_to_show,
    get_use_rth,
    parse_forex_pair,
    UnsupportedSecTypeError,
    InvalidForexPairError,
)


# ---- build_contract ---------------------------------------------------------

def test_build_stk_returns_stock():
    c = build_contract("AAPL", "STK", "SMART", "USD")
    assert isinstance(c, Stock)
    assert c.symbol == "AAPL"
    assert c.exchange == "SMART"
    assert c.currency == "USD"


def test_build_stk_uppercases_symbol():
    c = build_contract("aapl", "STK", "SMART", "USD")
    assert c.symbol == "AAPL"


def test_build_fut_returns_future_without_expiry():
    c = build_contract("ES", "FUT", "CME", "USD")
    assert isinstance(c, Future)
    assert c.symbol == "ES"
    assert c.exchange == "CME"
    assert c.currency == "USD"
    # Front-month is resolved later via reqContractDetails
    assert c.lastTradeDateOrContractMonth in ("", None)


def test_build_cash_returns_forex_with_pair():
    c = build_contract("EURUSD", "CASH", "IDEALPRO", "USD")
    assert isinstance(c, Forex)
    assert c.symbol == "EUR"      # base
    assert c.currency == "USD"    # quote
    assert c.exchange == "IDEALPRO"


def test_build_cash_jpy_quote():
    c = build_contract("USDJPY", "CASH", "IDEALPRO", "JPY")
    assert c.symbol == "USD"
    assert c.currency == "JPY"


def test_build_crypto_returns_generic_contract():
    c = build_contract("BTC", "CRYPTO", "PAXOS", "USD")
    assert isinstance(c, Contract)
    assert c.secType == "CRYPTO"
    assert c.symbol == "BTC"
    assert c.exchange == "PAXOS"
    assert c.currency == "USD"


def test_build_unsupported_sec_type_raises():
    with pytest.raises(UnsupportedSecTypeError):
        build_contract("XYZ", "BOND", "SMART", "USD")


# ---- parse_forex_pair -------------------------------------------------------

@pytest.mark.parametrize("pair,base,quote", [
    ("EURUSD", "EUR", "USD"),
    ("usdjpy", "USD", "JPY"),
    ("GBPJPY", "GBP", "JPY"),
])
def test_parse_forex_pair_ok(pair, base, quote):
    assert parse_forex_pair(pair) == (base, quote)


@pytest.mark.parametrize("bad", ["EUR", "EURUSDX", "", "12USD"])
def test_parse_forex_pair_invalid(bad):
    with pytest.raises(InvalidForexPairError):
        parse_forex_pair(bad)


# ---- get_what_to_show -------------------------------------------------------

@pytest.mark.parametrize("sec_type,expected", [
    ("STK", "TRADES"),
    ("FUT", "TRADES"),
    ("CRYPTO", "TRADES"),
    ("CASH", "MIDPOINT"),
    ("OPT", "TRADES"),
])
def test_what_to_show(sec_type, expected):
    assert get_what_to_show(sec_type) == expected


# ---- get_use_rth ------------------------------------------------------------

@pytest.mark.parametrize("sec_type,expected", [
    ("STK", True),
    ("OPT", True),
    ("FUT", False),
    ("CASH", False),
    ("CRYPTO", False),
])
def test_use_rth(sec_type, expected):
    assert get_use_rth(sec_type) is expected
