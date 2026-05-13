"""Fetch news from IBKR for approved symbols and persist to news_cache."""
import logging
import time

logger = logging.getLogger(__name__)


def fetch_and_cache_news(data_layer) -> int:
    """
    Fetch news for all approved symbols. Returns count of articles saved.
    Rate-limit safe: 0.5s delay between symbols.
    """
    from app.db.database import (
        get_approved_symbols_with_meta, insert_news_cache, clear_news_cache_older_than,
    )

    try:
        clear_news_cache_older_than(hours=24)
    except Exception:
        pass

    syms = get_approved_symbols_with_meta()[:40]
    count = 0
    for sym_meta in syms:
        symbol = sym_meta.get("symbol", "")
        if not symbol:
            continue
        try:
            news_items = data_layer.get_news(symbol)
            for item in news_items or []:
                headline = item.get("title", "")
                if not headline:
                    continue
                insert_news_cache(
                    symbol=symbol,
                    headline=headline,
                    provider=item.get("provider", ""),
                    sentiment=item.get("sentiment", "neutral"),
                    article_id=str(item.get("article_id", "")),
                    published_at=str(item.get("date", "")),
                )
                count += 1
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"News fetch failed for {symbol}: {e}")

    logger.info(f"News cache updated: {count} articles for {len(syms)} symbols")
    return count
