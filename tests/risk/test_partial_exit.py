# tests/risk/test_partial_exit.py
import pytest
from app.risk.partial_exit import PartialExitManager
from app.db.models import Trade
from datetime import datetime


def _trade(qty=10, remaining=None, partial_done=False):
    return Trade(
        id=1, symbol="AAPL", action="BUY", quantity=qty,
        entry_price=100.0, stop_loss_price=98.0,
        take_profit_price=110.0, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="1",
        trade_status="OPEN", entry_fill_price=100.0,
        partial_exit_done=partial_done,
        remaining_quantity=remaining if remaining is not None else qty,
    )


def test_no_exit_when_not_profitable():
    mgr = PartialExitManager()
    trade = _trade()
    result = mgr.check_exit(trade, 101.0)
    assert not result.should_exit


def test_exit_50pct_at_1_5x_sl():
    mgr = PartialExitManager()
    trade = _trade(qty=10)
    result = mgr.check_exit(trade, 103.0)
    assert result.should_exit
    assert result.exit_reason == "PARTIAL_50PCT"
    assert result.exit_quantity == 5.0
    assert result.remaining_quantity == 5.0
    assert not result.close_all


def test_close_all_when_remaining_too_small():
    mgr = PartialExitManager()
    trade = _trade(qty=1)
    result = mgr.check_exit(trade, 103.0)
    assert result.should_exit
    assert result.close_all


def test_no_second_exit():
    mgr = PartialExitManager()
    trade = _trade(partial_done=True)
    result = mgr.check_exit(trade, 103.0)
    assert not result.should_exit


def test_breakeven_sl_after_partial():
    mgr = PartialExitManager()
    trade = _trade(qty=10, remaining=5, partial_done=True)
    new_sl = mgr.get_breakeven_sl(trade)
    assert new_sl == pytest.approx(100.3, rel=1e-3)


def test_update_trade_after_partial():
    mgr = PartialExitManager()
    trade = _trade(qty=10)
    result = mgr.check_exit(trade, 103.0)
    updated = mgr.update_trade_after_partial(trade, result)
    assert updated.partial_exit_done
    assert updated.remaining_quantity == 5.0
    assert updated.stop_loss_price == pytest.approx(100.3, rel=1e-3)
