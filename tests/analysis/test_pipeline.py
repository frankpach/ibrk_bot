# tests/analysis/test_pipeline.py
import json
from unittest.mock import MagicMock, patch
from app.analysis.pipeline import AnalysisPipeline, AnalysisContext, AnalysisResult


def _make_data_layer():
    dl = MagicMock()
    df = MagicMock()
    df.__len__ = lambda self: 30
    df.__getitem__ = lambda self, k: MagicMock()
    df.__getitem__.iloc = [-1]
    dl.get_ohlcv.return_value = df
    dl.get_historical_volatility.return_value = None
    dl.get_news.return_value = []
    dl.get_earnings_date.return_value = None
    return dl


def test_pipeline_fetch_data_insufficient():
    dl = MagicMock()
    dl.get_ohlcv.return_value = None
    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"))
    result = pipe.run()
    assert result.recommendation == "ERROR"
    assert result.failed_at_step == "fetch_data"


@patch("app.analysis.indicators.compute_features")
@patch("app.analysis.scorer.compute_score")
@patch("app.analysis.hard_rules.check_all")
@patch("app.infrastructure.db.compat.insert_feature_snapshot")
@patch("app.infrastructure.db.compat.insert_candidate_decision")
def test_pipeline_hard_rules_fail(mock_insert_dec, mock_insert_fs, mock_hard, mock_score, mock_features):
    dl = _make_data_layer()
    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"))
    mock_features.return_value = MagicMock()
    mock_score.return_value = MagicMock(total=70, recommendation="BUY")
    mock_hard.return_value = MagicMock(passed=False, failures=["earnings"], warnings=[])
    result = pipe.run()
    assert result.recommendation == "REJECTED"
    assert result.hard_rules.passed is False


@patch("app.analysis.indicators.compute_features")
@patch("app.analysis.scorer.compute_score")
@patch("app.analysis.hard_rules.check_all")
@patch("app.infrastructure.db.compat.insert_feature_snapshot")
@patch("app.infrastructure.db.compat.insert_candidate_decision")
def test_pipeline_daily_discovery_low_score(mock_insert_dec, mock_insert_fs, mock_hard, mock_score, mock_features):
    dl = _make_data_layer()
    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="daily_discovery"))
    mock_features.return_value = MagicMock()
    mock_score.return_value = MagicMock(total=50, recommendation="HOLD")
    mock_hard.return_value = MagicMock(passed=True, failures=[], warnings=[])
    result = pipe.run()
    # When daily_discovery skips LLM, recommendation is not updated (stays UNKNOWN)
    assert result.recommendation == "UNKNOWN"


@patch("app.analysis.indicators.compute_features")
@patch("app.analysis.scorer.compute_score")
@patch("app.analysis.hard_rules.check_all")
@patch("app.ml.signal_filter.get_signal_filter")
@patch("app.infrastructure.db.compat.insert_feature_snapshot")
@patch("app.infrastructure.db.compat.insert_candidate_decision")
def test_pipeline_ml_filter_rejects(mock_insert_dec, mock_insert_fs, mock_get_filter, mock_hard, mock_score, mock_features):
    dl = _make_data_layer()
    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"))
    mock_features.return_value = MagicMock()
    mock_score.return_value = MagicMock(total=70, recommendation="BUY")
    mock_hard.return_value = MagicMock(passed=True, failures=[], warnings=[])
    mock_filter = MagicMock()
    mock_filter.should_ignore.return_value = True
    mock_get_filter.return_value = mock_filter
    result = pipe.run()
    assert result.recommendation == "REJECTED"
    assert "ML filter" in result.llm_narrative


@patch("subprocess.run")
@patch("app.analysis.indicators.compute_features")
@patch("app.analysis.scorer.compute_score")
@patch("app.analysis.hard_rules.check_all")
@patch("app.ml.signal_filter.get_signal_filter")
@patch("app.infrastructure.db.compat.insert_feature_snapshot")
@patch("app.infrastructure.db.compat.insert_candidate_decision")
def test_pipeline_llm_success(mock_insert_dec, mock_insert_fs, mock_get_filter, mock_hard, mock_score, mock_features, mock_subproc):
    dl = _make_data_layer()
    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"))
    mock_features.return_value = MagicMock(to_dict=lambda: {"rsi_14": 50})
    mock_score.return_value = MagicMock(total=70, recommendation="BUY")
    mock_hard.return_value = MagicMock(passed=True, failures=[], warnings=[], earnings_in_days=30)
    mock_filter = MagicMock()
    mock_filter.should_ignore.return_value = False
    mock_get_filter.return_value = mock_filter
    mock_subproc.return_value = MagicMock(
        stdout=json.dumps({"type": "text", "part": {"text": '{"narrative": "good", "confidence": 0.8, "recommendation": "BUY"}'}}),
        stderr="",
    )
    result = pipe.run()
    assert result.recommendation == "BUY"


@patch("app.analysis.indicators.compute_features")
@patch("app.analysis.scorer.compute_score")
@patch("app.analysis.hard_rules.check_all")
@patch("app.ml.signal_filter.get_signal_filter")
@patch("app.infrastructure.db.compat.insert_feature_snapshot")
@patch("app.infrastructure.db.compat.insert_candidate_decision")
def test_pipeline_exception(mock_insert_dec, mock_insert_fs, mock_get_filter, mock_hard, mock_score, mock_features):
    dl = _make_data_layer()
    pipe = AnalysisPipeline("AAPL", dl, AnalysisContext(mode="on_demand"))
    mock_features.side_effect = Exception("fail")
    result = pipe.run()
    assert result.recommendation == "ERROR"
    assert result.failed_at_step == "compute_indicators"


def test_analysis_result_to_dict():
    r = AnalysisResult(symbol="AAPL")
    d = r.to_dict()
    assert d["symbol"] == "AAPL"
    assert d["recommendation"] == "UNKNOWN"
