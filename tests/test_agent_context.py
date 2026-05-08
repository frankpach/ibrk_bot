# tests/test_agent_context.py
"""Verifica que el prompt al LLM contiene todos los indicadores necesarios."""
from app.llm.agent import build_llm_prompt
from app.analysis.indicators import FeatureSet
from datetime import datetime


def _make_features():
    return FeatureSet(
        symbol="AAPL", timestamp=datetime(2026, 1, 1),
        rsi_14=27.5, macd_line=-0.18, macd_signal=-0.10,
        macd_crossover=True, atr_pct=1.8,
        sma20=285.0, sma50=290.0, sma200=270.0,
        bollinger_position=0.05, volume_ratio_20d=2.1,
        hist_volatility_30d=25.0,
    )


def test_prompt_contains_rsi():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "27.5" in prompt


def test_prompt_contains_macd():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "macd" in prompt.lower() or "MACD" in prompt


def test_prompt_contains_capital():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "500" in prompt


def test_prompt_contains_price():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "287.75" in prompt


def test_prompt_contains_score():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "72" in prompt


def test_prompt_contains_bollinger():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "bollinger" in prompt.lower() or "0.05" in prompt


def test_prompt_with_patterns_includes_them():
    patterns = ["AAPL BUY WIN — RSI oversold + volume spike → TAKE_PROFIT in 2 days"]
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=patterns)
    assert "WIN" in prompt or "oversold" in prompt
