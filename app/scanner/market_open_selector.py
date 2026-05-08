"""
Pre-open symbol selector.

15 minutes before each market session, select_top_symbols() is called by the
APScheduler cron job. It:
  1. Fetches candidate symbols (IB Scanner for STK_US, seed list otherwise).
  2. Scores each candidate with simple_score() (or QuantScorer if available).
  3. Always includes open positions regardless of score.
  4. Saves top-N to the active_symbols DB table.
  5. Returns the selected symbol list for logging.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from app.db.database import upsert_active_symbols

if TYPE_CHECKING:
    from app.ibkr.client import IBKRClient

logger = logging.getLogger(__name__)

IB_SCANNER_MARKETS = {"STK_US"}


def _get_scorer():
    """Return QuantScorer if available, else None (use simple_score)."""
    try:
        from app.analysis.scorer import QuantScorer
        return QuantScorer()
    except (ImportError, Exception):
        return None


def simple_score(rsi, volume_ratio):
    """Score a symbol using RSI extremeness and volume ratio.

    Returns score in [0, 100]. Higher = more tradeable.
    """
    rsi_score = abs((rsi or 50) - 50) / 50
    vol_score = min((volume_ratio or 1.0) / 3.0, 1.0)
    return (rsi_score * 0.6 + vol_score * 0.4) * 100


def _score_symbol(scorer, symbol, indicators):
    rsi = indicators.get("rsi")
    volume_ratio = indicators.get("volume_ratio")
    if scorer is not None:
        try:
            return scorer.score(symbol, rsi=rsi, volume_ratio=volume_ratio)
        except Exception as exc:
            logger.warning("QuantScorer failed for %s: %s", symbol, exc)
    return simple_score(rsi, volume_ratio)


def _get_candidates(market_key, ib_client):
    if market_key in IB_SCANNER_MARKETS:
        from app.ibkr.ib_scanner import get_stk_us_candidates
        results = get_stk_us_candidates(ib_client)
        if results:
            return [r["symbol"] for r in results]
        logger.warning(
            "IB Scanner returned no results for %s, falling back to seed list",
            market_key,
        )

    from app.db.database import get_approved_symbols_with_meta
    meta = get_approved_symbols_with_meta()
    return [m["symbol"] for m in meta if m.get("market_key") == market_key]


def _get_open_position_symbols(ib_client):
    try:
        positions = ib_client.ib.positions()
        return {pos.contract.symbol for pos in positions if pos.position != 0}
    except Exception as exc:
        logger.warning("Could not fetch open positions: %s", exc)
        return set()


def select_top_symbols(
    market_key,
    ib_client,
    ib_data_layer,
    session_date=None,
    n=10,
):
    """Select the top N symbols for a market session and persist them.

    Open positions are always included regardless of score.
    """
    today = session_date or date.today().isoformat()
    scorer = _get_scorer()

    # Load full metadata so get_indicators can use the right sec_type/exchange/currency
    from app.db.database import get_approved_symbols_with_meta
    all_meta = {m["symbol"]: m for m in get_approved_symbols_with_meta()}

    candidates = _get_candidates(market_key, ib_client)
    logger.info("Pre-open %s: %d raw candidates", market_key, len(candidates))

    scores = {}
    for symbol in candidates:
        try:
            meta = all_meta.get(symbol, {})
            indicators = ib_data_layer.get_indicators(
                symbol,
                sec_type=meta.get("sec_type", "STK"),
                exchange=meta.get("exchange", "SMART"),
                currency=meta.get("currency", "USD"),
            )
        except Exception as exc:
            logger.warning("Could not fetch indicators for %s: %s", symbol, exc)
            indicators = {}
        scores[symbol] = _score_symbol(scorer, symbol, indicators)

    ranked = sorted(scores, key=lambda s: scores[s], reverse=True)
    top_n = ranked[:n]

    open_positions = _get_open_position_symbols(ib_client)
    forced = [sym for sym in open_positions if sym not in set(top_n)]
    selected = forced + top_n

    all_scores = {sym: scores.get(sym, 0.0) for sym in selected}
    upsert_active_symbols(market_key, selected, today, scores=all_scores)

    logger.info("Pre-open %s: selected %s", market_key, selected)
    return selected
