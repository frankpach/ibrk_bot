# tests/test_iblayer_indicators.py
import pandas as pd
import pytest
from datetime import datetime


def make_ohlcv(n=30, base=100.0) -> pd.DataFrame:
    import random
    rng = random.Random(42)
    rows = []
    price = base
    for i in range(n):
        change = rng.uniform(-0.02, 0.025)
        price = max(price * (1 + change), base * 0.5)
        rows.append({
            "open": price * 0.999, "high": price * 1.01,
            "low": price * 0.99, "close": price,
            "volume": int(rng.uniform(500_000, 2_000_000))
        })
    return pd.DataFrame(rows)


class TestIBDataLayer:
    def setup_method(self):
        from app.analysis.mock_client import MockIBClient
        from app.analysis.data import IBDataLayer
        self.client = MockIBClient()
        self.layer = IBDataLayer(self.client)

    def test_get_ohlcv_returns_dataframe(self):
        df = self.layer.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
        assert df is not None
        assert len(df) > 0
        assert "close" in df.columns
        assert "volume" in df.columns

    def test_get_ohlcv_cache_hit(self):
        df1 = self.layer.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
        df2 = self.layer.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
        assert df1 is df2  # same object = cache hit

    def test_get_ohlcv_trade_entry_no_cache(self):
        df1 = self.layer.get_ohlcv("AAPL", "30 D", "1 day", "trade_entry")
        df2 = self.layer.get_ohlcv("AAPL", "30 D", "1 day", "trade_entry")
        assert df1 is not df2  # different objects = no cache

    def test_get_ohlcv_returns_none_on_failure(self):
        from app.analysis.data import IBDataLayer
        class BrokenClient:
            class ib:
                @staticmethod
                def reqHistoricalData(*args, **kwargs):
                    raise RuntimeError("IB down")
                def isConnected(self): return True
        layer = IBDataLayer(BrokenClient())
        result = layer.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
        assert result is None

    def test_run_scanner_returns_list(self):
        symbols = self.layer.run_scanner("HOT_BY_VOLUME")
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        assert all(isinstance(s, str) for s in symbols)

    def test_get_historical_volatility_returns_df(self):
        df = self.layer.get_historical_volatility("AAPL", "scanner")
        assert df is not None
        assert "close" in df.columns


class TestIndicatorEngine:
    def test_compute_features_returns_featureset(self):
        from app.analysis.indicators import compute_features, FeatureSet
        df = make_ohlcv(30)
        fs = compute_features("AAPL", df)
        assert isinstance(fs, FeatureSet)
        assert fs.symbol == "AAPL"

    def test_compute_features_rsi_in_range(self):
        from app.analysis.indicators import compute_features
        df = make_ohlcv(30)
        fs = compute_features("AAPL", df)
        assert fs.rsi_14 is not None
        assert 0 <= fs.rsi_14 <= 100

    def test_compute_features_with_none_hourly(self):
        from app.analysis.indicators import compute_features
        df = make_ohlcv(30)
        fs = compute_features("AAPL", df, df_hourly=None)
        assert fs.rsi_14 is not None  # daily still computed

    def test_compute_features_insufficient_data(self):
        from app.analysis.indicators import compute_features
        df = make_ohlcv(10)  # less than 15 rows
        fs = compute_features("AAPL", df)
        assert fs.rsi_14 is None
        assert fs.macd_line is None

    def test_compute_from_df_compatible(self):
        from app.analysis.indicators import compute_from_df
        df = make_ohlcv(30)
        result = compute_from_df(df)
        assert isinstance(result, dict)
        assert "rsi" in result

    def test_compute_single_indicator_rsi(self):
        from app.analysis.indicators import compute_single_indicator
        df = make_ohlcv(30)
        val = compute_single_indicator("rsi_14", df)
        assert val is not None
        assert 0 <= val <= 100

    def test_compute_single_indicator_unknown(self):
        from app.analysis.indicators import compute_single_indicator
        df = make_ohlcv(30)
        val = compute_single_indicator("unknown_indicator", df)
        assert val is None

    def test_classify_signal_strong(self):
        from app.analysis.indicators import classify_signal
        assert classify_signal(28.0, True, 1.6) == "STRONG"

    def test_classify_signal_medium(self):
        from app.analysis.indicators import classify_signal
        assert classify_signal(28.0, True, 1.0) == "MEDIUM"

    def test_classify_signal_weak(self):
        from app.analysis.indicators import classify_signal
        assert classify_signal(50.0, False, 1.0) == "WEAK"

    def test_classify_multitimeframe_strong(self):
        from app.analysis.indicators import classify_multitimeframe
        assert classify_multitimeframe("STRONG", "STRONG", "MEDIUM") == "STRONG"

    def test_classify_multitimeframe_medium(self):
        from app.analysis.indicators import classify_multitimeframe
        assert classify_multitimeframe("STRONG", "WEAK", "MEDIUM") == "MEDIUM"

    def test_classify_multitimeframe_weak(self):
        from app.analysis.indicators import classify_multitimeframe
        assert classify_multitimeframe("WEAK", "WEAK", "WEAK") == "WEAK"

    def test_preprocessor_still_imports_classify_signal(self):
        # Backwards compatibility
        from app.scanner.preprocessor import classify_signal
        assert classify_signal(28.0, True, 1.6) == "STRONG"

    def test_backtest_still_works_with_compute_from_df(self):
        from app.analysis.indicators import compute_from_df
        df = make_ohlcv(30)
        result = compute_from_df(df)
        assert "rsi" in result
        assert "macd_crossover" in result
