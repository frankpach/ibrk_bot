# tests/db/test_database.py
import pytest
from datetime import datetime
from app.db.database import (
    get_connection, init_db,
    insert_signal, get_pending_signals, mark_signal_processed,
    insert_trade, get_open_trades, close_trade, update_trade_status, get_trades_by_status,
    insert_pattern, get_patterns_for_symbol,
    insert_decision, get_approved_symbols, get_approved_symbols_with_meta,
    save_symbol_proposal, get_pending_proposals, approve_symbol,
    insert_feature_snapshot, get_feature_snapshot_by_id, get_closed_trades_with_snapshots,
)
from app.db.models import Signal, Trade, Pattern, Decision


def test_insert_and_get_signal():
    sig = Signal(
        id=None, symbol="AAPL", strength="STRONG",
        rsi=30.0, macd=-0.1, volume_ratio=1.5,
        extra_indicators="{}", created_at=datetime.utcnow(),
    )
    sid = insert_signal(sig)
    pending = get_pending_signals()
    assert any(s.id == sid for s in pending)


def test_mark_signal_processed():
    sig = Signal(
        id=None, symbol="MSFT", strength="MEDIUM",
        rsi=50.0, macd=0.0, volume_ratio=1.0,
        extra_indicators="{}", created_at=datetime.utcnow(),
    )
    sid = insert_signal(sig)
    mark_signal_processed(sid)
    pending = get_pending_signals()
    assert not any(s.id == sid for s in pending)


def test_insert_and_get_trade():
    trade = Trade(
        id=None, symbol="TSLA", action="BUY", quantity=10,
        entry_price=200.0, stop_loss_price=196.0,
        take_profit_price=212.0, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="1",
    )
    tid = insert_trade(trade)
    open_trades = get_open_trades()
    assert any(t.id == tid for t in open_trades)


def test_close_trade():
    trade = Trade(
        id=None, symbol="NVDA", action="BUY", quantity=5,
        entry_price=100.0, stop_loss_price=98.0,
        take_profit_price=106.0, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="2",
    )
    tid = insert_trade(trade)
    close_trade(tid, 105.0, "TAKE_PROFIT", 25.0, 0.05, exit_fill_price=105.0)
    open_trades = get_open_trades()
    assert not any(t.id == tid for t in open_trades)


def test_update_trade_status():
    trade = Trade(
        id=None, symbol="META", action="BUY", quantity=5,
        entry_price=300.0, stop_loss_price=294.0,
        take_profit_price=318.0, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="3",
    )
    tid = insert_trade(trade)
    update_trade_status(tid, trade_status="FILLED", stop_loss_price=295.0)
    trades = get_trades_by_status("FILLED")
    assert any(t.id == tid for t in trades)


def test_insert_and_get_pattern():
    pat = Pattern(
        id=None, symbol="AAPL", pattern_text="test pattern",
        win_count=5, loss_count=2,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    pid = insert_pattern(pat)
    patterns = get_patterns_for_symbol("AAPL")
    assert any(p.id == pid for p in patterns)


def test_insert_decision():
    dec = Decision(
        id=None, signal_id=1, symbol="AAPL",
        llm_model="gpt-4", prompt_summary="test", response="BUY",
        action="BUY", stop_loss_pct=0.02, take_profit_pct=0.06,
        created_at=datetime.utcnow(),
    )
    did = insert_decision(dec)
    assert did > 0


def test_get_approved_symbols():
    syms = get_approved_symbols()
    assert "AAPL" in syms


def test_get_approved_symbols_with_meta():
    meta = get_approved_symbols_with_meta()
    symbols = [m["symbol"] for m in meta]
    assert "AAPL" in symbols


def test_symbol_proposal_and_approval():
    save_symbol_proposal("NFLX", "streaming growth")
    proposals = get_pending_proposals()
    assert any(p["symbol"] == "NFLX" for p in proposals)
    approve_symbol("NFLX")
    proposals = get_pending_proposals()
    assert not any(p["symbol"] == "NFLX" for p in proposals)
    assert "NFLX" in get_approved_symbols()


# ---------- feature_snapshot_id / new functions ----------

def test_get_feature_snapshot_by_id_not_found():
    """Returns None for a non-existent snapshot id without raising."""
    result = get_feature_snapshot_by_id(999999)
    assert result is None


def test_get_feature_snapshot_by_id_found():
    """Insert a snapshot and retrieve it by id."""
    snap_id = insert_feature_snapshot({
        "symbol": "AAPL",
        "timestamp": datetime.utcnow().isoformat(),
        "context": "test",
        "rsi_14": 42.0,
        "macd_line": 0.5,
        "atr_pct": 1.5,
        "volume_ratio_20d": 1.2,
        "bollinger_position": 0.4,
        "rs_vs_spy_30d": 0.02,
    })
    result = get_feature_snapshot_by_id(snap_id)
    assert result is not None
    assert result["id"] == snap_id
    assert result["symbol"] == "AAPL"
    assert result["rsi_14"] == pytest.approx(42.0)


def test_get_closed_trades_with_snapshots_empty():
    """Returns empty list when no closed trades with snapshots exist."""
    result = get_closed_trades_with_snapshots()
    assert result == []


def test_trades_table_has_feature_snapshot_id_column():
    """Verify the migration added feature_snapshot_id to trades table."""
    conn = get_connection()
    info = conn.execute("PRAGMA table_info(trades)").fetchall()
    conn.close()
    col_names = [row["name"] for row in info]
    assert "feature_snapshot_id" in col_names
