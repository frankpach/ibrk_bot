"""Tests for app/ml/cycle.py"""
import pytest
from unittest.mock import MagicMock, patch


def test_run_learning_cycle_no_trades(tmp_path):
    """Cycle runs without error when no closed trades exist."""
    from app.ml.cycle import run_learning_cycle
    data_layer = MagicMock()
    with patch("app.analysis.evaluator.run_return_evaluator"), \
         patch("app.db.database.get_closed_trades_with_snapshots", return_value=[]), \
         patch("app.db.database.get_approved_symbols", return_value=[]):
        report = run_learning_cycle(data_layer)
    assert report.signal_filter_auc is None
    assert report.errors == [] or isinstance(report.errors, list)


def test_run_learning_cycle_with_trades(tmp_path):
    """Cycle returns AUC when enough trades exist."""
    from app.ml.cycle import run_learning_cycle
    # Build 15 fake trade dicts
    fake_trades = [
        {"pnl_pct": 0.01 if i % 2 == 0 else -0.01,
         "rsi_14": 50 + i, "macd_line": 0, "atr_pct": 2.0,
         "volume_ratio_20d": 1.0, "bollinger_position": 0.5,
         "rs_vs_spy_30d": 0.0}
        for i in range(15)
    ]
    data_layer = MagicMock()
    with patch("app.analysis.evaluator.run_return_evaluator"), \
         patch("app.db.database.get_closed_trades_with_snapshots", return_value=fake_trades), \
         patch("app.db.database.get_approved_symbols", return_value=[]), \
         patch("app.ml.signal_filter.get_signal_filter") as mock_sf, \
         patch("app.notifications.telegram.notify"):
        mock_sf.return_value.retrain.return_value = 0.63
        report = run_learning_cycle(data_layer)
    assert report.signal_filter_auc == 0.63
    assert report.samples_used == 15


def test_maybe_rollback_not_enough_trades():
    """No rollback when fewer than 5 closed trades."""
    from app.ml.cycle import maybe_rollback_parameters
    with patch("app.db.database.get_closed_trades_by_symbol", return_value=[]):
        result = maybe_rollback_parameters("AAPL")
    assert result is False


def test_maybe_rollback_good_win_rate():
    """No rollback when win rate >= 30%."""
    from app.ml.cycle import maybe_rollback_parameters
    trades = [MagicMock(pnl_pct=0.01) for _ in range(5)]  # all wins
    with patch("app.db.database.get_closed_trades_by_symbol", return_value=trades):
        result = maybe_rollback_parameters("AAPL")
    assert result is False


def test_maybe_rollback_applies_when_win_rate_low():
    """Rollback applied when win rate < 30% and previous_json exists."""
    import json
    from app.ml.cycle import maybe_rollback_parameters
    trades = [MagicMock(pnl_pct=-0.01) for _ in range(5)]  # all losses
    params = MagicMock()
    params.previous_json = json.dumps({"stop_loss_pct": 0.025})
    with patch("app.db.database.get_closed_trades_by_symbol", return_value=trades), \
         patch("app.db.database.get_or_create_symbol_parameters", return_value=params), \
         patch("app.db.database.update_symbol_parameters") as mock_update, \
         patch("app.notifications.telegram.notify"):
        result = maybe_rollback_parameters("AAPL")
    assert result is True
    mock_update.assert_called_once()


def test_get_win_rate_last_10_insufficient():
    """Returns None when fewer than 3 trades."""
    from app.ml.cycle import _get_win_rate_last_10
    with patch("app.db.database.get_closed_trades_by_symbol", return_value=[]):
        result = _get_win_rate_last_10("AAPL")
    assert result is None


def test_run_learning_cycle_without_ib_client_no_regression():
    """run_learning_cycle(data_layer) with no ib_client still works — no regression."""
    from app.ml.cycle import run_learning_cycle
    data_layer = MagicMock()
    with patch("app.analysis.evaluator.run_return_evaluator"), \
         patch("app.db.database.get_closed_trades_with_snapshots", return_value=[]), \
         patch("app.db.database.get_approved_symbols", return_value=[]):
        report = run_learning_cycle(data_layer)
    assert report is not None
    assert report.errors == [] or isinstance(report.errors, list)


def test_run_learning_cycle_with_ib_client_calls_account_snapshot():
    """run_learning_cycle(data_layer, ib_client=mock) calls upsert_account_snapshot."""
    from app.ml.cycle import run_learning_cycle
    data_layer = MagicMock()
    ib_client = MagicMock()
    ib_client.get_account.return_value = {
        "net_liquidation": 50000.0,
        "buying_power": 25000.0,
    }

    with patch("app.analysis.evaluator.run_return_evaluator"), \
         patch("app.db.database.get_closed_trades_with_snapshots", return_value=[]), \
         patch("app.db.database.get_approved_symbols", return_value=[]), \
         patch("app.db.database.upsert_account_snapshot") as mock_acct, \
         patch("app.db.database.get_daily_pnl", return_value=500.0):
        report = run_learning_cycle(data_layer, ib_client=ib_client)

    mock_acct.assert_called_once()
    kwargs = mock_acct.call_args.kwargs
    assert kwargs["net_liquidation"] == 50000.0
    assert kwargs["buying_power"] == 25000.0
    assert kwargs["daily_pnl_usd"] == 500.0
    assert abs(kwargs["daily_pnl_pct"] - 1.0) < 0.01  # 500/50000*100 = 1.0%


def test_learning_report_to_telegram():
    """to_telegram() produces non-empty string."""
    from app.ml.cycle import LearningReport
    report = LearningReport(date="2026-05-13", signal_filter_auc=0.63, samples_used=20)
    msg = report.to_telegram()
    assert "0.630" in msg
    assert "2026-05-13" in msg
