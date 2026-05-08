# app/analysis/data.py
"""
IBDataLayer — wraps IBKRClient to provide cached market data.
TTL varies by context: trade_entry=0, on_demand=120, scanner=900, backtest=3600, fundamentals=86400.
Never modifies IBKRClient. Uses client_id=12 (IB_CLIENT_ID_DATA).
Returns None on failure — never raises exceptions.
"""
import logging
import time
from datetime import datetime
import pandas as pd
from app.config.settings import IB_MOCK, IB_CLIENT_ID_DATA

logger = logging.getLogger(__name__)

TTL = {
    "trade_entry": 0,
    "on_demand": 120,
    "scanner": 900,
    "backtest": 3600,
    "fundamentals": 86400,
}


class IBDataLayer:
    def __init__(self, ib_client):
        self._client = ib_client
        self._cache: dict = {}  # key -> (data, expires_at)

    def _cache_key(self, symbol: str, context: str, extra: str = "") -> str:
        return f"{symbol.upper()}:{context}:{extra}"

    def _get_cached(self, key: str):
        if key in self._cache:
            data, expires_at = self._cache[key]
            if time.time() < expires_at:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data, context: str):
        ttl = TTL.get(context, 120)
        if ttl == 0:
            return  # trade_entry: never cache
        expires_at = time.time() + ttl
        self._cache[key] = (data, expires_at)

    def get_ohlcv(self, symbol: str, duration: str, bar_size: str, context: str) -> pd.DataFrame | None:
        key = self._cache_key(symbol, context, f"{duration}:{bar_size}")
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            from ib_insync import Stock
            contract = Stock(symbol.upper(), "SMART", "USD")
            bars = self._client.ib.reqHistoricalData(
                contract, endDateTime="", durationStr=duration,
                barSizeSetting=bar_size, whatToShow="TRADES",
                useRTH=True, formatDate=1,
            )
            if not bars:
                return None
            df = pd.DataFrame([{
                "open": b.open, "high": b.high, "low": b.low,
                "close": b.close, "volume": b.volume
            } for b in bars])
            self._set_cached(key, df, context)
            return df
        except Exception as e:
            logger.error(f"IBDataLayer.get_ohlcv({symbol}): {e}")
            return None

    def get_historical_volatility(self, symbol: str, context: str) -> pd.DataFrame | None:
        key = self._cache_key(symbol, context, "HV")
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            from ib_insync import Stock
            contract = Stock(symbol.upper(), "SMART", "USD")
            bars = self._client.ib.reqHistoricalData(
                contract, endDateTime="", durationStr="30 D",
                barSizeSetting="1 day", whatToShow="HISTORICAL_VOLATILITY",
                useRTH=True, formatDate=1,
            )
            if not bars:
                return None
            df = pd.DataFrame([{"close": b.close} for b in bars])
            self._set_cached(key, df, context)
            return df
        except Exception as e:
            logger.error(f"IBDataLayer.get_historical_volatility({symbol}): {e}")
            return None

    def get_implied_volatility(self, symbol: str, context: str) -> pd.DataFrame | None:
        key = self._cache_key(symbol, context, "IV")
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            from ib_insync import Stock
            contract = Stock(symbol.upper(), "SMART", "USD")
            bars = self._client.ib.reqHistoricalData(
                contract, endDateTime="", durationStr="30 D",
                barSizeSetting="1 day", whatToShow="OPTION_IMPLIED_VOLATILITY",
                useRTH=True, formatDate=1,
            )
            if not bars:
                return None
            df = pd.DataFrame([{"close": b.close} for b in bars])
            self._set_cached(key, df, context)
            return df
        except Exception as e:
            logger.error(f"IBDataLayer.get_implied_volatility({symbol}): {e}")
            return None

    def get_news(self, symbol: str) -> list:
        key = self._cache_key(symbol, "scanner", "news")
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            from app.scanner.news import get_news_summary, _extract_sentiment
            # Try IB news first, fall back to Yahoo RSS
            news_items = []
            try:
                from ib_insync import Stock
                contract = Stock(symbol.upper(), "SMART", "USD")
                news = self._client.ib.reqHistoricalNews(
                    reqId=1, conId=contract.conId if hasattr(contract, "conId") else 0,
                    providerCodes="BRFG+DJNL+BRFUPDN",
                    startDateTime="", endDateTime="", totalResults=3,
                )
                for item in (news or []):
                    headline = getattr(item, "headline", "")
                    sentiment = _extract_sentiment(headline)
                    news_items.append({"title": headline, "sentiment": sentiment, "date": getattr(item, "time", "")})
            except Exception:
                pass

            if not news_items:
                # Yahoo RSS fallback
                import feedparser
                url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    title = getattr(entry, "title", "")
                    sentiment = _extract_sentiment(title)
                    news_items.append({"title": title, "sentiment": sentiment, "date": str(getattr(entry, "published", ""))})

            self._set_cached(key, news_items, "scanner")
            return news_items
        except Exception as e:
            logger.error(f"IBDataLayer.get_news({symbol}): {e}")
            return []

    def get_earnings_date(self, symbol: str) -> datetime | None:
        key = self._cache_key(symbol, "fundamentals", "earnings")
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        # Try IB fundamental data
        try:
            from ib_insync import Stock
            contract = Stock(symbol.upper(), "SMART", "USD")
            xml_data = self._client.ib.reqFundamentalData(contract, "CalendarReport")
            if xml_data:
                import re
                match = re.search(r'<EarningsDate>(\d{4}-\d{2}-\d{2})</EarningsDate>', xml_data)
                if match:
                    dt = datetime.strptime(match.group(1), "%Y-%m-%d")
                    self._set_cached(key, dt, "fundamentals")
                    return dt
        except Exception:
            pass
        self._set_cached(key, None, "fundamentals")
        return None

    def run_scanner(self, scan_code: str, max_results: int = 20) -> list:
        key = self._cache_key("SCANNER", "scanner", scan_code)
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            results = self._client.ib.reqScannerData(None)
            if isinstance(results, list):
                # MockIBClient returns list of strings; real IB returns ScanData objects
                if results and isinstance(results[0], str):
                    symbols = results[:max_results]
                else:
                    symbols = [getattr(r, "contractDetails", {}).contract.symbol
                               for r in results[:max_results]
                               if hasattr(r, "contractDetails")]
                self._set_cached(key, symbols, "scanner")
                return symbols
        except Exception as e:
            logger.error(f"IBDataLayer.run_scanner({scan_code}): {e}")
        return []

    def get_spy_price_on(self, date: datetime) -> float | None:
        key = self._cache_key("SPY", "backtest", date.strftime("%Y%m%d"))
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            df = self.get_ohlcv("SPY", "5 D", "1 day", "backtest")
            if df is not None and len(df) > 0:
                price = float(df["close"].iloc[-1])
                self._set_cached(key, price, "backtest")
                return price
        except Exception as e:
            logger.error(f"IBDataLayer.get_spy_price_on: {e}")
        return None
