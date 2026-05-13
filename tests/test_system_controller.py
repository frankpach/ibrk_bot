# tests/test_system_controller.py
from unittest.mock import MagicMock
from app.system.controller import SystemController


def test_pause_stops_scanner():
    mock_scheduler = MagicMock()
    ctrl = SystemController(mock_scheduler)
    ctrl.pause()
    mock_scheduler.pause_job.assert_any_call("scanner")
    mock_scheduler.pause_job.assert_any_call("scanner_fetch")
    assert ctrl.is_paused is True


def test_resume_restarts_scanner():
    mock_scheduler = MagicMock()
    ctrl = SystemController(mock_scheduler)
    ctrl.pause()
    ctrl.resume()
    mock_scheduler.resume_job.assert_any_call("scanner")
    mock_scheduler.resume_job.assert_any_call("scanner_fetch")
    assert ctrl.is_paused is False


def test_circuit_breaker_triggers_on_loss():
    mock_scheduler = MagicMock()
    ctrl = SystemController(mock_scheduler)
    triggered = ctrl.check_circuit_breaker(daily_pnl=-25.0, capital=500.0)
    assert triggered is True
    assert ctrl.is_paused is True


def test_circuit_breaker_does_not_trigger_on_small_loss():
    mock_scheduler = MagicMock()
    ctrl = SystemController(mock_scheduler)
    triggered = ctrl.check_circuit_breaker(daily_pnl=-10.0, capital=500.0)
    assert triggered is False
    assert ctrl.is_paused is False


def test_mode_toggle():
    mock_scheduler = MagicMock()
    ctrl = SystemController(mock_scheduler)
    assert ctrl.mode == "paper"
    ctrl.set_mode("live")
    assert ctrl.mode == "live"
    ctrl.set_mode("paper")
    assert ctrl.mode == "paper"
