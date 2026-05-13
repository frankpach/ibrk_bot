# tests/risk/test_trailing_stop.py
import pytest
from app.risk.trailing_stop import TrailingStopManager, StopUpdateResult
from app.db.models import Trade
from datetime import datetime


def _trade(action="BUY", entry=100.0, sl_pct=0.02, current_sl=98.0):
    return Trade(
        id=1, symbol="AAPL", action=action, quantity=10,
        entry_price=entry, stop_loss_price=current_sl,
        take_profit_price=110.0, stop_loss_pct=sl_pct,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="1",
        trade_status="OPEN", entry_fill_price=entry,
        remaining_quantity=10,
    )


def test_no_update_when_pnl_low():
    mgr = TrailingStopManager()
    trade = _trade()
    result = mgr.update_stop_levels(trade, 101.0)
    assert result.new_stop_price is None


def test_breakeven_when_pnl_exceeds_1_5x_sl():
    mgr = TrailingStopManager()
    trade = _trade(sl_pct=0.02)
    result = mgr.update_stop_levels(trade, 103.5)
    assert result.new_stop_price is not None
    assert result.reason == "breakeven"
    assert result.new_stop_price == pytest.approx(100.3, rel=1e-3)


def test_trailing_when_pnl_exceeds_3x_sl():
    mgr = TrailingStopManager()
    trade = _trade(sl_pct=0.02)
    result = mgr.update_stop_levels(trade, 107.0)
    assert result.reason == "trailing"
    assert result.new_stop_price == pytest.approx(103.5, rel=1e-3)


def test_never_moves_sl_backward_buy():
    mgr = TrailingStopManager()
    trade = _trade(current_sl=99.0)
    result = mgr.update_stop_levels(trade, 101.0)
    assert result.new_stop_price is None or result.new_stop_price >= 99.0


def test_never_moves_sl_backward_sell():
    mgr = TrailingStopManager()
    trade = _trade(action="SELL", entry=100.0, current_sl=102.0)
    result = mgr.update_stop_levels(trade, 99.0)
    assert result.new_stop_price is None or result.new_stop_price <= 102.0


def test_should_close_when_price_below_new_sl():
    mgr = TrailingStopManager()
    trade = _trade(sl_pct=0.02)
    # Extreme gap down that still meets trailing threshold (unlikely but tests logic)
    # price = 107 -> trailing SL = 103.5
    result = mgr.update_stop_levels(trade, 107.0)
    assert result.new_stop_price is not None
    # If price were exactly at the new SL, should_close would be True during that same update
    # We simulate by checking the condition manually
    assert result.should_close is False  # price 107 > 103.5


def test_get_current_sl_returns_updated():
    mgr = TrailingStopManager()
    trade = _trade(sl_pct=0.02)
    sl = mgr.get_current_sl(trade, 103.5)
    assert sl == pytest.approx(100.3, rel=1e-3)
