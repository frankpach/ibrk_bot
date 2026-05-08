# tests/test_multitimeframe.py
from app.scanner.preprocessor import classify_signal, classify_multitimeframe


def test_classify_single_strong():
    assert classify_signal(rsi=28.0, macd_crossover=True, volume_ratio=1.6) == "STRONG"


def test_classify_single_weak():
    assert classify_signal(rsi=50.0, macd_crossover=False, volume_ratio=1.0) == "WEAK"


def test_multitimeframe_strong_when_all_confirm():
    result = classify_multitimeframe("STRONG", "STRONG", "MEDIUM")
    assert result == "STRONG"


def test_multitimeframe_medium_when_two_confirm():
    result = classify_multitimeframe("STRONG", "MEDIUM", "WEAK")
    assert result == "MEDIUM"


def test_multitimeframe_weak_when_only_one():
    result = classify_multitimeframe("STRONG", "WEAK", "WEAK")
    assert result == "WEAK"


def test_multitimeframe_weak_when_all_weak():
    result = classify_multitimeframe("WEAK", "WEAK", "WEAK")
    assert result == "WEAK"


def test_multitimeframe_strong_requires_daily_confirmation():
    result = classify_multitimeframe("WEAK", "STRONG", "STRONG")
    assert result == "MEDIUM"
