import pytest
from app.risk.market_regime import MarketRegimeDetector, MarketRegime, RegimeAdjustments


class TestMarketRegimeDetector:
    def test_low_vol(self):
        d = MarketRegimeDetector()
        r = d.get_regime(12.0)
        assert r.regime == "low_vol"
        assert r.vix_level == 12.0

    def test_normal(self):
        d = MarketRegimeDetector()
        r = d.get_regime(18.0)
        assert r.regime == "normal"

    def test_high_vol(self):
        d = MarketRegimeDetector()
        r = d.get_regime(28.0)
        assert r.regime == "high_vol"

    def test_crisis(self):
        d = MarketRegimeDetector()
        r = d.get_regime(40.0)
        assert r.regime == "crisis"

    def test_boundary_15(self):
        d = MarketRegimeDetector()
        r = d.get_regime(15.0)
        assert r.regime == "normal"  # 15 < 25 → normal

    def test_boundary_25(self):
        d = MarketRegimeDetector()
        r = d.get_regime(25.0)
        assert r.regime == "high_vol"  # 25 >= 25 → high_vol

    def test_boundary_35(self):
        d = MarketRegimeDetector()
        r = d.get_regime(35.0)
        assert r.regime == "crisis"  # 35 >= 35 → crisis

    def test_adjustments_low_vol(self):
        d = MarketRegimeDetector()
        adj = d.get_adjustments("low_vol")
        assert adj.position_size_multiplier == 1.2
        assert adj.sl_widening_multiplier == 0.9
        assert adj.entry_blocked is False

    def test_adjustments_crisis(self):
        d = MarketRegimeDetector()
        adj = d.get_adjustments("crisis")
        assert adj.position_size_multiplier == 0.0
        assert adj.entry_blocked is True

    def test_adjustments_from_market_regime(self):
        d = MarketRegimeDetector()
        r = d.get_regime(30.0)
        adj = d.get_adjustments(r)
        assert adj.position_size_multiplier == 0.5
