import pytest
from app.risk.dynamic_sizing import PositionSizer


class TestPositionSizer:
    def test_nvda_volatile_high_confidence(self):
        sizer = PositionSizer(max_risk_pct=0.02, max_position_usd=500.0, slippage_buffer=0.005)
        result = sizer.calculate_size(
            symbol="NVDA",
            entry_price=214.91,
            stop_loss_pct=0.025,
            capital=500.0,
            atr_pct=2.8,
            win_rate=0.65,
            score=78,
        )
        # Base: $10 / 0.03 = $333.33
        # WR: 1.15x, Vol: 0.71x, Conf: 1.04x
        # Final: $333.33 * 1.15 * 0.71 * 1.04 = ~$283
        assert result.units > 0
        assert result.units <= 500.0 / 214.91  # Capped
        assert "Win rate adj" in " ".join(result.reasons)
        assert result.estimated_risk_usd > 0

    def test_spy_stable(self):
        sizer = PositionSizer(slippage_buffer=0.005)
        result = sizer.calculate_size(
            symbol="SPY",
            entry_price=500.0,
            stop_loss_pct=0.025,
            capital=500.0,
            atr_pct=1.2,
            win_rate=0.55,
            score=72,
        )
        # Higher size due to lower volatility
        assert result.units > 0
        assert result.volatility_adj > 1.0  # 2.0 / 1.2 = 1.67

    def test_no_atr_uses_default(self):
        sizer = PositionSizer(slippage_buffer=0.005)
        result = sizer.calculate_size(
            symbol="AAPL",
            entry_price=100.0,
            stop_loss_pct=0.025,
            capital=500.0,
            atr_pct=None,
            win_rate=None,
            score=None,
        )
        assert result.volatility_adj == 1.0
        assert result.win_rate_adj == 1.0  # 0.5 + 0.5 default
        assert result.confidence_adj == 1.0

    def test_capped_at_max_position(self):
        sizer = PositionSizer(max_position_usd=100.0, slippage_buffer=0.005)
        result = sizer.calculate_size(
            symbol="CHEAP",
            entry_price=1.0,
            stop_loss_pct=0.01,
            capital=5000.0,
            atr_pct=0.5,
            win_rate=0.8,
            score=95,
        )
        assert result.units * 1.0 <= 100.0  # Capped

    def test_slippage_buffer_increases_risk(self):
        sizer1 = PositionSizer(slippage_buffer=0.0)
        sizer2 = PositionSizer(slippage_buffer=0.005)
        
        r1 = sizer1.calculate_size("A", 100.0, 0.025, 500.0, atr_pct=2.0, win_rate=0.5, score=75)
        r2 = sizer2.calculate_size("A", 100.0, 0.025, 500.0, atr_pct=2.0, win_rate=0.5, score=75)
        
        # With slippage buffer, effective SL is higher → smaller position
        assert r2.units < r1.units

    def test_reasons_are_informative(self):
        sizer = PositionSizer(slippage_buffer=0.005)
        result = sizer.calculate_size(
            symbol="TEST", entry_price=100.0, stop_loss_pct=0.025,
            capital=500.0, atr_pct=2.0, win_rate=0.6, score=80,
        )
        assert len(result.reasons) >= 4
        assert any("Base risk" in r for r in result.reasons)
        assert any("Win rate" in r for r in result.reasons)
