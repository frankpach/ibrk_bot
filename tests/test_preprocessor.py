# tests/test_preprocessor.py
from app.scanner.preprocessor import classify_signal


def test_strong_all_three():
    assert classify_signal(rsi=28.0, macd_crossover=True, volume_ratio=1.6) == "STRONG"


def test_strong_overbought():
    assert classify_signal(rsi=72.0, macd_crossover=True, volume_ratio=1.6) == "STRONG"


def test_medium_two_of_three():
    assert classify_signal(rsi=28.0, macd_crossover=True, volume_ratio=1.0) == "MEDIUM"


def test_medium_rsi_and_volume():
    assert classify_signal(rsi=72.0, macd_crossover=False, volume_ratio=1.6) == "MEDIUM"


def test_weak_one_condition():
    assert classify_signal(rsi=28.0, macd_crossover=False, volume_ratio=1.0) == "WEAK"


def test_none_no_conditions():
    assert classify_signal(rsi=50.0, macd_crossover=False, volume_ratio=1.0) == "NONE"
