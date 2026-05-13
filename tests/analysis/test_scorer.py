# tests/analysis/test_scorer.py
from unittest.mock import MagicMock, patch
import pytest
from app.analysis.scorer import (
    _dim_momentum,
    _dim_trend,
    _dim_volume,
    _dim_volatility,
    _dim_portfolio_fit,
    _dim_sentiment,
    _dim_price_change,
    _get_multipliers,
    compute_score,
    update_weights_attenuated,
    THRESHOLDS,
    GLOBAL_WEIGHTS,
)


def _make_features(**kwargs):
    defaults = {
        "rsi_14": None,
        "macd_crossover": None,
        "sma20": None,
        "sma50": None,
        "sma200": None,
        "rs_vs_spy_30d": None,
        "bollinger_position": None,
        "volume_ratio_20d": None,
        "atr_pct": None,
        "price_change_pct": None,
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


# ---------- _dim_momentum ----------
def test_dim_momentum_rsi_extreme():
    f = _make_features(rsi_14=20, macd_crossover=False)
    assert _dim_momentum(f) == 0.5


def test_dim_momentum_rsi_moderate():
    f = _make_features(rsi_14=30, macd_crossover=False)
    assert _dim_momentum(f) == 0.3


def test_dim_momentum_rsi_mild():
    f = _make_features(rsi_14=40, macd_crossover=False)
    assert _dim_momentum(f) == 0.1


def test_dim_momentum_macd():
    f = _make_features(rsi_14=50, macd_crossover=True)
    assert _dim_momentum(f) == 0.4


def test_dim_momentum_combined():
    f = _make_features(rsi_14=20, macd_crossover=True)
    assert _dim_momentum(f) == 0.9


def test_dim_momentum_none():
    f = _make_features()
    assert _dim_momentum(f) == 0.0


# ---------- _dim_trend ----------
def test_dim_trend_sma_bullish():
    f = _make_features(sma50=110, sma200=100, sma20=115, rs_vs_spy_30d=0.06, bollinger_position=0.7)
    assert _dim_trend(f) == pytest.approx(1.0)


def test_dim_trend_sma_bearish():
    f = _make_features(sma50=90, sma200=100, sma20=85, rs_vs_spy_30d=-0.01, bollinger_position=0.3)
    assert _dim_trend(f) == pytest.approx(0.0)


def test_dim_trend_rs_weak():
    f = _make_features(sma50=100, sma200=100, rs_vs_spy_30d=0.02, bollinger_position=0.5)
    assert _dim_trend(f) == pytest.approx(0.25)


def test_dim_trend_none():
    f = _make_features()
    assert _dim_trend(f) == 0.0


# ---------- _dim_volume ----------
def test_dim_volume_high():
    f = _make_features(volume_ratio_20d=3.5)
    assert _dim_volume(f) == 1.0


def test_dim_volume_med():
    f = _make_features(volume_ratio_20d=1.2)
    assert _dim_volume(f) == 0.5


def test_dim_volume_low():
    f = _make_features(volume_ratio_20d=0.3)
    assert _dim_volume(f) == 0.1


def test_dim_volume_none():
    f = _make_features()
    assert _dim_volume(f) == 0.0


# ---------- _dim_volatility ----------
def test_dim_volatility_high():
    # ATR=5.0 is very high — SL noise risk is severe → 0.2
    f = _make_features(atr_pct=5.0)
    assert _dim_volatility(f) == 0.2


def test_dim_volatility_med():
    # ATR=1.2 is in optimal zone [1.0, 2.5] → 1.0
    f = _make_features(atr_pct=1.2)
    assert _dim_volatility(f) == 1.0


def test_dim_volatility_low():
    # ATR=0.3 is below 0.5 (very low movement expected) → 0.3
    f = _make_features(atr_pct=0.3)
    assert _dim_volatility(f) == 0.3


def test_dim_volatility_none():
    f = _make_features()
    assert _dim_volatility(f) == 0.0


def test_dim_volatility_optimal():
    # ATR=2.0 is in optimal zone [1.0, 2.5] → 1.0
    f = _make_features(atr_pct=2.0)
    assert _dim_volatility(f) == 1.0


def test_dim_volatility_high_zone():
    # ATR=3.0 is in high zone (2.5, 4.0] → 0.5
    f = _make_features(atr_pct=3.0)
    assert _dim_volatility(f) == 0.5


# ---------- _dim_portfolio_fit ----------
def test_dim_portfolio_fit_empty():
    assert _dim_portfolio_fit([], capital=500.0) == 1.0


def test_dim_portfolio_fit_one():
    assert _dim_portfolio_fit(["AAPL"]) == 0.7


def test_dim_portfolio_fit_two():
    assert _dim_portfolio_fit(["AAPL", "TSLA"]) == 0.4


def test_dim_portfolio_fit_three():
    assert _dim_portfolio_fit(["A", "B", "C"]) == 0.0


# ---------- _dim_sentiment ----------
def test_dim_sentiment_positive():
    news = [{"sentiment": "positive"}, {"sentiment": "positive"}, {"sentiment": "negative"}]
    assert _dim_sentiment(news) == pytest.approx(0.6 + 0.4 * (2/3))


def test_dim_sentiment_negative():
    news = [{"sentiment": "negative"}, {"sentiment": "negative"}]
    assert _dim_sentiment(news) == pytest.approx(max(0.0, 0.4 - 0.4 * 1.0))


def test_dim_sentiment_neutral():
    news = [{"sentiment": "positive"}, {"sentiment": "negative"}]
    assert _dim_sentiment(news) == 0.5


def test_dim_sentiment_empty():
    assert _dim_sentiment([]) == 0.0


# ---------- _dim_price_change ----------
def test_dim_price_change_high():
    # pc=6.0 → strong momentum, watch overbought
    f = _make_features(price_change_pct=6.0)
    assert _dim_price_change(f) == 0.7


def test_dim_price_change_med():
    # pc=1.5 → positive moderate momentum — ideal BUY
    f = _make_features(price_change_pct=1.5)
    assert _dim_price_change(f) == 0.9


def test_dim_price_change_low():
    # pc=0.3 → neutral-positive
    f = _make_features(price_change_pct=0.3)
    assert _dim_price_change(f) == 0.6


def test_dim_price_change_none():
    f = _make_features()
    assert _dim_price_change(f) == 0.0


def test_dim_price_change_moderate_drop():
    # pc=-2.0 → moderate drop, caution
    f = _make_features(price_change_pct=-2.0)
    assert _dim_price_change(f) == 0.2


def test_dim_price_change_collapse():
    # pc=-5.0 → collapse / bear trap
    f = _make_features(price_change_pct=-5.0)
    assert _dim_price_change(f) == 0.1


def test_dim_price_change_ideal_buy():
    # AC-03.1: pc=2.0 → ideal BUY momentum
    f = _make_features(price_change_pct=2.0)
    assert _dim_price_change(f) == 0.9


# ---------- _get_multipliers ----------
@patch("app.db.database.get_or_create_symbol_parameters")
def test_get_multipliers_from_db(mock_params):
    mock_params.return_value = MagicMock(
        momentum_mult=1.2, trend_mult=0.9, volume_mult=1.0,
        volatility_mult=1.1, portfolio_fit_mult=0.8, sentiment_mult=1.0
    )
    m = _get_multipliers("AAPL")
    assert m["momentum"] == 1.2
    assert m["portfolio_fit"] == 0.8


@patch("app.db.database.get_or_create_symbol_parameters")
def test_get_multipliers_fallback(mock_params):
    mock_params.side_effect = Exception("db error")
    m = _get_multipliers("AAPL")
    assert all(v == 1.0 for v in m.values())


# ---------- compute_score ----------
@patch("app.analysis.scorer._get_multipliers")
def test_compute_score_rejected(mock_mult):
    mock_mult.return_value = {k: 1.0 for k in GLOBAL_WEIGHTS}
    f = _make_features(rsi_14=50, macd_crossover=False, sma50=100, sma200=100,
                       volume_ratio_20d=0.5, atr_pct=0.3, price_change_pct=0.1)
    qs = compute_score(f, "AAPL", [])
    assert qs.total < THRESHOLDS["rejected"] + 1
    assert qs.recommendation in ("REJECTED", "WATCHLIST")


@patch("app.analysis.scorer._get_multipliers")
def test_compute_score_priority(mock_mult):
    mock_mult.return_value = {k: 1.0 for k in GLOBAL_WEIGHTS}
    # atr_pct=2.0 (optimal zone) + price_change_pct=3.0 (ideal BUY) → PRIORITY
    f = _make_features(rsi_14=20, macd_crossover=True, sma50=110, sma200=100,
                       volume_ratio_20d=4.0, atr_pct=2.0, price_change_pct=3.0,
                       rs_vs_spy_30d=0.08, bollinger_position=0.8)
    qs = compute_score(f, "AAPL", [])
    assert qs.total >= THRESHOLDS["propose"]
    assert qs.recommendation == "PRIORITY"


@patch("app.analysis.scorer._get_multipliers")
def test_compute_score_watchlist(mock_mult):
    mock_mult.return_value = {k: 1.0 for k in GLOBAL_WEIGHTS}
    f = _make_features(rsi_14=35, macd_crossover=False, sma50=101, sma200=100,
                       volume_ratio_20d=1.2, atr_pct=1.0, price_change_pct=1.0,
                       rs_vs_spy_30d=0.02, bollinger_position=0.5)
    qs = compute_score(f, "AAPL", [])
    assert THRESHOLDS["rejected"] < qs.total <= THRESHOLDS["watchlist"] + 5


@patch("app.analysis.scorer._get_multipliers")
def test_compute_score_to_dict(mock_mult):
    mock_mult.return_value = {k: 1.0 for k in GLOBAL_WEIGHTS}
    f = _make_features(rsi_14=50, volume_ratio_20d=1.0, atr_pct=1.0, price_change_pct=1.0)
    qs = compute_score(f, "AAPL", [])
    d = qs.to_dict()
    assert "symbol" in d
    assert "total" in d


# ---------- update_weights_attenuated ----------
@patch("app.db.database.get_or_create_symbol_parameters")
@patch("app.db.database.update_symbol_parameters")
def test_update_weights_attenuated_low_trade_count(mock_update, mock_get):
    mock_get.return_value = MagicMock(trade_count=2)
    assert update_weights_attenuated("AAPL", "momentum", 1.2, 0.8) is False


@patch("app.db.database.get_or_create_symbol_parameters")
@patch("app.db.database.update_symbol_parameters")
def test_update_weights_attenuated_success(mock_update, mock_get):
    mock_get.return_value = MagicMock(trade_count=10, momentum_mult=1.0)
    assert update_weights_attenuated("AAPL", "momentum", 1.2, 0.8) is True
    mock_update.assert_called_once()


@patch("app.db.database.get_or_create_symbol_parameters")
@patch("app.db.database.update_symbol_parameters")
def test_update_weights_attenuated_bounds(mock_update, mock_get):
    mock_get.return_value = MagicMock(trade_count=10, momentum_mult=1.4)
    update_weights_attenuated("AAPL", "momentum", 2.0, 1.0)
    args = mock_update.call_args
    assert args[1]["momentum_mult"] == pytest.approx(1.49)


@patch("app.db.database.get_or_create_symbol_parameters")
def test_update_weights_attenuated_exception(mock_get):
    mock_get.side_effect = Exception("db fail")
    assert update_weights_attenuated("AAPL", "momentum", 1.2, 0.8) is False
