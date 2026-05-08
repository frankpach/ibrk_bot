"""
IB Scanner integration for pre-open symbol selection.

Only STK_US uses the live IB Scanner. FUT, FX, and CRYPTO fall back to
their full seed lists because IB Scanner does not reliably return results
for those instrument types on paper accounts.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ib_insync import ScannerSubscription

if TYPE_CHECKING:
    from app.ibkr.client import IBKRClient

logger = logging.getLogger(__name__)

# Scan codes run in order; union is ranked by first appearance
STK_US_SCAN_CODES = ["MOST_ACTIVE", "TOP_VOLUME_RATE", "HOT_BY_PRICE"]
STK_US_LOCATION = "STK.US.MAJOR"
STK_US_INSTRUMENT = "STK"


def run_ib_scanner(
    ib_client: "IBKRClient",
    scan_code: str,
    location: str,
    instrument: str,
    limit: int = 50,
) -> list[dict]:
    """Run one IB scanner subscription synchronously.

    Args:
        ib_client: Connected IBKRClient instance (uses ib_client.ib internally).
        scan_code: IB scan code, e.g. "MOST_ACTIVE".
        location: IB location code, e.g. "STK.US.MAJOR".
        instrument: IB instrument type, e.g. "STK".
        limit: Maximum number of results to return.

    Returns:
        List of dicts [{"symbol": str, "rank": int}, ...], ordered by IB rank.
        Returns empty list on any error.
    """
    sub = ScannerSubscription(
        instrument=instrument,
        locationCode=location,
        scanCode=scan_code,
        numberOfRows=limit,
    )
    try:
        scan_data = ib_client.ib.reqScannerData(sub)
    except Exception as exc:
        logger.warning(
            "IB scanner %s/%s failed: %s", location, scan_code, exc
        )
        return []

    results: list[dict] = []
    for item in scan_data[:limit]:
        symbol = getattr(item.contractDetails.contract, "symbol", None)
        if symbol:
            results.append({"symbol": symbol, "rank": item.rank})

    logger.info(
        "IB scanner %s/%s returned %d results", location, scan_code, len(results)
    )
    return results


def get_stk_us_candidates(
    ib_client: "IBKRClient",
    limit: int = 50,
) -> list[dict]:
    """Union MOST_ACTIVE + TOP_VOLUME_RATE + HOT_BY_PRICE from STK.US.MAJOR.

    Deduplicates by symbol. Ranking is determined by earliest appearance
    across the three scans (lower rank = appears first = better).

    Args:
        ib_client: Connected IBKRClient instance.
        limit: Maximum symbols to return after union.

    Returns:
        List of dicts [{"symbol": str, "rank": int}, ...], deduplicated
        and sorted by composite rank (ascending = best first).
    """
    seen: dict[str, int] = {}   # symbol -> best (lowest) composite rank
    composite_rank = 0

    for scan_code in STK_US_SCAN_CODES:
        results = run_ib_scanner(
            ib_client,
            scan_code=scan_code,
            location=STK_US_LOCATION,
            instrument=STK_US_INSTRUMENT,
            limit=limit,
        )
        for item in results:
            symbol = item["symbol"]
            if symbol not in seen:
                seen[symbol] = composite_rank
                composite_rank += 1
            # Already seen: keep original (earlier) rank

    sorted_symbols = sorted(seen.items(), key=lambda kv: kv[1])
    candidates = [
        {"symbol": sym, "rank": rank} for sym, rank in sorted_symbols[:limit]
    ]
    logger.info(
        "get_stk_us_candidates: %d unique symbols from union of %d scans",
        len(candidates),
        len(STK_US_SCAN_CODES),
    )
    return candidates
