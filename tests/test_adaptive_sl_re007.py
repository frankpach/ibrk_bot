import pytest
from app.risk.adaptive_sl import calculate_adaptive_sl


class TestAdaptiveSL:
    def test_nvda_volatile(self):
        # NVDA with ATR 2.8%
        sl = calculate_adaptive_sl(2.8)
        assert sl == pytest.approx(0.042, abs=0.001)

    def test_spy_stable(self):
        # SPY with ATR 1.2%
        sl = calculate_adaptive_sl(1.2)
        assert sl == pytest.approx(0.018, abs=0.001)

    def test_minimum_bound(self):
        # Very low ATR
        sl = calculate_adaptive_sl(0.5)
        assert sl == pytest.approx(0.015, abs=0.001)  # Min 1.5%

    def test_maximum_bound(self):
        # Very high ATR
        sl = calculate_adaptive_sl(5.0)
        assert sl == pytest.approx(0.05, abs=0.001)  # Max 5%

    def test_none_atr_uses_default(self):
        sl = calculate_adaptive_sl(None)
        assert sl == pytest.approx(0.025, abs=0.001)

    def test_zero_atr_uses_default(self):
        sl = calculate_adaptive_sl(0.0)
        assert sl == pytest.approx(0.025, abs=0.001)

    def test_exact_atr_15(self):
        # ATR 1.5% -> exactly at minimum
        sl = calculate_adaptive_sl(1.5)
        assert sl == pytest.approx(0.0225, abs=0.001)
