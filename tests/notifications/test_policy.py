# tests/notifications/test_policy.py
from app.notifications.policy import NotificationPolicy, DigestGenerator, get_policy, get_digest_generator


def test_policy_verbose_allows_all():
    p = NotificationPolicy(level="verbose")
    assert p.should_notify("generic")
    assert p.should_notify("circuit_breaker")


def test_policy_critical_blocks_normal():
    p = NotificationPolicy(level="critical_only")
    assert p.should_notify("circuit_breaker")
    assert not p.should_notify("position_opened")


def test_policy_normal_allows_normal():
    p = NotificationPolicy(level="normal")
    assert p.should_notify("position_opened")
    assert not p.should_notify("generic")


def test_policy_invalid_level_raises():
    p = NotificationPolicy()
    try:
        p.set_level("invalid")
        assert False
    except ValueError:
        pass


def test_digest_generator():
    from app.db.models import Trade
    from datetime import datetime
    dg = DigestGenerator()
    trade = Trade(
        id=1, symbol="AAPL", action="BUY", quantity=10,
        entry_price=100.0, stop_loss_price=98.0,
        take_profit_price=110.0, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=50.0, pnl_pct=0.05,
        opened_at=datetime.utcnow(), closed_at=None, order_id="1",
    )
    msg = dg.generate_digest([trade], daily_pnl=50.0, signals_processed=5, system_status="OK")
    assert "AAPL" in msg
    assert "$50.0" in msg
    assert "OK" in msg


def test_digest_suppression():
    dg = DigestGenerator()
    assert not dg.is_suppressed("circuit_breaker")
    dg.start_suppression()
    assert dg.is_suppressed("position_opened")
    assert not dg.is_suppressed("circuit_breaker")
    dg.end_suppression()
    assert not dg.is_suppressed("position_opened")


def test_singletons():
    assert get_policy() is get_policy()
    assert get_digest_generator() is get_digest_generator()
