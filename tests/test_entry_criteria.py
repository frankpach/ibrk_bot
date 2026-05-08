# tests/test_entry_criteria.py
"""Tests para criterios de entrada de 4 condiciones."""
from app.analysis.indicators import classify_signal_v2, FeatureSet
from datetime import datetime


def _features(**kwargs):
    defaults = dict(
        symbol="AAPL", timestamp=datetime(2026, 1, 1),
        rsi_14=50.0, macd_crossover=False, volume_ratio_20d=1.0,
        bollinger_position=0.5, sma20=100.0,
    )
    defaults.update(kwargs)
    return FeatureSet(**defaults)


def test_strong_requires_all_4_conditions():
    f = _features(rsi_14=27.0, macd_crossover=True, volume_ratio_20d=2.0, bollinger_position=0.05)
    assert classify_signal_v2(f) == "STRONG"


def test_missing_rsi_condition_downgrades_to_medium():
    f = _features(rsi_14=40.0, macd_crossover=True, volume_ratio_20d=2.0, bollinger_position=0.05)
    assert classify_signal_v2(f) == "MEDIUM"


def test_missing_macd_downgrades():
    f = _features(rsi_14=27.0, macd_crossover=False, volume_ratio_20d=2.0, bollinger_position=0.05)
    assert classify_signal_v2(f) == "MEDIUM"


def test_missing_volume_downgrades():
    f = _features(rsi_14=27.0, macd_crossover=True, volume_ratio_20d=0.8, bollinger_position=0.05)
    assert classify_signal_v2(f) == "MEDIUM"


def test_overbought_also_triggers_strong():
    f = _features(rsi_14=72.0, macd_crossover=True, volume_ratio_20d=2.0, bollinger_position=0.92)
    assert classify_signal_v2(f) == "STRONG"


def test_weak_when_fewer_than_2_conditions():
    f = _features(rsi_14=50.0, macd_crossover=False, volume_ratio_20d=0.5, bollinger_position=0.5)
    assert classify_signal_v2(f) == "WEAK"


def test_none_fields_handled_gracefully():
    f = _features(rsi_14=None, macd_crossover=None, volume_ratio_20d=None, bollinger_position=None)
    result = classify_signal_v2(f)
    assert result in ("STRONG", "MEDIUM", "WEAK")
