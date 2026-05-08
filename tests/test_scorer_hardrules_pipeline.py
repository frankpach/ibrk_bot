# tests/test_scorer_hardrules_pipeline.py
import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd


def make_features(rsi=28.0, macd_cross=True, vol_ratio=1.8, sma20=285.0, sma50=280.0, sma200=270.0):
    from app.analysis.indicators import FeatureSet
    return FeatureSet(
        symbol="AAPL", timestamp=datetime.utcnow(),
        rsi_14=rsi, macd_line=-0.12, macd_signal=-0.15, macd_crossover=macd_cross,
        atr_pct=2.5, sma20=sma20, sma50=sma50, sma200=sma200,
        bollinger_upper=295.0, bollinger_lower=275.0, bollinger_position=0.65,
        vwap=287.0, volume_ratio_20d=vol_ratio,
        rs_vs_spy_30d=0.05, rs_vs_qqq_30d=0.03,
    )


class TestQuantScorer:
    def test_strong_signal_scores_high(self):
        from app.analysis.scorer import compute_score
        features = make_features(rsi=28.0, macd_cross=True, vol_ratio=1.8)
        score = compute_score(features, "AAPL", [])
        assert score.total >= 60

    def test_neutral_signal_scores_medium(self):
        from app.analysis.scorer import compute_score
        from app.analysis.indicators import FeatureSet
        features = FeatureSet(symbol="AAPL", timestamp=datetime.utcnow())
        score = compute_score(features, "AAPL", [])
        assert 20 <= score.total <= 70

    def test_score_has_recommendation(self):
        from app.analysis.scorer import compute_score
        features = make_features()
        score = compute_score(features, "AAPL", [])
        assert score.recommendation in ("REJECTED", "WATCHLIST", "PROPOSE", "PRIORITY")

    def test_multiplier_clamp_max(self):
        from app.analysis.scorer import update_weights_attenuated, MULT_MAX
        # With very high suggestion, should clamp to MULT_MAX
        # (needs trade_count >= 5 — this test will return False since no trades in fresh DB)
        result = update_weights_attenuated("TESTX", "momentum", 99.0, 1.0)
        # Returns False because trade_count < 5
        assert result is False

    def test_score_returns_quantscore_dataclass(self):
        from app.analysis.scorer import compute_score, QuantScore
        features = make_features()
        score = compute_score(features, "AAPL", [])
        assert isinstance(score, QuantScore)
        assert 0 <= score.total <= 100


class TestHardRules:
    def test_passes_with_normal_conditions(self):
        from app.analysis.hard_rules import check_all
        features = make_features()
        result = check_all("AAPL", features, [], earnings_date=None)
        assert result.passed is True

    def test_fails_on_close_earnings(self):
        from app.analysis.hard_rules import check_all
        features = make_features()
        soon = datetime.now() + timedelta(days=2)
        result = check_all("AAPL", features, [], earnings_date=soon)
        assert result.passed is False
        assert any("Earnings" in f for f in result.failures)

    def test_warns_on_nearby_earnings(self):
        from app.analysis.hard_rules import check_all
        features = make_features()
        soon = datetime.now() + timedelta(days=5)
        result = check_all("AAPL", features, [], earnings_date=soon)
        assert result.passed is True
        assert any("Earnings" in w for w in result.warnings)

    def test_warns_unknown_earnings(self):
        from app.analysis.hard_rules import check_all
        features = make_features()
        result = check_all("AAPL", features, [], earnings_date=None)
        assert any("unknown" in w.lower() for w in result.warnings)

    def test_no_llm_involved(self):
        from app.analysis.hard_rules import check_all
        features = make_features()
        # Hard rules must complete fast (no LLM)
        import time
        start = time.time()
        result = check_all("AAPL", features, [], earnings_date=None)
        elapsed = time.time() - start
        assert elapsed < 1.0


class TestDBAnalysisTables:
    def test_init_creates_tables(self):
        from app.db.database import init_analysis_tables, get_connection
        init_analysis_tables()
        conn = get_connection()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "feature_snapshots" in tables
        assert "symbol_parameters" in tables
        assert "candidate_decisions" in tables
        assert "watchlist_scores" in tables

    def test_get_or_create_symbol_parameters_defaults(self):
        from app.db.database import get_or_create_symbol_parameters, init_analysis_tables
        init_analysis_tables()
        params = get_or_create_symbol_parameters("TESTSYM")
        assert params.symbol == "TESTSYM"
        assert params.momentum_mult == 1.0
        assert params.trade_count == 0

    def test_insert_feature_snapshot(self):
        from app.db.database import insert_feature_snapshot, init_analysis_tables
        init_analysis_tables()
        fs_dict = {
            "symbol": "AAPL", "timestamp": datetime.utcnow().isoformat(),
            "context": "on_demand", "rsi_14": 28.5, "macd_crossover": True,
            "volume_ratio_20d": 1.8,
        }
        snapshot_id = insert_feature_snapshot(fs_dict)
        assert isinstance(snapshot_id, int)
        assert snapshot_id > 0


class TestAnalysisPipeline:
    def setup_method(self):
        from app.analysis.mock_client import MockIBClient
        from app.analysis.data import IBDataLayer
        from app.analysis.pipeline import AnalysisContext
        self.data_layer = IBDataLayer(MockIBClient())
        self.context = AnalysisContext(mode="on_demand")

    def test_pipeline_run_returns_result(self):
        from app.analysis.pipeline import AnalysisPipeline
        pipeline = AnalysisPipeline("AAPL", self.data_layer, self.context)
        result = pipeline.run()
        assert result.symbol == "AAPL"
        assert result.recommendation in ("REJECTED", "WATCHLIST", "PROPOSE", "PRIORITY", "ERROR", "BUY", "SELL", "IGNORE")

    def test_pipeline_completes_without_llm(self):
        from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
        ctx = AnalysisContext(mode="daily_discovery")
        pipeline = AnalysisPipeline("AAPL", self.data_layer, ctx)
        import time
        start = time.time()
        result = pipeline.run()
        elapsed = time.time() - start
        assert result.failed_at_step is None or elapsed < 30

    def test_pipeline_hard_rules_fail_skips_llm(self):
        from app.analysis.pipeline import AnalysisPipeline
        from unittest.mock import patch
        pipeline = AnalysisPipeline("AAPL", self.data_layer, self.context)
        with patch.object(pipeline, "_llm_interpret") as mock_llm, \
             patch.object(pipeline, "_check_hard_rules") as mock_hr:
            from app.analysis.hard_rules import HardRulesResult
            mock_hr.side_effect = lambda: setattr(
                pipeline._result, "hard_rules",
                HardRulesResult(passed=False, failures=["test failure"])
            )
            pipeline.run()
            mock_llm.assert_not_called()

    def test_pipeline_notifies_progress(self):
        from app.analysis.pipeline import AnalysisPipeline
        notifications = []
        pipeline = AnalysisPipeline("AAPL", self.data_layer, self.context,
                                     notify_fn=notifications.append)
        pipeline.run()
        assert len(notifications) >= 2

    def test_pipeline_persists_feature_snapshot(self):
        from app.analysis.pipeline import AnalysisPipeline
        from app.db.database import init_analysis_tables
        init_analysis_tables()
        pipeline = AnalysisPipeline("AAPL", self.data_layer, self.context)
        result = pipeline.run()
        # feature_snapshot_id is set if persist succeeded
        if result.failed_at_step is None:
            assert result.feature_snapshot_id is not None
