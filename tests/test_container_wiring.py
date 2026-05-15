# tests/test_container_wiring.py
"""Verify the DI Container wires all Sprint 1 components correctly."""
from unittest.mock import MagicMock

from app.container import test_container as make_test_container
from app.alerts.manager import AlertConfig, AlertManager, check_alert_triggered
from app.ibkr.dedup import OrderDeduplicator


def test_container_has_alert_manager():
    c = make_test_container()
    assert isinstance(c.alert_manager, AlertManager)
    assert c.alert_manager._broker is c.broker


def test_container_has_order_deduplicator():
    c = make_test_container()
    assert isinstance(c.order_deduplicator, OrderDeduplicator)


def test_deduplicator_is_same_instance():
    c = make_test_container()
    assert c.order_deduplicator is c.order_deduplicator


def test_alert_manager_with_mock_broker():
    """AlertManager delegates price fetch to injected broker."""
    mock_broker = MagicMock()
    mock_broker.get_price.return_value = 200.0
    mock_broker.get_prev_close.return_value = 195.0
    manager = AlertManager(broker=mock_broker)
    current, _ = manager.get_price_and_prev_close("AAPL")
    assert current == 200.0
    mock_broker.get_price.assert_called_once_with("AAPL")


def test_alert_manager_handles_broker_error_gracefully():
    mock_broker = MagicMock()
    mock_broker.get_price.side_effect = RuntimeError("IB Gateway disconnected")
    manager = AlertManager(broker=mock_broker)
    current, prev = manager.get_price_and_prev_close("AAPL")
    assert current == 0.0
    assert prev == 0.0


def test_check_alert_triggered_above_threshold():
    alert = AlertConfig(id=1, symbol="AAPL", threshold_pct=0.05)
    triggered, pct = check_alert_triggered(alert, current_price=210.0, prev_close=200.0)
    assert triggered is True
    assert abs(pct - 0.05) < 0.001


def test_check_alert_not_triggered_below_threshold():
    alert = AlertConfig(id=2, symbol="TSLA", threshold_pct=0.05)
    triggered, pct = check_alert_triggered(alert, current_price=203.0, prev_close=200.0)
    assert triggered is False


def test_pipeline_accepts_broker_kwarg_without_breaking():
    """Pipeline still works when broker kwarg is omitted (backward compat)."""
    from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
    dl = MagicMock()
    dl.get_ohlcv.return_value = None
    dl.get_historical_volatility.return_value = None
    dl.get_news.return_value = []
    dl.get_earnings_date.return_value = None
    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"))
    result = pipe.run()
    # No broker → portfolio=[] → pipeline completes (with error due to no data)
    assert result.symbol == "AAPL"


def test_pipeline_calls_broker_get_portfolio_when_injected():
    """When broker is provided, portfolio is fetched from broker not httpx."""
    import pandas as pd
    import numpy as np
    from app.analysis.pipeline import AnalysisPipeline, AnalysisContext

    mock_broker = MagicMock()
    mock_broker.get_portfolio.return_value = [{"symbol": "TSLA", "qty": 10}]

    # Build a minimal OHLCV DataFrame with 20 rows so the pipeline passes the
    # data-quality gate (requires >= 15 rows) and reaches the _score() step
    # where get_portfolio is called.
    n = 20
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    df = pd.DataFrame({
        "open":   np.full(n, 150.0),
        "high":   np.full(n, 155.0),
        "low":    np.full(n, 145.0),
        "close":  np.full(n, 152.0),
        "volume": np.full(n, 1_000_000.0),
    }, index=dates)

    dl = MagicMock()
    dl.get_ohlcv.return_value = df
    dl.get_historical_volatility.return_value = None
    dl.get_news.return_value = []
    dl.get_earnings_date.return_value = None

    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"),
                            broker=mock_broker)
    pipe.run()
    mock_broker.get_portfolio.assert_called_once()
