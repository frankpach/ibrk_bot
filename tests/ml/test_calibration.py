"""Tests for app/ml/calibration.py"""
import pytest
from unittest.mock import MagicMock, patch
import threading

_DB = "app.infrastructure.db.compat"


def test_on_symbol_approved_launches_thread():
    from app.ml.calibration import on_symbol_approved
    with patch("app.ml.calibration._run_calibration_safe") as mock_run:
        on_symbol_approved("AAPL", MagicMock())
        import time; time.sleep(0.1)
        mock_run.assert_called_once_with("AAPL", mock_run.call_args[0][1])


def test_on_symbol_approved_returns_immediately():
    """on_symbol_approved is non-blocking."""
    import time
    from app.ml.calibration import on_symbol_approved

    slow_client = MagicMock()
    start = time.time()
    with patch("app.ml.calibration._run_calibration_safe"):
        on_symbol_approved("AAPL", slow_client)
    elapsed = time.time() - start
    assert elapsed < 0.5


def test_calibration_selects_best_profit_factor():
    """_run_calibration_safe picks the SL/TP with highest profit_factor."""
    from app.ml.calibration import _run_calibration_safe

    call_count = 0
    def fake_backtest(symbol, ib_client, period_days, stop_loss_pct, take_profit_pct, capital):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.total_trades = 10
        if stop_loss_pct == 0.025 and take_profit_pct == 0.060:
            result.profit_factor = 2.5
        else:
            result.profit_factor = 1.0
        return result

    with patch("app.backtest.engine.run_backtest", side_effect=fake_backtest), \
         patch(f"{_DB}.update_symbol_parameters") as mock_update, \
         patch("app.notifications.telegram.notify"), \
         patch("time.sleep"):
        _run_calibration_safe("AAPL", MagicMock())

    assert call_count == 20
    mock_update.assert_called_once()
    call_kwargs = mock_update.call_args
    assert call_kwargs[1]["stop_loss_pct"] == 0.025
    assert call_kwargs[1]["take_profit_pct"] == 0.060
    assert call_kwargs[1]["backtest_calibrated"] == 1


def test_calibration_uses_defaults_when_no_valid_results():
    """Uses defaults when all backtest results have < MIN_TRADES trades."""
    from app.ml.calibration import _run_calibration_safe

    def fake_backtest(**kwargs):
        result = MagicMock()
        result.total_trades = 0
        result.profit_factor = 0.0
        return result

    with patch("app.backtest.engine.run_backtest", side_effect=lambda **kw: fake_backtest(**kw)), \
         patch(f"{_DB}.update_symbol_parameters") as mock_update, \
         patch("app.notifications.telegram.notify"), \
         patch("time.sleep"):
        _run_calibration_safe("AAPL", MagicMock())

    mock_update.assert_called_once()
    args = mock_update.call_args
    assert args[1]["stop_loss_pct"] == 0.025
    assert args[1]["take_profit_pct"] == 0.060
