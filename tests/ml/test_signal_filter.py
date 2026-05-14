# tests/ml/test_signal_filter.py
import pickle
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from app.ml.signal_filter import SignalFilter, get_signal_filter, FilterFeatures


# ---------- SignalFilter initialization ----------
def test_init_no_model():
    sf = SignalFilter(model_path="/nonexistent/path.pkl")
    assert sf._model is None
    assert sf._scaler is None


def test_init_loads_model(tmp_path):
    path = tmp_path / "model.pkl"
    # Use a real LogisticRegression if sklearn is available, else skip
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        model = LogisticRegression()
        scaler = StandardScaler()
        with open(path, "wb") as f:
            pickle.dump({"model": model, "scaler": scaler}, f)
        sf = SignalFilter(model_path=str(path))
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        assert isinstance(sf._model, LogisticRegression)
        assert isinstance(sf._scaler, StandardScaler)
    except ImportError:
        pytest.skip("sklearn not available")


def test_init_load_failure(tmp_path):
    path = tmp_path / "bad.pkl"
    path.write_text("not pickle")
    sf = SignalFilter(model_path=str(path))
    assert sf._model is None


# ---------- _extract_features ----------
def test_extract_features_from_object():
    sf = SignalFilter(model_path="/nonexistent")
    f = MagicMock()
    f.rsi_14 = 30
    f.macd_line = 1.5
    f.atr_pct = 2.5
    f.volume_ratio_20d = 1.2
    f.bollinger_position = 0.6
    f.rs_vs_spy_30d = 0.03
    f.day_of_week = 2
    f.hour = 14
    f.rsi_1h = 55.0
    f.volume_ratio_1h = 1.3
    result = sf._extract_features(f)
    # 12 features: rsi, macd, atr, vol_ratio, boll, rs_spy, dow, hour,
    #              rsi_1h, vol_1h, vol_regime, vwap_dev
    assert len(result) == 12
    assert result[:10] == [30, 1.5, 2.5, 1.2, 0.6, 0.03, 2, 14, 55.0, 1.3]
    assert result[10] == 1   # vol_regime: atr=2.5 → moderate (1)
    assert abs(result[11] - 0.2) < 0.01  # vwap_dev: (0.6-0.5)*2 = 0.2


def test_extract_features_defaults():
    sf = SignalFilter(model_path="/nonexistent")
    f = MagicMock(spec=[])  # Missing attributes should use defaults
    result = sf._extract_features(f)
    assert len(result) == 12
    assert result[:10] == [50, 0, 2.0, 1.0, 0.5, 0, 0, 10, 50, 1.0]


# ---------- predict / should_ignore ----------
def test_predict_heuristic_rsi_extreme():
    sf = SignalFilter(model_path="/nonexistent")
    f = MagicMock()
    f.rsi_14 = 20
    f.volume_ratio_20d = 1.0
    f.atr_pct = 2.0
    f.rs_vs_spy_30d = 0.0
    p = sf.predict(f)
    assert p == pytest.approx(0.6)
    assert sf.should_ignore(f) is False


def test_predict_heuristic_high_atr():
    sf = SignalFilter(model_path="/nonexistent")
    f = MagicMock()
    f.rsi_14 = 50
    f.volume_ratio_20d = 1.0
    f.atr_pct = 5.0
    f.rs_vs_spy_30d = 0.0
    p = sf.predict(f)
    assert p == pytest.approx(0.4)
    assert sf.should_ignore(f) is True


def test_predict_heuristic_low_volume():
    sf = SignalFilter(model_path="/nonexistent")
    f = MagicMock()
    f.rsi_14 = 50
    f.volume_ratio_20d = 0.5
    f.atr_pct = 2.0
    f.rs_vs_spy_30d = 0.0
    p = sf.predict(f)
    assert p == pytest.approx(0.5)


def test_predict_heuristic_positive_rs():
    sf = SignalFilter(model_path="/nonexistent")
    f = MagicMock()
    f.rsi_14 = 50
    f.volume_ratio_20d = 1.0
    f.atr_pct = 2.0
    f.rs_vs_spy_30d = 0.03
    p = sf.predict(f)
    assert p == pytest.approx(0.55)


def test_predict_with_model(tmp_path):
    try:
        from sklearn.linear_model import LogisticRegression
        path = tmp_path / "model.pkl"
        model = LogisticRegression()
        with open(path, "wb") as f:
            pickle.dump({"model": model, "scaler": None}, f)
        sf = SignalFilter(model_path=str(path))
        f = MagicMock()
        f.rsi_14 = 50
        f.volume_ratio_20d = 1.0
        f.atr_pct = 2.0
        f.rs_vs_spy_30d = 0.0
        p = sf.predict(f)
        assert 0.0 <= p <= 1.0
    except ImportError:
        pytest.skip("sklearn not available")


def test_predict_model_exception_fallback():
    sf = SignalFilter(model_path="/nonexistent")
    sf._model = MagicMock()
    sf._model.predict_proba.side_effect = Exception("fail")
    f = MagicMock()
    f.rsi_14 = 50
    f.volume_ratio_20d = 1.0
    f.atr_pct = 2.0
    f.rs_vs_spy_30d = 0.0
    p = sf.predict(f)
    assert 0.0 <= p <= 1.0


# ---------- retrain ----------
def test_retrain_insufficient_data():
    sf = SignalFilter(model_path="/nonexistent")
    trades = [MagicMock() for _ in range(3)]
    assert sf.retrain(trades) is False


def test_retrain_no_sklearn():
    sf = SignalFilter(model_path="/nonexistent")
    trades = [MagicMock(features=MagicMock(), pnl_pct=0.01) for _ in range(15)]
    with patch.dict("sys.modules", {"sklearn": None, "sklearn.linear_model": None,
                                    "sklearn.preprocessing": None, "sklearn.model_selection": None}):
        assert sf.retrain(trades) is False


def test_retrain_success(tmp_path):
    try:
        import sklearn
    except ImportError:
        pytest.skip("sklearn not available")
    # Use dict format (from get_closed_trades_with_snapshots)
    trades = []
    for i in range(15):
        trades.append({
            "pnl_pct": 0.01 if i % 2 == 0 else -0.01,
            "rsi_14": 50 + i, "macd_line": 0, "atr_pct": 2.0,
            "volume_ratio_20d": 1.0, "bollinger_position": 0.5,
            "rs_vs_spy_30d": 0.0, "day_of_week": 0, "hour": 10,
        })
    path = tmp_path / "model.pkl"
    sf = SignalFilter(model_path=str(path))
    result = sf.retrain(trades)
    assert isinstance(result, float)  # returns AUC now
    assert path.exists()


def test_retrain_skips_missing_snapshot_id():
    """Trade objects without feature_snapshot_id are silently skipped."""
    sf = SignalFilter(model_path="/nonexistent")
    trades = []
    for i in range(15):
        t = MagicMock(spec=[])  # no attributes at all → no feature_snapshot_id
        trades.append(t)
    # All skipped → insufficient data → False
    result = sf.retrain(trades)
    assert result is False


def test_retrain_all_same_class(tmp_path):
    """When all wins or all losses, CV fails gracefully → returns 0.5 AUC."""
    try:
        import sklearn
    except ImportError:
        pytest.skip("sklearn not available")
    trades = []
    for i in range(15):
        trades.append({
            "pnl_pct": 0.01,  # all wins → single class
            "rsi_14": 50 + i, "macd_line": 0, "atr_pct": 2.0,
            "volume_ratio_20d": 1.0, "bollinger_position": 0.5,
            "rs_vs_spy_30d": 0.0, "day_of_week": 0, "hour": 10,
        })
    path = tmp_path / "model_same_class.pkl"
    sf = SignalFilter(model_path=str(path))
    result = sf.retrain(trades)
    # CV fails on single class → AUC falls back to 0.5; final fit also fails → returns 0.5 float
    assert isinstance(result, float)
    assert result == pytest.approx(0.5)


# ---------- singleton ----------
def test_get_signal_filter_singleton():
    import app.ml.signal_filter as sf_mod
    old = sf_mod._filter_instance
    sf_mod._filter_instance = None
    f1 = get_signal_filter()
    f2 = get_signal_filter()
    assert f1 is f2
    sf_mod._filter_instance = old


# ---------- FilterFeatures dataclass ----------
def test_filter_features():
    ff = FilterFeatures(rsi=50, macd=0, atr_pct=2.0, volume_ratio=1.0,
                        bollinger_position=0.5, rs_vs_spy=0.0, day_of_week=1, hour=10)
    assert ff.rsi == 50
    assert ff.hour == 10
