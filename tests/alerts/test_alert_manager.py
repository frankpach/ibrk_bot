# tests/alerts/test_manager.py
from unittest.mock import MagicMock, patch
from app.alerts.manager import (
    parse_alert_command,
    check_alert_triggered,
    check_all_alerts,
    AlertManager,
)
from tests.mocks.mock_broker import MockBrokerAdapter


def test_parse_alert_command_valid():
    result = parse_alert_command("TSLA", "5%")
    assert result is not None
    assert result.symbol == "TSLA"
    assert result.threshold_pct == 0.05


def test_parse_alert_command_invalid():
    assert parse_alert_command("TSLA", "abc") is None
    assert parse_alert_command("TSLA", "-5%") is None
    assert parse_alert_command("TSLA", "150%") is None


def test_check_alert_triggered():
    alert = parse_alert_command("AAPL", "5%")
    triggered, pct = check_alert_triggered(alert, 105.0, 100.0)
    assert triggered is True
    assert pct == 0.05


def test_check_alert_not_triggered():
    alert = parse_alert_command("AAPL", "10%")
    triggered, pct = check_alert_triggered(alert, 105.0, 100.0)
    assert triggered is False


def test_check_alert_zero_prev_close():
    alert = parse_alert_command("AAPL", "5%")
    triggered, pct = check_alert_triggered(alert, 105.0, 0.0)
    assert triggered is False
    assert pct == 0.0


def test_get_price_and_prev_close_success():
    """prev_close must come from broker.get_prev_close, not duplicate of current price."""
    import decimal
    broker = MockBrokerAdapter(
        prices={"AAPL": decimal.Decimal("155.0")},
        prev_closes={"AAPL": decimal.Decimal("150.0")},
    )
    manager = AlertManager(broker=broker)
    current, prev = manager.get_price_and_prev_close("AAPL")
    assert current == 155.0
    assert prev == 150.0
    # Regression guard: prev_close must NOT equal current price when they differ
    assert current != prev


def test_get_price_and_prev_close_uses_real_prev_close():
    """Alert fires only because prev_close differs from current price."""
    import decimal
    from app.alerts.manager import AlertConfig
    broker = MockBrokerAdapter(
        prices={"TSLA": decimal.Decimal("110.0")},
        prev_closes={"TSLA": decimal.Decimal("100.0")},
    )
    manager = AlertManager(broker=broker)
    current, prev = manager.get_price_and_prev_close("TSLA")
    alert = AlertConfig(id=1, symbol="TSLA", threshold_pct=0.05)
    triggered, pct = check_alert_triggered(alert, current, prev)
    assert triggered is True
    assert abs(pct - 0.10) < 1e-6


def test_get_price_and_prev_close_failure():
    broker = MockBrokerAdapter(prices={})  # no price, no prev_close
    manager = AlertManager(broker=broker)
    current, prev = manager.get_price_and_prev_close("AAPL")
    assert current == 0.0
    assert prev == 0.0


@patch("app.alerts.manager.AlertManager.get_price_and_prev_close", return_value=(105.0, 100.0))
@patch("app.alerts.manager.notify")
def test_check_all_alerts_triggered(mock_notify, mock_get_price):
    alert = parse_alert_command("AAPL", "5%")
    db_get = MagicMock(return_value=[alert])
    db_mark = MagicMock()
    check_all_alerts(db_get, db_mark)
    mock_notify.assert_called_once()
    db_mark.assert_called_once()


@patch("app.alerts.manager.AlertManager.get_price_and_prev_close", return_value=(101.0, 100.0))
@patch("app.alerts.manager.notify")
def test_check_all_alerts_not_triggered(mock_notify, mock_get_price):
    alert = parse_alert_command("AAPL", "5%")
    db_get = MagicMock(return_value=[alert])
    db_mark = MagicMock()
    check_all_alerts(db_get, db_mark)
    mock_notify.assert_not_called()
    db_mark.assert_not_called()


@patch("app.alerts.manager.AlertManager.get_price_and_prev_close", return_value=(0.0, 0.0))
@patch("app.alerts.manager.notify")
def test_check_all_alerts_price_fetch_fail(mock_notify, mock_get_price):
    alert = parse_alert_command("AAPL", "5%")
    db_get = MagicMock(return_value=[alert])
    db_mark = MagicMock()
    check_all_alerts(db_get, db_mark)
    mock_notify.assert_not_called()
    db_mark.assert_not_called()


def test_check_all_alerts_empty():
    db_get = MagicMock(return_value=[])
    db_mark = MagicMock()
    check_all_alerts(db_get, db_mark)
    db_get.assert_called_once()
    db_mark.assert_not_called()
