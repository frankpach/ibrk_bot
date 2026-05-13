# tests/db/test_database.py
import pytest
from datetime import datetime
from app.db.database import (
    get_connection, init_db,
    insert_signal, get_pending_signals, mark_signal_processed,
    insert_trade, get_open_trades, close_trade, update_trade_status, get_trades_by_status,
    insert_pattern, get_patterns_for_symbol, get_closed_trades_by_symbol,
    insert_decision, get_approved_symbols, get_approved_symbols_with_meta,
    save_symbol_proposal, get_pending_proposals, approve_symbol,
    insert_feature_snapshot, get_feature_snapshot_by_id, get_closed_trades_with_snapshots,
    upsert_position_snapshot, get_position_snapshots,
    upsert_account_snapshot, get_account_history,
    insert_news_cache, get_news_cache,
    upsert_scanner_results, get_scanner_results,
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


def test_get_closed_trades_by_symbol_empty():
    """When no closed trades exist for symbol, returns empty list."""
    result = get_closed_trades_by_symbol("NFLX", limit=10)
    assert result == []


def test_get_closed_trades_by_symbol_returns_trades():
    """Insert a closed trade for a symbol, verify it's returned."""
    # Create and insert a closed trade
    trade = Trade(
        id=None, symbol="GOOG", action="BUY", quantity=5,
        entry_price=150.0, stop_loss_price=147.0,
        take_profit_price=156.0, stop_loss_pct=0.02,
        take_profit_pct=0.04, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="goog1",
    )
    tid = insert_trade(trade)
    close_trade(tid, 155.0, "TAKE_PROFIT", 25.0, 0.033, exit_fill_price=155.0)

    # Query by symbol
    result = get_closed_trades_by_symbol("GOOG", limit=10)
    assert len(result) == 1
    assert result[0].symbol == "GOOG"
    assert result[0].status == "CLOSED"
    assert result[0].exit_price == pytest.approx(155.0)


def test_get_closed_trades_by_symbol_respects_limit():
    """Insert multiple closed trades, verify limit is respected."""
    # Insert 5 closed trades for the same symbol
    for i in range(5):
        trade = Trade(
            id=None, symbol="AMZN", action="BUY", quantity=2,
            entry_price=200.0 + i, stop_loss_price=198.0 + i,
            take_profit_price=208.0 + i, stop_loss_pct=0.01,
            take_profit_pct=0.04, signal_strength="MEDIUM",
            llm_justification="test", status="OPEN",
            exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
            opened_at=datetime.utcnow(), closed_at=None, order_id=f"amzn{i}",
        )
        tid = insert_trade(trade)
        close_trade(tid, 206.0 + i, "TAKE_PROFIT", 12.0, 0.03, exit_fill_price=206.0 + i)

    # Get with limit=3
    result = get_closed_trades_by_symbol("AMZN", limit=3)
    assert len(result) == 3
    assert all(t.symbol == "AMZN" for t in result)


def test_get_closed_trades_by_symbol_case_insensitive():
    """Symbol lookup should be case-insensitive."""
    trade = Trade(
        id=None, symbol="JPM", action="SELL", quantity=10,
        entry_price=180.0, stop_loss_price=182.0,
        take_profit_price=174.0, stop_loss_pct=0.01,
        take_profit_pct=0.03, signal_strength="WEAK",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="jpm1",
    )
    tid = insert_trade(trade)
    close_trade(tid, 175.0, "TAKE_PROFIT", 50.0, 0.028, exit_fill_price=175.0)

    # Query with lowercase
    result = get_closed_trades_by_symbol("jpm", limit=10)
    assert len(result) == 1
    assert result[0].symbol == "JPM"


def test_get_patterns_for_symbol_empty():
    """When no patterns exist for symbol, returns empty list."""
    result = get_patterns_for_symbol("UNKNOWN_SYM", limit=3)
    assert result == []


def test_get_patterns_for_symbol_returns_patterns():
    """Insert a pattern for a symbol, verify it's returned."""
    pat = Pattern(
        id=None, symbol="TSLA", pattern_text="bullish divergence",
        win_count=3, loss_count=1,
        created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    pid = insert_pattern(pat)

    # Query by symbol with limit
    result = get_patterns_for_symbol("TSLA", limit=3)
    assert len(result) == 1
    assert result[0].symbol == "TSLA"
    assert result[0].pattern_text == "bullish divergence"


def test_get_patterns_for_symbol_respects_limit():
    """Insert multiple patterns, verify limit is respected."""
    # Insert 5 patterns for the same symbol
    for i in range(5):
        pat = Pattern(
            id=None, symbol="SPY", pattern_text=f"pattern_{i}",
            win_count=i, loss_count=i // 2,
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        insert_pattern(pat)

    # Get with limit=2
    result = get_patterns_for_symbol("SPY", limit=2)
    assert len(result) == 2
    assert all(p.symbol == "SPY" for p in result)


def test_get_patterns_for_symbol_no_limit():
    """When no limit is specified, returns all patterns."""
    # Insert 3 patterns for a fresh symbol
    for i in range(3):
        pat = Pattern(
            id=None, symbol="QQQ", pattern_text=f"pattern_{i}",
            win_count=i, loss_count=0,
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        insert_pattern(pat)

    # Get without limit
    result = get_patterns_for_symbol("QQQ")
    assert len(result) == 3
    assert all(p.symbol == "QQQ" for p in result)


# --- LD-001: Live Dashboard table tests ---

def test_upsert_and_get_position_snapshot():
    """Test insert and update (upsert) of position_snapshots."""
    upsert_position_snapshot(9001, "AAPL", 175.0, 50.0, 0.025)
    snapshots = get_position_snapshots()
    assert 9001 in snapshots
    assert snapshots[9001]["symbol"] == "AAPL"
    assert snapshots[9001]["current_price"] == pytest.approx(175.0)

    # Update — same trade_id should replace, not duplicate
    upsert_position_snapshot(9001, "AAPL", 180.0, 100.0, 0.05)
    snapshots = get_position_snapshots()
    # Still only one entry for trade_id 9001
    assert snapshots[9001]["current_price"] == pytest.approx(180.0)
    assert snapshots[9001]["pnl_usd"] == pytest.approx(100.0)


def test_upsert_account_snapshot_unique_date():
    """Test that same date updates, not inserts twice."""
    upsert_account_snapshot("2026-05-10", 100000.0, 50000.0, 500.0, 0.005)
    upsert_account_snapshot("2026-05-10", 101000.0, 51000.0, 600.0, 0.006)

    history = get_account_history(days=30)
    dates = [r["date"] for r in history]
    # date must appear exactly once (UNIQUE constraint + INSERT OR REPLACE)
    assert dates.count("2026-05-10") == 1
    # The second upsert should have won
    entry = next(r for r in history if r["date"] == "2026-05-10")
    assert entry["net_liquidation"] == pytest.approx(101000.0)


def test_get_account_history_oldest_first():
    """Insert 3 distinct dates, verify oldest comes first."""
    upsert_account_snapshot("2026-05-01", 90000.0, 40000.0, 100.0, 0.001)
    upsert_account_snapshot("2026-05-02", 91000.0, 41000.0, 200.0, 0.002)
    upsert_account_snapshot("2026-05-03", 92000.0, 42000.0, 300.0, 0.003)

    history = get_account_history(days=30)
    # Filter to just our 3 test dates
    test_dates = [r["date"] for r in history if r["date"] in ("2026-05-01", "2026-05-02", "2026-05-03")]
    assert test_dates == ["2026-05-01", "2026-05-02", "2026-05-03"]


def test_news_cache_insert_and_filter():
    """Insert news for AAPL and NVDA, filter by AAPL only."""
    insert_news_cache("AAPL", "Apple beats earnings", "Reuters", "positive",
                      "art_aapl_001", "2026-05-13T10:00:00")
    insert_news_cache("NVDA", "Nvidia launches new GPU", "Bloomberg", "positive",
                      "art_nvda_001", "2026-05-13T10:05:00")

    aapl_news = get_news_cache(symbols=["AAPL"], limit=10)
    assert len(aapl_news) >= 1
    assert all(n["symbol"] == "AAPL" for n in aapl_news)

    all_news = get_news_cache(limit=50)
    symbols_in_result = {n["symbol"] for n in all_news}
    assert "AAPL" in symbols_in_result
    assert "NVDA" in symbols_in_result


def test_scanner_results_upsert_replaces():
    """Insert gainers, re-insert gainers, verify old data is gone."""
    first_batch = [
        {"symbol": "AAA", "name": "Alpha Corp", "change_pct": 5.0, "volume_ratio": 2.0},
        {"symbol": "BBB", "name": "Beta Inc",   "change_pct": 4.5, "volume_ratio": 1.8},
    ]
    upsert_scanner_results("gainers", first_batch)

    # Re-insert with different data
    second_batch = [
        {"symbol": "CCC", "name": "Gamma Ltd", "change_pct": 6.0, "volume_ratio": 3.0},
    ]
    upsert_scanner_results("gainers", second_batch)

    results = get_scanner_results("gainers")
    symbols = [r["symbol"] for r in results]
    # Old symbols must be gone
    assert "AAA" not in symbols
    assert "BBB" not in symbols
    # New symbol must be present
    assert "CCC" in symbols
    assert len(results) == 1


def test_symbol_parameter_has_new_fields():
    """SymbolParameter dataclass has the 3 new backtest fields with correct defaults."""
    from app.db.models import SymbolParameter
    sp = SymbolParameter(symbol="AAPL", updated_at="2026-01-01")
    assert sp.backtest_calibrated == 0
    assert sp.backtest_calibrated_at is None
    assert sp.backtest_profit_factor is None
