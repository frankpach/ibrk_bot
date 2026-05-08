# tests/test_backtest_engine.py
import pandas as pd
import pytest
from app.backtest.engine import (
    BacktestResult,
    apply_signals_to_df,
    simulate_trades,
    calculate_metrics,
)


def make_df(closes: list, volumes: list = None) -> pd.DataFrame:
    if volumes is None:
        volumes = [1_000_000.0] * len(closes)
    return pd.DataFrame({"close": closes, "volume": volumes})


def test_apply_signals_returns_signal_column():
    df = make_df([100.0] * 30)
    result = apply_signals_to_df(df)
    assert "signal" in result.columns
    assert len(result) == 30


def test_apply_signals_weak_for_first_14():
    df = make_df([100.0] * 30)
    result = apply_signals_to_df(df)
    for i in range(14):
        assert result.iloc[i]["signal"] == "WEAK"


def test_simulate_trades_returns_list():
    df = make_df([100.0] * 30)
    df = apply_signals_to_df(df)
    trades = simulate_trades(df, stop_loss_pct=0.025, take_profit_pct=0.06, capital=500.0)
    assert isinstance(trades, list)


def test_simulate_trade_structure():
    closes = [100.0] * 15 + [90.0] * 5 + [85.0] * 5 + [88.0] * 5
    df = make_df(closes, volumes=[2_000_000.0] * 30)
    df = apply_signals_to_df(df)
    df.loc[df.index[20], "signal"] = "STRONG"
    trades = simulate_trades(df, stop_loss_pct=0.025, take_profit_pct=0.06, capital=500.0)
    if trades:
        t = trades[0]
        assert "entry_price" in t
        assert "exit_price" in t
        assert "pnl_pct" in t
        assert "exit_reason" in t
        assert "units" in t


def test_calculate_metrics_empty():
    result = calculate_metrics([], capital=500.0)
    assert result.total_trades == 0
    assert result.win_rate == 0.0
    assert result.total_pnl_usd == 0.0
    assert result.profit_factor == 0.0


def test_calculate_metrics_with_trades():
    trades = [
        {"pnl_usd": 10.0, "pnl_pct": 0.04, "exit_reason": "TAKE_PROFIT"},
        {"pnl_usd": -5.0, "pnl_pct": -0.025, "exit_reason": "STOP_LOSS"},
        {"pnl_usd": 8.0, "pnl_pct": 0.03, "exit_reason": "TAKE_PROFIT"},
    ]
    result = calculate_metrics(trades, capital=500.0)
    assert result.total_trades == 3
    assert result.wins == 2
    assert result.losses == 1
    assert result.win_rate == pytest.approx(66.67, abs=0.1)
    assert result.total_pnl_usd == pytest.approx(13.0)
    assert result.max_drawdown_pct >= 0


def test_calculate_metrics_profit_factor():
    trades = [
        {"pnl_usd": 20.0, "pnl_pct": 0.06, "exit_reason": "TAKE_PROFIT"},
        {"pnl_usd": -5.0, "pnl_pct": -0.025, "exit_reason": "STOP_LOSS"},
    ]
    result = calculate_metrics(trades, capital=500.0)
    assert result.profit_factor == pytest.approx(4.0)


def test_calculate_metrics_pnl_pct_of_capital():
    trades = [{"pnl_usd": 25.0, "pnl_pct": 0.05, "exit_reason": "TAKE_PROFIT"}]
    result = calculate_metrics(trades, capital=500.0)
    assert result.total_pnl_pct == pytest.approx(5.0)
