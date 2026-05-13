# app/analysis/data.py
"""
IBDataLayer — wraps IBKRClient to provide cached market data.
TTL varies by context: trade_entry=0, on_demand=120, scanner=900, backtest=3600, fundamentals=86400.
Never modifies IBKRClient. Uses client_id=12 (IB_CLIENT_ID_DATA).
Returns None on failure — never raises exceptions.
"""
import asyncio
import logging
import time
from datetime import datetime
import pandas as pd
from app.config.settings import IB_MOCK, IB_CLIENT_ID_DATA
from app.ibkr.contract_factory import build_contract, get_what_to_show, get_use_rth
from ib_insync import Future as IBFuture

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
        if data is None and context == "on_demand":
            return  # on_demand: never cache failures, retry next time
        ttl = TTL.get(context, 120)
        if ttl == 0:
            return  # trade_entry: never cache
        expires_at = time.time() + ttl
        self._cache[key] = (data, expires_at)

    def _resolve_future_front_month(self, contract):
        """Resolve front-month expiry for a generic Future contract."""
        result = self._client.ib.reqContractDetailsAsync(contract)
        # Always use the IBKRClient dedicated event loop - safe from any thread.
        ib_loop = getattr(self._client, "_loop", None)
        if isinstance(ib_loop, asyncio.AbstractEventLoop) and ib_loop.is_running():
            task = asyncio.run_coroutine_threadsafe(result, ib_loop)
            details = task.result(timeout=15)
        elif asyncio.iscoroutine(result):
            loop = asyncio.new_event_loop()
            try:
                details = loop.run_until_complete(result)
            finally:
                loop.close()
        else:
            # Test-friendly path: sync mock returns data directly
            details = result
        if not details:
            raise RuntimeError(f"No contract details for future {contract.symbol}")
        return sorted(
            details,
            key=lambda d: d.contract.lastTradeDateOrContractMonth or "99999999",
        )[0].contract

    def get_ohlcv(
        self,
        symbol: str,
        duration: str,
        bar_size: str,
        context,
        *,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> pd.DataFrame | None:
        context_str = str(context) if not isinstance(context, str) else context
        key = self._cache_key(symbol, context_str, f"{duration}:{bar_size}:{sec_type}")
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            contract = build_contract(symbol, sec_type, exchange, currency)
            # For futures, resolve front-month contract via IB
            if sec_type.upper() == "FUT":
                contract = self._resolve_future_front_month(contract)
            what_to_show = get_what_to_show(sec_type)
            use_rth = get_use_rth(sec_type)

            def _fetch(dur: str):
                """Fetch historical bars — thread-safe for Python 3.12+."""
                ib_loop = getattr(self._client, "_loop", None)
                if isinstance(ib_loop, asyncio.AbstractEventLoop) and ib_loop.is_running():
                    # Called from a thread without its own event loop — use IB client loop
                    future = asyncio.run_coroutine_threadsafe(
                        self._client.ib.reqHistoricalDataAsync(
                            contract, endDateTime="", durationStr=dur,
                            barSizeSetting=bar_size, whatToShow=what_to_show,
                            useRTH=use_rth, formatDate=1,
                        ),
                        ib_loop,
                    )
                    return future.result(timeout=30)
                # Called from the IB loop thread directly (safe to call synchronously)
                return self._client.ib.reqHistoricalData(
                    contract, endDateTime="", durationStr=dur,
                    barSizeSetting=bar_size, whatToShow=what_to_show,
                    useRTH=use_rth, formatDate=1,
                )

            # Primary request
            bars = _fetch(duration)

            # Fallback: if empty, try shorter durations progressively
            fallback_durations = ["30 D", "10 D", "5 D", "2 D"]
            for fallback in fallback_durations:
                if bars and len(bars) >= 15:
                    break
                try:
                    logger.info(f"Retrying {symbol} with duration={fallback} (primary={duration} returned {len(bars) if bars else 0})")
                    bars = _fetch(fallback)
                except Exception as retry_err:
                    logger.warning(f"Fallback {fallback} for {symbol} failed: {retry_err}")

            if not bars or len(bars) < 15:
                logger.warning(f"No historical bars for {symbol} after all retries (last got {len(bars) if bars else 0})")
                return None

            df = pd.DataFrame([{
                "open": b.open, "high": b.high, "low": b.low,
                "close": b.close, "volume": b.volume
            } for b in bars])
            self._set_cached(key, df, context_str)
            return df
        except Exception as e:
            logger.error(f"IBDataLayer.get_ohlcv({symbol}): {e}")
            return None

    def get_indicators(
        self,
        symbol: str,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> dict:
        """Return key indicators for a symbol as a plain dict.

        Used by market_open_selector.select_top_symbols() for scoring.
        Returns {"rsi": float|None, "volume_ratio": float|None} on success,
        empty dict on failure (caller falls back to simple_score defaults).
        """
        try:
            from app.analysis.indicators import compute_features
            df = self.get_ohlcv(
                symbol, "30 D", "1 day", "scanner",
                sec_type=sec_type, exchange=exchange, currency=currency,
            )
            if df is None or len(df) < 15:
                return {}
            fs = compute_features(symbol, df)
            return {
                "rsi": fs.rsi_14,
                "volume_ratio": fs.volume_ratio_20d,
                "macd_crossover": fs.macd_crossover,
                "bollinger_position": fs.bollinger_position,
                "atr_pct": fs.atr_pct,
            }
        except Exception as e:
            logger.warning(f"IBDataLayer.get_indicators({symbol}): {e}")
            return {}

    def _fetch_threadsafe(self, contract, duration: str, bar_size: str,
                          what_to_show: str, use_rth: bool = True) -> list:
        """Thread-safe reqHistoricalData — works from any thread in Python 3.12+."""
        ib_loop = getattr(self._client, "_loop", None)
        if isinstance(ib_loop, asyncio.AbstractEventLoop) and ib_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self._client.ib.reqHistoricalDataAsync(
                    contract, endDateTime="", durationStr=duration,
                    barSizeSetting=bar_size, whatToShow=what_to_show,
                    useRTH=use_rth, formatDate=1,
                ),
                ib_loop,
            )
            return future.result(timeout=30) or []
        return self._client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr=duration,
            barSizeSetting=bar_size, whatToShow=what_to_show,
            useRTH=use_rth, formatDate=1,
        ) or []

    def get_historical_volatility(self, symbol: str, context: str) -> pd.DataFrame | None:
        key = self._cache_key(symbol, context, "HV")
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        try:
            from ib_insync import Stock
            contract = Stock(symbol.upper(), "SMART", "USD")
            bars = self._fetch_threadsafe(contract, "30 D", "1 day",
                                          "HISTORICAL_VOLATILITY", True)
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
            bars = self._fetch_threadsafe(contract, "30 D", "1 day",
                                          "OPTION_IMPLIED_VOLATILITY", True)
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
