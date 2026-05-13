# tests/system/test_controller.py
from unittest.mock import MagicMock, patch
from app.system.controller import SystemController, init_controller, get_controller, CIRCUIT_BREAKER_PCT


def test_pause_resume():
    sched = MagicMock()
    ctrl = SystemController(sched)
    ctrl.pause()
    assert ctrl.is_paused is True
    sched.pause_job.assert_any_call("signal_processor")
    sched.pause_job.assert_any_call("scanner")
    ctrl.resume()
    assert ctrl.is_paused is False
    sched.resume_job.assert_any_call("signal_processor")
    sched.resume_job.assert_any_call("scanner")


def test_set_mode_live():
    sched = MagicMock()
    ctrl = SystemController(sched)
    with patch("app.system.controller.notify") as mock_notify:
        ctrl.set_mode("live")
    assert ctrl.mode == "live"


def test_set_mode_paper():
    sched = MagicMock()
    ctrl = SystemController(sched)
    ctrl.set_mode("paper")
    assert ctrl.mode == "paper"


def test_set_mode_invalid():
    sched = MagicMock()
    ctrl = SystemController(sched)
    try:
        ctrl.set_mode("invalid")
        assert False, "Expected ValueError"
    except ValueError:
        pass


@patch("app.system.controller.notify")
def test_check_circuit_breaker_triggered(mock_notify):
    sched = MagicMock()
    ctrl = SystemController(sched)
    result = ctrl.check_circuit_breaker(-6000.0, 100000.0)
    assert result is True
    assert ctrl.is_paused is True
    mock_notify.assert_called_once()


@patch("app.system.controller.notify")
def test_check_circuit_breaker_not_triggered(mock_notify):
    sched = MagicMock()
    ctrl = SystemController(sched)
    result = ctrl.check_circuit_breaker(-1000.0, 100000.0)
    assert result is False
    mock_notify.assert_not_called()


def test_check_circuit_breaker_positive_pnl():
    sched = MagicMock()
    ctrl = SystemController(sched)
    result = ctrl.check_circuit_breaker(1000.0, 100000.0)
    assert result is False


def test_status():
    sched = MagicMock()
    ctrl = SystemController(sched)
    s = ctrl.status()
    assert "paused" in s
    assert "mode" in s


def test_get_controller_before_init():
    import app.system.controller as ctrl_mod
    old = ctrl_mod._controller
    ctrl_mod._controller = None
    try:
        get_controller()
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass
    finally:
        ctrl_mod._controller = old


def test_init_controller():
    import app.system.controller as ctrl_mod
    old = ctrl_mod._controller
    ctrl_mod._controller = None
    sched = MagicMock()
    ctrl = init_controller(sched)
    assert ctrl is not None
    assert get_controller() is ctrl
    ctrl_mod._controller = old
