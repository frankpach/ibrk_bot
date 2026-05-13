import pytest
from app.risk.drawdown import DrawdownRecovery, RecoveryMode


class TestDrawdownRecovery:
    def test_normal_drawdown(self):
        r = DrawdownRecovery()
        mode = r.get_mode(0.03)  # 3%
        assert mode.mode == "normal"
        assert mode.position_size_mult == 1.0
        assert mode.entry_blocked is False
        assert mode.min_signal_strength == "WEAK"

    def test_cautious_drawdown(self):
        r = DrawdownRecovery()
        mode = r.get_mode(0.07)  # 7%
        assert mode.mode == "cautious"
        assert mode.position_size_mult == 0.5
        assert mode.entry_blocked is False
        assert mode.min_signal_strength == "STRONG"

    def test_pause_drawdown(self):
        r = DrawdownRecovery()
        mode = r.get_mode(0.12)  # 12%
        assert mode.mode == "pause"
        assert mode.position_size_mult == 0.0
        assert mode.entry_blocked is True

    def test_paper_only_drawdown(self):
        r = DrawdownRecovery()
        mode = r.get_mode(0.18)  # 18%
        assert mode.mode == "paper_only"
        assert mode.entry_blocked is True

    def test_should_block_entry(self):
        r = DrawdownRecovery()
        blocked, reason = r.should_block_entry(0.12)
        assert blocked is True
        assert "12.0%" in reason

    def test_should_allow_entry(self):
        r = DrawdownRecovery()
        blocked, reason = r.should_block_entry(0.03)
        assert blocked is False
        assert reason == "ok"

    def test_size_multiplier(self):
        r = DrawdownRecovery()
        assert r.get_size_multiplier(0.03) == 1.0
        assert r.get_size_multiplier(0.08) == 0.5
        assert r.get_size_multiplier(0.15) == 0.0

    def test_min_signal_strength(self):
        r = DrawdownRecovery()
        assert r.get_min_signal_strength(0.03) == "WEAK"
        assert r.get_min_signal_strength(0.08) == "STRONG"
