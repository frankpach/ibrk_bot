# app/analysis/admission.py
"""Daily discovery and universe rotation using AnalysisPipeline."""
import logging
from datetime import datetime
from app.config.settings import MARKET_TZ
from app.notifications.telegram import notify
from app.analysis.pipeline import AnalysisPipeline, AnalysisContext

logger = logging.getLogger(__name__)
PROTECTED_SYMBOLS = {"SPY", "QQQ"}


def run_daily_discovery(data_layer):
    """Run IB Scanner, evaluate candidates, rotate universe if needed."""
    now = datetime.now(tz=MARKET_TZ)
    if now.weekday() >= 5:
        logger.debug("Weekend — skipping daily discovery")
        return

    logger.info("Starting daily discovery scan...")

    # Collect candidates from multiple scanners
    candidates = set()
    for scan_code in ("HOT_BY_VOLUME", "TOP_PERC_GAIN", "MOST_ACTIVE"):
        try:
            results = data_layer.run_scanner(scan_code, max_results=20)
            candidates.update(results)
        except Exception as e:
            logger.error(f"Scanner {scan_code} failed: {e}")

    # Filter: exclude already active symbols
    from app.infrastructure.db.compat import get_approved_symbols
    active = set(get_approved_symbols())
    new_candidates = [s for s in candidates if s not in active][:20]

    if not new_candidates:
        logger.info("No new candidates found today")
        return

    logger.info(f"Evaluating {len(new_candidates)} candidates: {new_candidates}")

    # Evaluate each candidate
    context = AnalysisContext(mode="daily_discovery")
    from app.container import get_container
    _c = get_container()
    scored = []
    for symbol in new_candidates:
        try:
            pipeline = AnalysisPipeline(symbol, data_layer, context, notify_fn=None,
                                        broker=_c.broker, event_bus=_c.event_bus)
            result = pipeline.run()
            if result.score:
                scored.append((symbol, result.score.total))
                logger.info(f"  {symbol}: score={result.score.total:.1f} [{result.recommendation}]")
        except Exception as e:
            logger.error(f"Evaluation failed for {symbol}: {e}")

    # Universe rotation
    if scored:
        _rotate_universe(scored)


def _rotate_universe(scored_candidates: list):
    """Rotate universe if a candidate scores higher than the weakest current member."""
    from app.infrastructure.db.compat import get_approved_symbols, get_connection

    # Get current watchlist scores
    conn = get_connection()
    rows = conn.execute("SELECT symbol, watchlist_score FROM watchlist_scores").fetchall()
    conn.close()
    current_scores = {r["symbol"]: r["watchlist_score"] for r in rows}

    best_candidate = max(scored_candidates, key=lambda x: x[1])
    sym, score = best_candidate

    if score < 75:
        return  # Not strong enough

    # Find weakest in current universe (excluding protected)
    active_symbols = get_approved_symbols()
    unprotected = [(s, current_scores.get(s, 0.5)) for s in active_symbols if s not in PROTECTED_SYMBOLS]
    if not unprotected:
        return

    weakest_sym, weakest_score = min(unprotected, key=lambda x: x[1])

    if weakest_score < 0.40:
        # Rotate
        notify(
            f"🔄 Universe rotation:\n"
            f"  <b>{sym}</b> enters (score: {score:.0f})\n"
            f"  <b>{weakest_sym}</b> exits (watchlist: {weakest_score:.2f})\n"
        )
        logger.info(f"Universe rotation: {sym} IN, {weakest_sym} OUT")

        # Update DB
        from app.infrastructure.db.compat import approve_symbol
        from app.infrastructure.db.compat import get_connection as gc
        conn = gc()
        conn.execute("UPDATE symbol_config SET approved=0 WHERE symbol=?", (weakest_sym,))
        conn.commit()
        conn.close()
        approve_symbol(sym)
