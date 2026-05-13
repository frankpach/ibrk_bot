"""Fetch scanner data (most active, gainers, losers, sectors, implied move) from IBKR."""
import logging
import math

logger = logging.getLogger(__name__)

SECTOR_ETFS = {
    "XLK": "Tech", "XLF": "Finance", "XLE": "Energy",
    "XLV": "Health", "XLY": "Consumer", "XLI": "Industrial",
}


def fetch_and_cache_scanner(data_layer) -> None:
    """Fetch scanner results for most_active, gainers, losers, top_movers."""
    from app.db.database import upsert_scanner_results

    scan_map = {
        "most_active": "MOST_ACTIVE",
        "gainers":     "TOP_PERC_GAIN",
        "losers":      "TOP_PERC_LOSE",
    }
    for scan_type, scan_code in scan_map.items():
        try:
            raw = data_layer.run_scanner(scan_code)
            results = [
                {"symbol": s, "name": "", "change_pct": None,
                 "volume_ratio": None, "extra_json": "{}"}
                for s in (raw or [])[:10]
            ]
            upsert_scanner_results(scan_type, results)
        except Exception as e:
            logger.warning(f"Scanner {scan_type} ({scan_code}) failed: {e}")

    # top_movers = union of gainers + losers (already stored separately)
    try:
        from app.db.database import get_scanner_results
        movers = get_scanner_results("gainers") + get_scanner_results("losers")
        movers.sort(key=lambda r: abs(r.get("change_pct") or 0), reverse=True)
        upsert_scanner_results("top_movers", movers[:10])
    except Exception as e:
        logger.warning(f"Top movers merge failed: {e}")


def fetch_and_cache_sectors(data_layer) -> None:
    """Fetch sector ETF daily performance."""
    from app.db.database import upsert_scanner_results

    results = []
    for etf, name in SECTOR_ETFS.items():
        try:
            df = data_layer.get_ohlcv(etf, "2 D", "1 day", "scanner")
            if df is not None and len(df) >= 2:
                prev = float(df["close"].iloc[-2])
                curr = float(df["close"].iloc[-1])
                change_pct = round((curr - prev) / prev * 100, 2) if prev > 0 else 0.0
                results.append({
                    "symbol": etf, "name": name,
                    "change_pct": change_pct, "volume_ratio": None,
                    "extra_json": "{}",
                })
        except Exception as e:
            logger.warning(f"Sector ETF {etf} failed: {e}")

    if results:
        upsert_scanner_results("sector", results)


def fetch_implied_move(data_layer, symbols: list) -> None:
    """Fetch implied volatility as proxy for expected weekly move."""
    from app.db.database import upsert_scanner_results

    results = []
    for symbol in symbols[:10]:
        try:
            iv_df = data_layer.get_implied_volatility(symbol, "scanner")
            if iv_df is not None and len(iv_df) > 0:
                iv = float(iv_df["close"].iloc[-1])
                weekly_move = round(iv / math.sqrt(52) * 100, 1)
                results.append({
                    "symbol": symbol, "name": "",
                    "change_pct": weekly_move, "volume_ratio": None,
                    "extra_json": f'{{"iv": {iv:.4f}}}',
                })
        except Exception as e:
            logger.debug(f"Implied move {symbol}: {e}")

    if results:
        upsert_scanner_results("implied_move", results)
