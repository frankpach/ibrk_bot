import pytest
import time
from app.risk.cooldown import ReentryCooldown


class TestReentryCooldown:
    def test_sl_cooldown_blocks_reentry(self):
        c = ReentryCooldown(cooldown_hours=24.0, min_move_pct=0.02)
        c.record_exit("NVDA", 200.0, "STOP_LOSS")
        
        # Price moved only 1% (< 2% threshold), should be blocked
        allowed, reason = c.can_reenter("NVDA", 202.0)
        assert allowed is False
        assert "SL cooldown" in reason

    def test_sl_cooldown_allows_after_time(self):
        c = ReentryCooldown(cooldown_hours=0.001)  # 3.6 seconds
        c.record_exit("NVDA", 200.0, "STOP_LOSS")
        time.sleep(0.05)  # Wait past cooldown
        
        allowed, reason = c.can_reenter("NVDA", 205.0)
        assert allowed is True

    def test_price_move_allows_early_reentry(self):
        c = ReentryCooldown(cooldown_hours=24.0, min_move_pct=0.02)
        c.record_exit("NVDA", 200.0, "STOP_LOSS")
        
        # Price moved 3% from exit
        allowed, reason = c.can_reenter("NVDA", 206.0)
        assert allowed is True
        assert "price moved" in reason

    def test_tp_shorter_cooldown(self):
        c = ReentryCooldown(tp_cooldown_hours=0.00001, min_move_pct=0.05)  # 0.036s, high move threshold
        c.record_exit("AAPL", 150.0, "TAKE_PROFIT")
        time.sleep(0.1)
        
        # Price moved 1% (< 5% threshold), cooldown expired, should allow
        allowed, reason = c.can_reenter("AAPL", 151.5)
        assert allowed is True

    def test_tp_blocks_during_cooldown(self):
        c = ReentryCooldown(tp_cooldown_hours=4.0)
        c.record_exit("AAPL", 150.0, "TAKE_PROFIT")
        
        allowed, reason = c.can_reenter("AAPL", 155.0)
        assert allowed is False
        assert "TP cooldown" in reason

    def test_no_record_allows_entry(self):
        c = ReentryCooldown()
        allowed, reason = c.can_reenter("TSLA", 250.0)
        assert allowed is True
        assert reason == "ok"

    def test_clear_symbol(self):
        c = ReentryCooldown()
        c.record_exit("NVDA", 200.0, "STOP_LOSS")
        c.clear("NVDA")
        
        allowed, _ = c.can_reenter("NVDA", 205.0)
        assert allowed is True

    def test_trailing_stop_uses_tp_cooldown(self):
        c = ReentryCooldown(tp_cooldown_hours=4.0)
        c.record_exit("META", 300.0, "TRAILING_STOP")
        
        allowed, reason = c.can_reenter("META", 305.0)
        assert allowed is False
        assert "TP cooldown" in reason
