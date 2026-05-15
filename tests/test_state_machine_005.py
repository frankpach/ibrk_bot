import pytest
from datetime import datetime, timezone
from app.infrastructure.db.compat import init_db, get_connection, insert_trade, get_open_trades, get_trades_by_status, update_trade_status, update_trade_close_fill, close_trade
from app.db.models import Trade


@pytest.fixture
def fresh_db(tmp_path):
    import app.infrastructure.db.compat as db_mod
    orig_path = db_mod.DB_PATH
    db_mod.DB_PATH = str(tmp_path / "test_state_machine.db")
    init_db()
    yield
    db_mod.DB_PATH = orig_path


class TestTradeStateMachine:
    def test_insert_trade_with_default_status(self, fresh_db):
        trade = Trade(
            id=None, symbol="AAPL", action="BUY", quantity=1.0,
            entry_price=100.0, stop_loss_price=97.5, take_profit_price=106.0,
            stop_loss_pct=0.025, take_profit_pct=0.06,
            signal_strength="STRONG", llm_justification="test",
            status="OPEN", exit_price=None, exit_reason=None,
            pnl_usd=None, pnl_pct=None,
            opened_at=datetime.now(timezone.utc), closed_at=None, order_id="123",
        )
        tid = insert_trade(trade)
        assert tid > 0
        
        open_trades = get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0].trade_status == "PENDING"
        assert open_trades[0].entry_fill_price is None

    def test_update_trade_status(self, fresh_db):
        trade = Trade(
            id=None, symbol="NVDA", action="BUY", quantity=0.5,
            entry_price=200.0, stop_loss_price=195.0, take_profit_price=212.0,
            stop_loss_pct=0.025, take_profit_pct=0.06,
            signal_strength="MEDIUM", llm_justification="test2",
            status="OPEN", exit_price=None, exit_reason=None,
            pnl_usd=None, pnl_pct=None,
            opened_at=datetime.now(timezone.utc), closed_at=None, order_id="456",
        )
        tid = insert_trade(trade)
        
        update_trade_status(tid, "SUBMITTED")
        trades = get_trades_by_status("SUBMITTED")
        assert len(trades) == 1
        assert trades[0].id == tid
        
        update_trade_status(tid, "FILLED", fill_price=200.05)
        filled = get_trades_by_status("FILLED")
        assert len(filled) == 1
        assert filled[0].entry_fill_price == 200.05

    def test_close_trade_updates_status(self, fresh_db):
        trade = Trade(
            id=None, symbol="TSLA", action="SELL", quantity=1.0,
            entry_price=250.0, stop_loss_price=256.25, take_profit_price=235.0,
            stop_loss_pct=0.025, take_profit_pct=0.06,
            signal_strength="STRONG", llm_justification="test3",
            status="OPEN", exit_price=None, exit_reason=None,
            pnl_usd=None, pnl_pct=None,
            opened_at=datetime.now(timezone.utc), closed_at=None, order_id="789",
        )
        tid = insert_trade(trade)
        update_trade_status(tid, "OPEN")
        
        update_trade_close_fill(tid, "close-123", 248.0)
        close_trade(tid, 248.0, "TAKE_PROFIT", 2.0, 0.008, exit_fill_price=247.95)
        
        closed = get_trades_by_status("CLOSED")
        assert len(closed) == 1
        assert closed[0].exit_fill_price == 247.95
        assert closed[0].close_order_id == "close-123"
        assert closed[0].status == "CLOSED"

    def test_open_trades_excludes_closed(self, fresh_db):
        t1 = Trade(id=None, symbol="A", action="BUY", quantity=1.0,
                   entry_price=100.0, stop_loss_price=97.5, take_profit_price=106.0,
                   stop_loss_pct=0.025, take_profit_pct=0.06,
                   signal_strength="S", llm_justification="x", status="OPEN",
                   exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
                   opened_at=datetime.now(timezone.utc), closed_at=None, order_id="1")
        t2 = Trade(id=None, symbol="B", action="BUY", quantity=1.0,
                   entry_price=100.0, stop_loss_price=97.5, take_profit_price=106.0,
                   stop_loss_pct=0.025, take_profit_pct=0.06,
                   signal_strength="S", llm_justification="x", status="OPEN",
                   exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
                   opened_at=datetime.now(timezone.utc), closed_at=None, order_id="2")
        tid1 = insert_trade(t1)
        tid2 = insert_trade(t2)
        update_trade_status(tid1, "OPEN")
        update_trade_status(tid2, "OPEN")
        
        close_trade(tid1, 100.0, "MANUAL", 0.0, 0.0)
        
        open_trades = get_open_trades()
        assert len(open_trades) == 1
        assert open_trades[0].symbol == "B"
