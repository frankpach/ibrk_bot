# tests/alerts/test_manager.py
from unittest.mock import MagicMock, patch
from app.alerts.manager import (
    parse_alert_command,
    check_alert_triggered,
    _get_price_and_prev_close,
    check_all_alerts,
)


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


@patch("app.alerts.manager.httpx.get")
def test_get_price_and_prev_close_success(mock_get):
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 150.0, "close": 145.0})
    current, prev = _get_price_and_prev_close("AAPL")
    assert current == 150.0
    assert prev == 145.0


@patch("app.alerts.manager.httpx.get")
def test_get_price_and_prev_close_failure(mock_get):
    mock_get.side_effect = Exception("network")
    current, prev = _get_price_and_prev_close("AAPL")
    assert current == 0.0
    assert prev == 0.0


@patch("app.alerts.manager._get_price_and_prev_close", return_value=(105.0, 100.0))
@patch("app.alerts.manager.notify")
def test_check_all_alerts_triggered(mock_notify, mock_get_price):
    alert = parse_alert_command("AAPL", "5%")
    db_get = MagicMock(return_value=[alert])
    db_mark = MagicMock()
    check_all_alerts(db_get, db_mark)
    mock_notify.assert_called_once()
    db_mark.assert_called_once()


@patch("app.alerts.manager._get_price_and_prev_close", return_value=(101.0, 100.0))
@patch("app.alerts.manager.notify")
def test_check_all_alerts_not_triggered(mock_notify, mock_get_price):
    alert = parse_alert_command("AAPL", "5%")
    db_get = MagicMock(return_value=[alert])
    db_mark = MagicMock()
    check_all_alerts(db_get, db_mark)
    mock_notify.assert_not_called()
    db_mark.assert_not_called()


@patch("app.alerts.manager._get_price_and_prev_close", return_value=(0.0, 0.0))
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
