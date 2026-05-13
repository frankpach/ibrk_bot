import pytest
import time
from app.notifications.throttler import NotificationThrottler


class TestNotificationThrottler:
    def test_circuit_breaker_once_per_activation(self):
        t = NotificationThrottler()
        
        # First notification passes
        assert t.notify_if_changed("circuit_breaker", "CB activated") is True
        
        # Second notification is throttled
        assert t.notify_if_changed("circuit_breaker", "CB still active") is False
        
        # After reset, passes again
        t.reset_state("circuit_breaker")
        assert t.notify_if_changed("circuit_breaker", "CB activated again") is True

    def test_position_closed_once_per_trade(self):
        t = NotificationThrottler()
        
        assert t.notify_if_changed("position_closed", "Trade 42 closed", content_hash="trade_42") is True
        assert t.notify_if_changed("position_closed", "Trade 42 closed again", content_hash="trade_42") is False
        assert t.notify_if_changed("position_closed", "Trade 43 closed", content_hash="trade_43") is True

    def test_digest_never_throttled(self):
        t = NotificationThrottler()
        
        assert t.notify_if_changed("digest", "Daily digest 1") is True
        assert t.notify_if_changed("digest", "Daily digest 2") is True
        assert t.notify_if_changed("digest", "Daily digest 3") is True

    def test_force_bypasses_throttle(self):
        t = NotificationThrottler()
        
        assert t.notify_if_changed("circuit_breaker", "CB") is True
        assert t.notify_if_changed("circuit_breaker", "CB", force=True) is True

    def test_min_interval(self):
        t = NotificationThrottler()
        
        assert t.notify_if_changed("signal_ignored", "Ignored AAPL") is True
        assert t.notify_if_changed("signal_ignored", "Ignored AAPL") is False  # Same hash, throttled
        
        # After 301 seconds, should pass
        # We'll manipulate state directly for test speed
        t._state[("signal_ignored", "Ignored AAPL")] = time.time() - 301
        assert t.notify_if_changed("signal_ignored", "Ignored AAPL") is True

    def test_clear_all(self):
        t = NotificationThrottler()
        t.notify_if_changed("circuit_breaker", "CB")
        t.notify_if_changed("position_closed", "PC", content_hash="t1")
        
        t.clear_all()
        assert len(t._state) == 0
        assert t.notify_if_changed("circuit_breaker", "CB again") is True
