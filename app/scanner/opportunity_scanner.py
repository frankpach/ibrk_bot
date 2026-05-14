"""Proactive hourly opportunity scanner — scores top movers and alerts on strong candidates."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

MIN_SCORE_THRESHOLD = 55.0
MIN_CHANGE_PCT = 1.5       # minimum % move to be interesting
MIN_VOLUME_RATIO = 1.3     # minimum volume surge
MAX_ATR_PCT = 8.0          # skip extremely volatile stocks (too risky)


def run_opportunity_scan(data_layer, ib_client=None) -> list:
    """
    Score top movers from scanner_results and update daily_watchlist.
    Returns list of NEW high-scoring opportunities (not previously alerted).
    """
    from app.db.database import (
        get_scanner_results, get_approved_symbols, upsert_daily_watchlist,
        mark_watchlist_alerted,
    )
    from app.config.settings import MARKET_TZ

    today = datetime.now(MARKET_TZ).strftime("%Y-%m-%d")
    approved = set(get_approved_symbols())

    # Get symbols from top movers + most active
    candidates = []
    for scan_type in ("top_movers", "most_active", "gainers"):
        for row in get_scanner_results(scan_type):
            sym = row.get("symbol", "")
            if sym and sym not in [c["symbol"] for c in candidates]:
                candidates.append({
                    "symbol": sym,
                    "change_pct": row.get("change_pct") or 0.0,
                    "volume_ratio": row.get("volume_ratio") or 0.0,
                    "scan_type": scan_type,
                })

    if not candidates:
        logger.debug("No scanner candidates found for opportunity scan")
        return []

    new_opportunities = []

    for cand in candidates[:20]:  # limit to avoid rate limit
        sym = cand["symbol"]
        change_pct = abs(cand.get("change_pct") or 0.0)
        vol_ratio = cand.get("volume_ratio") or 0.0

        # Quick pre-filter: skip if not interesting enough
        if change_pct < MIN_CHANGE_PCT and vol_ratio < MIN_VOLUME_RATIO:
            continue

        try:
            # Fetch OHLCV for scoring
            df = data_layer.get_ohlcv(sym, "5 D", "1 day", "scanner")
            if df is None or len(df) < 15:
                continue

            # Compute features
            from app.analysis.indicators import compute_features, classify_signal, compute_from_df
            ind = compute_from_df(df)
            if not ind:
                continue

            signal = classify_signal(ind.get("rsi"), ind.get("macd_crossover"), ind.get("volume_ratio"))

            # Get ATR to filter out crazy volatile stocks
            from app.analysis.indicators import _compute_atr
            atr = _compute_atr(df)
            if atr and atr > MAX_ATR_PCT:
                logger.debug(f"Skipping {sym}: ATR {atr:.1f}% too high")
                continue

            # Compute QuantScore
            from app.analysis.scorer import compute_score
            features = compute_features(sym, df)
            score_result = compute_score(features, sym, [])
            score = score_result.total

            if score < MIN_SCORE_THRESHOLD:
                continue

            reason = f"{cand['scan_type'].replace('_',' ')}: {cand['change_pct']:+.1f}% | signal={signal} | score={score:.0f}"

            is_new = upsert_daily_watchlist(
                date=today,
                symbol=sym,
                score=score,
                signal_strength=signal,
                change_pct=cand.get("change_pct") or 0.0,
                volume_ratio=vol_ratio,
                reason=reason,
            )

            if is_new and signal in ("STRONG", "MEDIUM"):
                new_opportunities.append({
                    "symbol": sym,
                    "score": score,
                    "signal": signal,
                    "change_pct": cand.get("change_pct") or 0.0,
                    "volume_ratio": vol_ratio,
                    "in_approved": sym in approved,
                    "reason": reason,
                })

        except Exception as e:
            logger.debug(f"Opportunity scan skipped {sym}: {e}")

    return new_opportunities


def notify_opportunities(opportunities: list, base_url: str = "http://localhost:8088") -> None:
    """Send Telegram alert for new high-scoring opportunities."""
    if not opportunities:
        return

    from app.notifications.telegram import notify

    lines = ["🎯 <b>Nuevas oportunidades detectadas</b>", ""]
    for opp in opportunities[:5]:
        sym = opp["symbol"]
        score = opp["score"]
        signal = opp["signal"]
        change = opp["change_pct"]
        vol = opp["volume_ratio"]
        in_approved = opp["in_approved"]
        status = "✅ aprobado" if in_approved else "⭕ no aprobado"

        signal_emoji = "🟢" if signal == "STRONG" else "🟡"
        lines.append(
            f"{signal_emoji} <b>{sym}</b> {change:+.1f}% | Vol {vol:.1f}× | Score {score:.0f} | {status}"
        )

    lines += [
        "",
        "Usa <code>/analizar SYMBOL</code> para análisis completo.",
        f"Ver lista: {base_url.replace('127.0.0.1', 'aiutox-pi.tail2a2cda.ts.net')}/reports",
    ]

    try:
        notify("\n".join(lines))
    except Exception as e:
        logging.getLogger(__name__).error(f"notify_opportunities failed: {e}")
