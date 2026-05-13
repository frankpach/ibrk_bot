# tests/analysis/test_data.py
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from app.analysis.data import IBDataLayer, TTL


def _make_bar(open=100, high=101, low=99, close=100.5, volume=1000):
    return MagicMock(open=open, high=high, low=low, close=close, volume=volume)


# ---------- cache ----------
def test_cache_hit():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = dl._cache_key("AAPL", "scanner", "30 D:1 day:STK")
    dl._set_cached(key, "data", "scanner")
    assert dl._get_cached(key) == "data"


def test_cache_miss():
    client = MagicMock()
    dl = IBDataLayer(client)
    assert dl._get_cached("missing:key") is None


def test_cache_expires():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = "AAPL:scanner:x"
    dl._cache[key] = ("old", 0)
    assert dl._get_cached(key) is None


def test_set_cached_skips_trade_entry():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = "AAPL:trade_entry:x"
    dl._set_cached(key, "data", "trade_entry")
    assert dl._get_cached(key) is None


def test_set_cached_skips_none_on_demand():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = "AAPL:on_demand:x"
    dl._set_cached(key, None, "on_demand")
    assert dl._get_cached(key) is None


# ---------- get_ohlcv ----------
@patch("app.analysis.data.build_contract")
@patch("app.analysis.data.get_what_to_show")
@patch("app.analysis.data.get_use_rth")
def test_get_ohlcv_cache_hit(mock_rth, mock_wts, mock_build):
    client = MagicMock()
    dl = IBDataLayer(client)
    key = dl._cache_key("AAPL", "scanner", "30 D:1 day:STK")
    dl._set_cached(key, pd.DataFrame({"close": [100]}), "scanner")
    df = dl.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
    assert df is not None
    client.ib.reqHistoricalData.assert_not_called()


@patch("app.analysis.data.build_contract")
@patch("app.analysis.data.get_what_to_show")
@patch("app.analysis.data.get_use_rth")
def test_get_ohlcv_success(mock_rth, mock_wts, mock_build):
    client = MagicMock()
    client.ib.reqHistoricalData.return_value = [_make_bar() for _ in range(20)]
    dl = IBDataLayer(client)
    df = dl.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
    assert df is not None
    assert len(df) == 20
    assert "close" in df.columns


@patch("app.analysis.data.build_contract")
@patch("app.analysis.data.get_what_to_show")
@patch("app.analysis.data.get_use_rth")
def test_get_ohlcv_fallback(mock_rth, mock_wts, mock_build):
    client = MagicMock()
    client.ib.reqHistoricalData.side_effect = [
        [],  # primary empty
        [_make_bar() for _ in range(20)],  # fallback 30 D
    ]
    dl = IBDataLayer(client)
    df = dl.get_ohlcv("AAPL", "60 D", "1 day", "scanner")
    assert df is not None


@patch("app.analysis.data.build_contract")
@patch("app.analysis.data.get_what_to_show")
@patch("app.analysis.data.get_use_rth")
def test_get_ohlcv_insufficient_bars(mock_rth, mock_wts, mock_build):
    client = MagicMock()
    client.ib.reqHistoricalData.return_value = [_make_bar() for _ in range(5)]
    dl = IBDataLayer(client)
    df = dl.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
    assert df is None


@patch("app.analysis.data.build_contract")
def test_get_ohlcv_exception(mock_build):
    client = MagicMock()
    client.ib.reqHistoricalData.side_effect = Exception("IB error")
    dl = IBDataLayer(client)
    df = dl.get_ohlcv("AAPL", "30 D", "1 day", "scanner")
    assert df is None


# ---------- get_indicators ----------
@patch("app.analysis.data.IBDataLayer.get_ohlcv")
@patch("app.analysis.indicators.compute_features")
def test_get_indicators_success(mock_features, mock_ohlcv):
    from app.analysis.indicators import FeatureSet
    fs = FeatureSet(symbol="AAPL", timestamp=__import__("datetime").datetime.utcnow())
    fs.rsi_14 = 55.0
    fs.volume_ratio_20d = 1.5
    fs.macd_crossover = True
    fs.bollinger_position = 0.5
    fs.atr_pct = 2.0
    mock_features.return_value = fs
    mock_ohlcv.return_value = pd.DataFrame({"close": list(range(30))})
    client = MagicMock()
    dl = IBDataLayer(client)
    result = dl.get_indicators("AAPL")
    assert result["rsi"] == 55.0
    assert result["volume_ratio"] == 1.5


@patch("app.analysis.data.IBDataLayer.get_ohlcv")
def test_get_indicators_none_df(mock_ohlcv):
    mock_ohlcv.return_value = None
    client = MagicMock()
    dl = IBDataLayer(client)
    assert dl.get_indicators("AAPL") == {}


@patch("app.analysis.data.IBDataLayer.get_ohlcv")
def test_get_indicators_exception(mock_ohlcv):
    mock_ohlcv.side_effect = Exception("fail")
    client = MagicMock()
    dl = IBDataLayer(client)
    assert dl.get_indicators("AAPL") == {}


# ---------- get_historical_volatility ----------
def test_get_hv_cache_hit():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = dl._cache_key("AAPL", "scanner", "HV")
    dl._set_cached(key, pd.DataFrame({"close": [0.2]}), "scanner")
    df = dl.get_historical_volatility("AAPL", "scanner")
    assert df is not None


def test_get_hv_success():
    client = MagicMock()
    client.ib.reqHistoricalData.return_value = [_make_bar(close=0.2) for _ in range(10)]
    dl = IBDataLayer(client)
    df = dl.get_historical_volatility("AAPL", "scanner")
    assert df is not None
    assert "close" in df.columns


def test_get_hv_empty():
    client = MagicMock()
    client.ib.reqHistoricalData.return_value = []
    dl = IBDataLayer(client)
    assert dl.get_historical_volatility("AAPL", "scanner") is None


def test_get_hv_exception():
    client = MagicMock()
    client.ib.reqHistoricalData.side_effect = Exception("fail")
    dl = IBDataLayer(client)
    assert dl.get_historical_volatility("AAPL", "scanner") is None


# ---------- get_implied_volatility ----------
def test_get_iv_cache_hit():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = dl._cache_key("AAPL", "scanner", "IV")
    dl._set_cached(key, pd.DataFrame({"close": [0.3]}), "scanner")
    df = dl.get_implied_volatility("AAPL", "scanner")
    assert df is not None


def test_get_iv_success():
    client = MagicMock()
    client.ib.reqHistoricalData.return_value = [_make_bar(close=0.3) for _ in range(10)]
    dl = IBDataLayer(client)
    df = dl.get_implied_volatility("AAPL", "scanner")
    assert df is not None


def test_get_iv_empty():
    client = MagicMock()
    client.ib.reqHistoricalData.return_value = []
    dl = IBDataLayer(client)
    assert dl.get_implied_volatility("AAPL", "scanner") is None


# ---------- get_news ----------
def test_get_news_cache_hit():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = dl._cache_key("AAPL", "scanner", "news")
    dl._set_cached(key, [{"title": "cached"}], "scanner")
    news = dl.get_news("AAPL")
    assert news == [{"title": "cached"}]


@patch("app.scanner.news._extract_sentiment")
def test_get_news_yahoo_fallback(mock_sentiment):
    mock_sentiment.return_value = "positive"
    client = MagicMock()
    client.ib.reqHistoricalNews.side_effect = Exception("no news")
    dl = IBDataLayer(client)
    news = dl.get_news("AAPL")
    assert isinstance(news, list)


def test_get_news_exception():
    client = MagicMock()
    client.ib.reqHistoricalNews.side_effect = Exception("fail")
    dl = IBDataLayer(client)
    news = dl.get_news("AAPL")
    assert news == []


# ---------- get_earnings_date ----------
def test_get_earnings_cache_hit():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = dl._cache_key("AAPL", "fundamentals", "earnings")
    from datetime import datetime
    dt = datetime(2024, 1, 15)
    dl._set_cached(key, dt, "fundamentals")
    assert dl.get_earnings_date("AAPL") == dt


def test_get_earnings_date_success():
    from datetime import datetime
    client = MagicMock()
    client.ib.reqFundamentalData.return_value = "<xml><EarningsDate>2024-01-15</EarningsDate></xml>"
    dl = IBDataLayer(client)
    result = dl.get_earnings_date("AAPL")
    assert result == datetime(2024, 1, 15)


def test_get_earnings_date_no_match():
    client = MagicMock()
    client.ib.reqFundamentalData.return_value = "<xml></xml>"
    dl = IBDataLayer(client)
    assert dl.get_earnings_date("AAPL") is None


def test_get_earnings_date_exception():
    client = MagicMock()
    client.ib.reqFundamentalData.side_effect = Exception("fail")
    dl = IBDataLayer(client)
    assert dl.get_earnings_date("AAPL") is None


# ---------- run_scanner ----------
def test_run_scanner_cache_hit():
    client = MagicMock()
    dl = IBDataLayer(client)
    key = dl._cache_key("SCANNER", "scanner", "TOP_PERC_GAIN")
    dl._set_cached(key, ["AAPL"], "scanner")
    assert dl.run_scanner("TOP_PERC_GAIN") == ["AAPL"]


def test_run_scanner_mock_list():
    client = MagicMock()
    client.ib.reqScannerData.return_value = ["AAPL", "TSLA"]
    dl = IBDataLayer(client)
    result = dl.run_scanner("TOP_PERC_GAIN")
    assert result == ["AAPL", "TSLA"]


def test_run_scanner_real_objects():
    client = MagicMock()
    item = MagicMock()
    item.contractDetails.contract.symbol = "AAPL"
    client.ib.reqScannerData.return_value = [item]
    dl = IBDataLayer(client)
    result = dl.run_scanner("TOP_PERC_GAIN")
    assert result == ["AAPL"]


def test_run_scanner_exception():
    client = MagicMock()
    client.ib.reqScannerData.side_effect = Exception("fail")
    dl = IBDataLayer(client)
    assert dl.run_scanner("TOP_PERC_GAIN") == []


# ---------- get_spy_price_on ----------
def test_get_spy_price_on_cache_hit():
    client = MagicMock()
    dl = IBDataLayer(client)
    from datetime import datetime
    dt = datetime(2024, 1, 15)
    key = dl._cache_key("SPY", "backtest", dt.strftime("%Y%m%d"))
    dl._set_cached(key, 450.0, "backtest")
    assert dl.get_spy_price_on(dt) == 450.0


@patch("app.analysis.data.IBDataLayer.get_ohlcv")
def test_get_spy_price_on_success(mock_ohlcv):
    mock_ohlcv.return_value = pd.DataFrame({"close": [445.0, 450.0]})
    client = MagicMock()
    dl = IBDataLayer(client)
    from datetime import datetime
    price = dl.get_spy_price_on(datetime(2024, 1, 15))
    assert price == 450.0


@patch("app.analysis.data.IBDataLayer.get_ohlcv")
def test_get_spy_price_on_none(mock_ohlcv):
    mock_ohlcv.return_value = None
    client = MagicMock()
    dl = IBDataLayer(client)
    from datetime import datetime
    assert dl.get_spy_price_on(datetime(2024, 1, 15)) is None
