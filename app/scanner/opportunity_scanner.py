"""Proactive hourly opportunity scanner — scores top movers and alerts on strong candidates."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

MIN_SCORE_THRESHOLD = 55.0
MIN_CHANGE_PCT = 1.5       # minimum % move to be interesting
MIN_VOLUME_RATIO = 1.3     # minimum volume surge
MAX_ATR_PCT = 8.0          # skip extremely volatile stocks (too risky)

# ---------------------------------------------------------------------------
# Feature 1: Sector Rotation Detector
# ---------------------------------------------------------------------------

SECTOR_ETF_MAP = {
    "XLK": ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN"],
    "XLF": ["JPM"],
    "XLE": ["CL", "GC"],
    "XLV": [],
    "XLY": ["TSLA", "AMZN"],
}
SECTOR_BOOST_THRESHOLD = 1.5   # % sector move to trigger boost
SECTOR_DRAG_THRESHOLD = -1.5   # % sector move to penalize


def get_sector_context() -> dict:
    """
    Returns {symbol: sector_boost_score} based on sector ETF performance.
    Positive = tailwind, negative = headwind, 0 = neutral.
    """
    from app.db.database import get_scanner_results

    sector_data = get_scanner_results("sector")
    context = {}

    for row in sector_data:
        etf = row.get("symbol", "")
        pct = float(row.get("change_pct") or 0)

        # Find which symbols map to this sector
        related = SECTOR_ETF_MAP.get(etf, [])

        if abs(pct) < 0.5:
            continue  # neutral, skip

        boost = 1.0
        if pct >= SECTOR_BOOST_THRESHOLD:
            boost = 1.3  # 30% score boost for stocks in strong sector
        elif pct >= 0.5:
            boost = 1.1
        elif pct <= SECTOR_DRAG_THRESHOLD:
            boost = 0.7  # 30% penalty for stocks in weak sector
        elif pct <= -0.5:
            boost = 0.9

        for sym in related:
            context[sym] = max(context.get(sym, 1.0), boost)

    return context


# ---------------------------------------------------------------------------
# Feature 3: Correlation Lag Detector
# ---------------------------------------------------------------------------

CORRELATION_LAG_THRESHOLD = -0.02  # symbol lagging sector by >2% = catch-up candidate
CORRELATION_PAIRS = [
    # (symbol, benchmark_etf, name)
    ("AAPL", "XLK", "Tech"),
    ("MSFT", "XLK", "Tech"),
    ("NVDA", "XLK", "Tech"),
    ("META", "XLK", "Tech"),
    ("JPM", "XLF", "Finance"),
    ("AMZN", "XLY", "Consumer"),
    ("TSLA", "XLY", "Consumer"),
]


def scan_correlation_lags(data_layer) -> list:
    """
    Find symbols significantly lagging their sector ETF today.
    A lagging symbol in an uptrending sector = potential catch-up trade.
    """
    from app.db.database import get_scanner_results, get_daily_watchlist, upsert_daily_watchlist
    from app.config.settings import MARKET_TZ

    today = datetime.now(MARKET_TZ).strftime("%Y-%m-%d")
    existing = {w["symbol"] for w in get_daily_watchlist(today)}

    sector_perf = {r["symbol"]: float(r.get("change_pct") or 0)
                   for r in get_scanner_results("sector")}

    results = []

    for sym, etf, sector_name in CORRELATION_PAIRS:
        if sym in existing:
            continue

        # Skip if earnings in next 3 days
        try:
            earnings_date = data_layer.get_earnings_date(sym)
            if earnings_date:
                days_to_earnings = (earnings_date - datetime.utcnow()).days
                if 0 <= days_to_earnings <= 3:
                    logger.info(f"[lag] Skipping {sym}: earnings in {days_to_earnings}d")
                    continue
        except Exception:
            pass

        sector_pct = sector_perf.get(etf, 0)
        if sector_pct < 0.5:
            continue  # sector not strong enough to matter

        try:
            # Get today's price change for the symbol
            df = data_layer.get_ohlcv(sym, "2 D", "1 day", "scanner")
            if df is None or len(df) < 2:
                continue

            prev_close = float(df["close"].iloc[-2])
            curr_close = float(df["close"].iloc[-1])
            sym_pct = (curr_close - prev_close) / prev_close if prev_close > 0 else 0

            lag = sym_pct - sector_pct

            # Symbol is lagging its sector significantly
            if lag <= CORRELATION_LAG_THRESHOLD:
                from app.analysis.indicators import compute_features, compute_from_df, classify_signal
                from app.analysis.scorer import compute_score
                ind = compute_from_df(df)
                if not ind:
                    continue
                signal = classify_signal(ind.get("rsi"), ind.get("macd_crossover"), ind.get("volume_ratio"))
                features = compute_features(sym, df)
                score_result = compute_score(features, sym, [])
                score = score_result.total

                reason = f"lag_{sector_name.lower()}: {sym_pct*100:+.1f}% vs sector {sector_pct:+.1f}% (lag={lag*100:+.1f}%)"

                is_new = upsert_daily_watchlist(
                    date=today, symbol=sym, score=score,
                    signal_strength=signal, change_pct=sym_pct * 100,
                    volume_ratio=ind.get("volume_ratio") or 1.0,
                    reason=reason,
                )

                if is_new and score >= 45:  # lower threshold for lag candidates
                    results.append({
                        "symbol": sym, "score": score, "signal": signal,
                        "change_pct": sym_pct * 100, "volume_ratio": ind.get("volume_ratio") or 1.0,
                        "in_approved": True,  # correlation pairs are all approved
                        "reason": reason,
                        "trigger": "lag",
                    })
        except Exception as e:
            logger.debug(f"Correlation lag scan failed for {sym}: {e}")

    return results


# ---------------------------------------------------------------------------
# Feature 2: News-triggered immediate analysis
# ---------------------------------------------------------------------------

def scan_news_triggered_opportunities(data_layer) -> list:
    """
    Check if any recent news (last 45min) warrants immediate analysis.
    Returns list of symbols with positive news that haven't been analyzed today.
    """
    from app.db.database import get_news_cache, get_daily_watchlist, upsert_daily_watchlist, get_approved_symbols
    from datetime import timedelta
    from app.config.settings import MARKET_TZ

    today = datetime.now(MARKET_TZ).strftime("%Y-%m-%d")
    cutoff = (datetime.utcnow() - timedelta(minutes=45)).isoformat()

    # Get very recent news (last 45 min)
    recent_news = get_news_cache(limit=50)
    recent_news = [n for n in recent_news if n.get("fetched_at", "") >= cutoff]

    if not recent_news:
        return []

    # Already in watchlist today?
    existing = {w["symbol"] for w in get_daily_watchlist(today)}

    # Score by news sentiment: only positive, not already tracked
    triggered = {}
    for n in recent_news:
        sym = n.get("symbol", "")
        if not sym or sym in existing:
            continue
        sentiment = n.get("sentiment", "neutral")
        if sentiment == "positive":
            triggered[sym] = triggered.get(sym, 0) + 1

    # Symbols with 1+ positive news items → immediate analysis candidate
    strong_news = [sym for sym, count in triggered.items() if count >= 1]

    approved = set(get_approved_symbols())
    results = []

    for sym in strong_news[:5]:
        try:
            # Skip if earnings in next 3 days
            earnings_date = data_layer.get_earnings_date(sym)
            if earnings_date:
                days_to_earnings = (datetime.utcnow() - earnings_date).days * -1
                if 0 <= days_to_earnings <= 3:
                    logger.info(f"[news] Skipping {sym}: earnings in {days_to_earnings}d")
                    continue
        except Exception:
            pass
        try:
            df = data_layer.get_ohlcv(sym, "5 D", "1 day", "scanner")
            if df is None or len(df) < 15:
                continue
            from app.analysis.indicators import compute_features, compute_from_df, classify_signal
            from app.analysis.scorer import compute_score
            ind = compute_from_df(df)
            if not ind:
                continue
            signal = classify_signal(ind.get("rsi"), ind.get("macd_crossover"), ind.get("volume_ratio"))
            features = compute_features(sym, df)
            score_result = compute_score(features, sym, [])
            score = score_result.total

            news_count = triggered[sym]
            reason = f"news_trigger: {news_count} noticias positivas recientes"

            is_new = upsert_daily_watchlist(
                date=today, symbol=sym, score=score,
                signal_strength=signal, change_pct=0.0,
                volume_ratio=ind.get("volume_ratio") or 1.0,
                reason=reason,
            )
            if is_new:
                results.append({
                    "symbol": sym, "score": score, "signal": signal,
                    "change_pct": 0.0, "volume_ratio": ind.get("volume_ratio") or 1.0,
                    "in_approved": sym in approved,
                    "reason": reason,
                    "trigger": "news",
                })
        except Exception as e:
            logger.debug(f"News-triggered scan failed for {sym}: {e}")

    return results


# ---------------------------------------------------------------------------
# Main opportunity scan (with sector boost applied)
# ---------------------------------------------------------------------------

def run_opportunity_scan(data_layer, ib_client=None) -> list:
    """
    Score top movers from scanner_results and update daily_watchlist.
    Returns list of NEW high-scoring opportunities (not previously alerted).
    Sector context is applied as a score multiplier.
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

    # Build sector context once for all candidates
    sector_ctx = get_sector_context()

    new_opportunities = []

    for cand in candidates[:20]:  # limit to avoid rate limit
        sym = cand["symbol"]
        change_pct = abs(cand.get("change_pct") or 0.0)
        vol_ratio = cand.get("volume_ratio") or 0.0

        # Quick pre-filter: skip if not interesting enough
        if change_pct < MIN_CHANGE_PCT and vol_ratio < MIN_VOLUME_RATIO:
            continue

        # Capa 5: Earnings awareness — skip if earnings in next 3 days
        try:
            earnings_date = data_layer.get_earnings_date(sym)
            if earnings_date:
                days_to_earnings = (earnings_date - datetime.now()).days
                if 0 <= days_to_earnings <= 3:
                    logger.info(f"Skipping {sym}: earnings in {days_to_earnings}d (too risky)")
                    continue
        except Exception:
            pass  # if we can't check, continue anyway

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

            # Apply sector rotation boost/drag
            sector_boost = sector_ctx.get(sym, 1.0)
            adjusted_score = min(100.0, score * sector_boost)

            if adjusted_score < MIN_SCORE_THRESHOLD:
                continue

            reason = f"{cand['scan_type'].replace('_',' ')}: {cand['change_pct']:+.1f}% | signal={signal} | score={adjusted_score:.0f}"

            is_new = upsert_daily_watchlist(
                date=today,
                symbol=sym,
                score=adjusted_score,
                signal_strength=signal,
                change_pct=cand.get("change_pct") or 0.0,
                volume_ratio=vol_ratio,
                reason=reason,
            )

            if is_new and signal in ("STRONG", "MEDIUM"):
                new_opportunities.append({
                    "symbol": sym,
                    "score": adjusted_score,
                    "signal": signal,
                    "change_pct": cand.get("change_pct") or 0.0,
                    "volume_ratio": vol_ratio,
                    "in_approved": sym in approved,
                    "reason": reason,
                    "trigger": None,
                })

        except Exception as e:
            logger.debug(f"Opportunity scan skipped {sym}: {e}")

    return new_opportunities


def notify_opportunities(opportunities: list, base_url: str = "http://localhost:8088") -> None:
    """Send Telegram alert for new high-scoring opportunities."""
    if not opportunities:
        return

    from app.notifications.telegram import notify

    trigger_emoji_map = {"news": "📰", "lag": "⏳"}

    lines = ["🎯 <b>Nuevas oportunidades detectadas</b>", ""]
    for opp in opportunities[:5]:
        sym = opp["symbol"]
        score = opp["score"]
        signal = opp["signal"]
        change = opp["change_pct"]
        vol = opp["volume_ratio"]
        in_approved = opp["in_approved"]
        status = "✅ aprobado" if in_approved else "⭕ no aprobado"
        trigger = opp.get("trigger")

        if trigger in trigger_emoji_map:
            lead_emoji = trigger_emoji_map[trigger]
        else:
            lead_emoji = "🟢" if signal == "STRONG" else "🟡"

        lines.append(
            f"{lead_emoji} <b>{sym}</b> {change:+.1f}% | Score {score:.0f} | {status}"
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
