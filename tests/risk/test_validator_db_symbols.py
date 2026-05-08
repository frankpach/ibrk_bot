from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from app.risk import validator

MARKET_TZ = ZoneInfo("America/New_York")
# A fixed Tuesday at 10:00 ET — always within market hours
MARKET_NOW = datetime(2025, 6, 3, 10, 0, 0, tzinfo=MARKET_TZ)


def _make_order_kwargs(symbol="AAPL"):
    return dict(
        symbol=symbol,
        action="BUY",
        quantity=1,
        order_type="MKT",
        stop_loss_pct=0.02,
        capital=10000.0,
        active_positions=0,
        price=150.0,
        now=MARKET_NOW,
    )


def test_validator_accepts_symbol_present_in_db():
    with patch.object(validator, "get_approved_symbols",
                      return_value=["AAPL", "BTC", "EURUSD"]):
        result = validator.validate_order(**_make_order_kwargs("BTC"))
    assert result.approved is True


def test_validator_rejects_symbol_not_in_db():
    with patch.object(validator, "get_approved_symbols",
                      return_value=["AAPL"]):
        result = validator.validate_order(**_make_order_kwargs("ZZZZ"))
    reasons = result.reasons if hasattr(result, "reasons") else []
    assert any("not allowed" in r.lower() or "unknown" in r.lower()
               for r in reasons)


def test_validator_does_not_use_hardcoded_settings_list():
    with patch.object(validator, "get_approved_symbols", return_value=[]):
        result = validator.validate_order(**_make_order_kwargs("AAPL"))
    reasons = result.reasons if hasattr(result, "reasons") else []
    assert any("not allowed" in r.lower() or "unknown" in r.lower()
               for r in reasons)
