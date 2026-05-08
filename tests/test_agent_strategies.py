# tests/test_agent_strategies.py
from app.llm.agent import get_symbol_category, get_strategy_context


def test_etf_category():
    assert get_symbol_category("SPY") == "etf"
    assert get_symbol_category("QQQ") == "etf"


def test_blue_chip_category():
    assert get_symbol_category("AAPL") == "blue_chip"
    assert get_symbol_category("MSFT") == "blue_chip"
    assert get_symbol_category("JPM") == "blue_chip"
    assert get_symbol_category("GOOGL") == "blue_chip"
    assert get_symbol_category("META") == "blue_chip"


def test_growth_category():
    assert get_symbol_category("TSLA") == "growth"
    assert get_symbol_category("NVDA") == "growth"


def test_unknown_defaults_to_blue_chip():
    assert get_symbol_category("FAKE") == "blue_chip"
    assert get_symbol_category("NFLX") == "blue_chip"


def test_etf_context_mentions_conservative():
    ctx = get_strategy_context("etf")
    assert "conservador" in ctx.lower() or "macro" in ctx.lower()


def test_growth_context_mentions_volatility():
    ctx = get_strategy_context("growth")
    assert "volatil" in ctx.lower() or "agresiv" in ctx.lower()


def test_blue_chip_context_is_moderate():
    ctx = get_strategy_context("blue_chip")
    assert "moderado" in ctx.lower() or "fundamental" in ctx.lower()


def test_all_categories_have_context():
    for cat in ("etf", "blue_chip", "growth"):
        ctx = get_strategy_context(cat)
        assert len(ctx) > 20
