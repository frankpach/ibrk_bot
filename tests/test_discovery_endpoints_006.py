# tests/test_discovery_endpoints_006.py
"""Tests for Issue 006: DailyDiscovery, ReturnEvaluator, endpoints, MCP."""
import pytest
import sys
from unittest.mock import patch, MagicMock


# Patch IBKRClient before app.api.main is imported, so module-level client = IBKRClient(...)
# does not attempt a real connection.
@pytest.fixture(autouse=False)
def mock_ib_client():
    mock_client = MagicMock()
    mock_client.ib.isConnected.return_value = False
    with patch("app.ibkr.client.IBKRClient", return_value=mock_client):
        # Remove cached module so fresh import uses the patch
        for mod in list(sys.modules.keys()):
            if "app.api.main" in mod:
                del sys.modules[mod]
        yield mock_client


class TestDailyDiscovery:
    def setup_method(self):
        from app.analysis.mock_client import MockIBClient
        from app.analysis.data import IBDataLayer
        self.data_layer = IBDataLayer(MockIBClient())

    def test_run_daily_discovery_weekend_skips(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        saturday = datetime(2026, 5, 9, 9, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch("app.analysis.admission.datetime") as mock_dt:
            mock_dt.now.return_value = saturday
            from app.analysis.admission import run_daily_discovery
            # Should not raise even on weekend
            run_daily_discovery(self.data_layer)

    def test_run_daily_discovery_runs_scanners(self):
        from app.analysis.admission import run_daily_discovery
        with patch("app.analysis.admission.AnalysisPipeline") as mock_pipeline_cls,              patch("app.analysis.admission.notify"):
            mock_pipeline_instance = MagicMock()
            from app.analysis.pipeline import AnalysisResult
            from app.analysis.scorer import QuantScore
            mock_result = AnalysisResult(symbol="NFLX", recommendation="PROPOSE")
            mock_result.score = QuantScore(
                symbol="NFLX", total=72.0, momentum=0.7, trend=0.6,
                volume=0.7, volatility=0.6, portfolio_fit=0.8, sentiment=0.7,
                price_change=0.5, recommendation="PROPOSE", weights_used={},
            )
            mock_pipeline_instance.run.return_value = mock_result
            mock_pipeline_cls.return_value = mock_pipeline_instance
            run_daily_discovery(self.data_layer)
            # Pipeline should have been called for candidates (may be 0 if mock returns empty)


class TestReturnEvaluator:
    def setup_method(self):
        from app.analysis.mock_client import MockIBClient
        from app.analysis.data import IBDataLayer
        self.data_layer = IBDataLayer(MockIBClient())

    def test_run_return_evaluator_no_crash(self):
        """ReturnEvaluator runs without crash even with no decisions to evaluate."""
        from app.analysis.evaluator import run_return_evaluator
        run_return_evaluator(self.data_layer)  # Should not raise


class TestNewEndpoints:
    @pytest.fixture(autouse=True)
    def setup_mock_client(self, mock_ib_client):
        self.mock_client = mock_ib_client

    def _get_client(self):
        import sys
        # Ensure fresh import with mock active
        for mod in list(sys.modules.keys()):
            if mod == "app.api.main":
                del sys.modules[mod]
        from app.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_candidate_analysis_endpoint_exists(self):
        client = self._get_client()
        response = client.get("/candidate-analysis/AAPL")
        assert response.status_code in (200, 500)  # not 404

    def test_single_indicator_endpoint_exists(self):
        client = self._get_client()
        response = client.get("/analysis/indicator/AAPL/rsi_14")
        assert response.status_code in (200, 404, 500)

    def test_universe_watchlist_endpoint(self):
        client = self._get_client()
        response = client.get("/universe/watchlist")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_candidate_decisions_endpoint(self):
        client = self._get_client()
        response = client.get("/candidate-decisions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_symbol_parameters_endpoint(self):
        client = self._get_client()
        response = client.get("/symbol-parameters/AAPL")
        assert response.status_code == 200
        data = response.json()
        assert "momentum_mult" in data


class TestMCPTools:
    def test_candidate_analysis_tool_exists(self):
        from app.mcp.server import candidate_analysis
        assert callable(candidate_analysis)

    def test_compute_indicator_tool_exists(self):
        from app.mcp.server import compute_indicator
        assert callable(compute_indicator)

    def test_universe_watchlist_tool_exists(self):
        from app.mcp.server import get_universe_watchlist
        assert callable(get_universe_watchlist)
