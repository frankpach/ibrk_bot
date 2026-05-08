# tests/test_alerts.py
import pytest
from app.alerts.manager import (
    parse_alert_command,
    check_alert_triggered,
    AlertConfig,
)


def test_parse_alert_command_basic():
    alert = parse_alert_command("TSLA", "5%")
    assert alert is not None
    assert alert.symbol == "TSLA"
    assert alert.threshold_pct == pytest.approx(0.05)


def test_parse_alert_command_decimal():
    alert = parse_alert_command("AAPL", "2.5%")
    assert alert is not None
    assert alert.symbol == "AAPL"
    assert alert.threshold_pct == pytest.approx(0.025)


def test_parse_alert_command_invalid_returns_none():
    alert = parse_alert_command("AAPL", "abc")
    assert alert is None


def test_parse_alert_command_without_percent():
    alert = parse_alert_command("MSFT", "3")
    assert alert is not None
    assert alert.threshold_pct == pytest.approx(0.03)


def test_check_alert_triggered_on_rise():
    alert = AlertConfig(id=1, symbol="TSLA", threshold_pct=0.05)
    triggered, pct = check_alert_triggered(alert, current_price=210.0, prev_close=200.0)
    assert triggered is True
    assert pct == pytest.approx(0.05)


def test_check_alert_triggered_on_drop():
    alert = AlertConfig(id=1, symbol="TSLA", threshold_pct=0.05)
    triggered, pct = check_alert_triggered(alert, current_price=190.0, prev_close=200.0)
    assert triggered is True
    assert pct == pytest.approx(-0.05)


def test_check_alert_not_triggered_small_move():
    alert = AlertConfig(id=1, symbol="TSLA", threshold_pct=0.05)
    triggered, pct = check_alert_triggered(alert, current_price=203.0, prev_close=200.0)
    assert triggered is False


def test_check_alert_zero_prev_close_safe():
    alert = AlertConfig(id=1, symbol="TSLA", threshold_pct=0.05)
    triggered, pct = check_alert_triggered(alert, current_price=100.0, prev_close=0.0)
    assert triggered is False
