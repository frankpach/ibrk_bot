"""Tests for app/ml/postmortem_stats.py"""
import pytest
from unittest.mock import MagicMock, patch

_DB = "app.infrastructure.db.compat"


def _make_trade(pnl_pct, exit_reason="STOP_LOSS"):
    t = MagicMock()
    t.pnl_pct = pnl_pct
    t.exit_reason = exit_reason
    return t


def test_returns_none_with_fewer_than_3_trades():
    from app.ml.postmortem_stats import enrich_postmortem_context
    with patch(f"{_DB}.get_closed_trades_by_symbol", return_value=[]):
        result = enrich_postmortem_context("AAPL")
    assert result is None


def test_returns_none_with_2_trades():
    from app.ml.postmortem_stats import enrich_postmortem_context
    trades = [_make_trade(0.01), _make_trade(-0.01)]
    with patch(f"{_DB}.get_closed_trades_by_symbol", return_value=trades):
        result = enrich_postmortem_context("AAPL")
    assert result is None


def test_returns_context_with_enough_trades():
    from app.ml.postmortem_stats import enrich_postmortem_context, PostmortemContext
    trades = [
        _make_trade(0.05, "TAKE_PROFIT"),
        _make_trade(-0.02, "STOP_LOSS"),
        _make_trade(0.03, "TAKE_PROFIT"),
        _make_trade(-0.01, "STOP_LOSS"),
        _make_trade(0.04, "TAKE_PROFIT"),
    ]
    with patch(f"{_DB}.get_closed_trades_by_symbol", return_value=trades), \
         patch(f"{_DB}.get_patterns_for_symbol", return_value=[]):
        result = enrich_postmortem_context("AAPL")
    assert isinstance(result, PostmortemContext)
    assert result.win_rate_last_10 == pytest.approx(3/5)
    assert result.sl_hit_rate == pytest.approx(2/5)
    assert result.tp_hit_rate == pytest.approx(3/5)
    assert result.most_common_exit == "TAKE_PROFIT"


def test_to_prompt_str_contains_key_info():
    from app.ml.postmortem_stats import PostmortemContext
    ctx = PostmortemContext(
        win_rate_last_10=0.6, avg_pnl_wins_pct=0.04,
        avg_pnl_losses_pct=-0.02, sl_hit_rate=0.3,
        tp_hit_rate=0.5, most_common_exit="TAKE_PROFIT",
        patterns_last_3=["Pattern A", "Pattern B"],
    )
    s = ctx.to_prompt_str()
    assert "60%" in s
    assert "TAKE_PROFIT" in s
    assert "Pattern A" in s


def test_patterns_included_in_context():
    from app.ml.postmortem_stats import enrich_postmortem_context
    trades = [_make_trade(0.01) for _ in range(5)]
    pattern = MagicMock()
    pattern.pattern_text = "RSI oversold + high volume = reliable entry"
    with patch(f"{_DB}.get_closed_trades_by_symbol", return_value=trades), \
         patch(f"{_DB}.get_patterns_for_symbol", return_value=[pattern]):
        result = enrich_postmortem_context("AAPL")
    assert len(result.patterns_last_3) == 1
    assert "RSI oversold" in result.patterns_last_3[0]


def test_graceful_on_db_error():
    from app.ml.postmortem_stats import enrich_postmortem_context
    with patch(f"{_DB}.get_closed_trades_by_symbol",
               side_effect=Exception("DB error")):
        result = enrich_postmortem_context("AAPL")
    assert result is None
