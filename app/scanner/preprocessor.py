# app/scanner/preprocessor.py
"""
Preprocesador de senales tecnicas multi-timeframe.
Corre cada 15 min en horario de mercado via APScheduler.
Senal solo cuando daily + al menos hourly o 5min confirman.
Nunca llama al LLM.
"""
import json
import logging
from datetime import datetime, timezone

import pandas as pd

from app.config.settings import (
    MARKET_TZ, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
)
from app.infrastructure.db.compat import get_approved_symbols, get_approved_symbols_with_meta, get_all_active_symbols_today, insert_signal
from app.db.models import Signal
from app.ibkr.contract_factory import build_contract, get_use_rth
from app.scanner.liquid_hours import is_liquid_at

logger = logging.getLogger(__name__)

from app.analysis.indicators import (
    classify_signal, classify_multitimeframe, compute_from_df as _calc_indicators
)



def _fetch_bars(ib_client, contract, duration: str, bar_size: str, use_rth: bool = True) -> pd.DataFrame:
    """Descarga barras historicas de IB y retorna DataFrame."""
    try:
        bars = ib_client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr=duration,
            barSizeSetting=bar_size, whatToShow="TRADES",
            useRTH=use_rth, formatDate=1,
        )
    except Exception as e:
        logger.warning(f"reqHistoricalData failed for {contract.symbol}: {e}")
        return pd.DataFrame()
    if not bars or len(bars) < 15:
        return pd.DataFrame()
    return pd.DataFrame([{
        "open": b.open, "high": b.high, "low": b.low,
        "close": b.close, "volume": b.volume
    } for b in bars])


def _weekly_trend_filter(df_weekly) -> str:
    """
    Determine weekly macro trend from weekly OHLCV DataFrame.
    Returns: "BULLISH", "BEARISH", or "NEUTRAL"
    """
    if df_weekly is None or len(df_weekly) < 20:
        return "NEUTRAL"
    try:
        close = df_weekly["close"]
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1] if len(df_weekly) >= 50 else sma20
        last_close = close.iloc[-1]
        if last_close > sma20 and sma20 > sma50:
            return "BULLISH"
        if last_close < sma20 and sma20 < sma50:
            return "BEARISH"
    except Exception:
        pass
    return "NEUTRAL"


def _is_market_hours(now: datetime) -> bool:
    et = now.astimezone(MARKET_TZ)
    if et.weekday() >= 5:
        return False
    open_t = et.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    close_t = et.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    return open_t <= et <= close_t


def scan_symbol(symbol: str, ib_client=None, symbol_meta: dict | None = None) -> dict:
    """
    Escanea un simbolo en 3 timeframes y retorna la senal combinada.
    Solo inserta en DB si la senal es STRONG o MEDIUM.

    Args:
        symbol: Ticker symbol.
        ib_client: IB connection client (optional when testing liquid-hours skip).
        symbol_meta: Dict with sec_type/exchange/currency/liquid_hours. Defaults to
                     US equity (STK/SMART/USD/US_RTH) when not provided.

    Returns:
        dict with at minimum {"symbol": ..., "skipped": bool}.
    """
    meta = symbol_meta or {
        "symbol": symbol, "sec_type": "STK", "exchange": "SMART",
        "currency": "USD", "liquid_hours": "US_RTH",
    }

    now = datetime.now(timezone.utc)
    if not is_liquid_at(now, meta.get("liquid_hours")):
        logger.debug(f"Outside liquid hours for {symbol} ({meta.get("liquid_hours")})")
        return {"symbol": symbol, "skipped": True, "reason": "not_liquid"}

    try:
        sec_type = meta.get("sec_type", "STK")
        exchange = meta.get("exchange", "SMART")
        currency = meta.get("currency", "USD")
        contract = build_contract(symbol, sec_type, exchange, currency)
        use_rth = get_use_rth(sec_type)

        df_daily = _fetch_bars(ib_client, contract, "30 D", "1 day", use_rth=use_rth)
        ind_daily = _calc_indicators(df_daily)
        if not ind_daily:
            logger.warning(f"Not enough daily bars for {symbol}")
            return {"symbol": symbol, "skipped": False, "strength": None}
        sig_daily = classify_signal(ind_daily["rsi"], ind_daily["macd_crossover"], ind_daily["volume_ratio"])

        df_hourly = _fetch_bars(ib_client, contract, "5 D", "1 hour", use_rth=use_rth)
        ind_hourly = _calc_indicators(df_hourly)
        sig_hourly = classify_signal(
            ind_hourly["rsi"], ind_hourly["macd_crossover"], ind_hourly["volume_ratio"]
        ) if ind_hourly else "WEAK"

        df_5min = _fetch_bars(ib_client, contract, "1 D", "5 mins", use_rth=use_rth)
        ind_5min = _calc_indicators(df_5min)
        sig_5min = classify_signal(
            ind_5min["rsi"], ind_5min["macd_crossover"], ind_5min["volume_ratio"]
        ) if ind_5min else "WEAK"

        strength = classify_multitimeframe(sig_daily, sig_hourly, sig_5min)

        logger.info(
            f"SCAN {symbol}: daily={sig_daily} hourly={sig_hourly} 5min={sig_5min} -> {strength}"
        )

        # Weekly trend fetch (best-effort — NEUTRAL on any failure)
        df_weekly = None
        try:
            weekly_bars = ib_client.ib.reqHistoricalData(
                contract, endDateTime="",
                durationStr="1 Y", barSizeSetting="1 week",
                whatToShow="TRADES", useRTH=use_rth, formatDate=1,
            )
            if weekly_bars and len(weekly_bars) >= 20:
                df_weekly = pd.DataFrame([{"close": b.close} for b in weekly_bars])
        except Exception as e:
            logger.warning(f"Weekly fetch failed for {symbol}: {e}")

        weekly_trend = _weekly_trend_filter(df_weekly)

        # Partial veto: downgrade strength on BEARISH macro trend
        original_strength = strength
        if weekly_trend == "BEARISH":
            if strength == "STRONG":
                strength = "MEDIUM"
                logger.info(f"{symbol}: STRONG→MEDIUM (bearish weekly trend)")
            elif strength == "MEDIUM":
                strength = "WEAK"
                logger.info(f"{symbol}: MEDIUM→WEAK (bearish weekly trend)")

        if strength in ("STRONG", "MEDIUM", "WEAK"):
            extra = json.dumps({
                "daily": sig_daily, "hourly": sig_hourly, "5min": sig_5min,
                "weekly_trend": weekly_trend
            })
            insert_signal(Signal(
                id=None, symbol=symbol, strength=strength,
                rsi=ind_daily["rsi"], macd=ind_daily["macd"],
                volume_ratio=ind_daily["volume_ratio"],
                extra_indicators=extra,
                created_at=datetime.now(tz=MARKET_TZ),
            ))
            logger.info(
                f"Signal {strength} for {symbol} "
                f"[D:{sig_daily} H:{sig_hourly} 5m:{sig_5min} W:{weekly_trend}] "
                f"RSI:{ind_daily['rsi']} Vol:{ind_daily['volume_ratio']}"
            )

        return {"symbol": symbol, "skipped": False, "strength": strength}

    except Exception as e:
        logger.error(f"Error scanning {symbol}: {e}")
        return {"symbol": symbol, "skipped": False, "strength": None, "error": str(e)}


def run_scan(ib_client=None) -> None:
    from datetime import date, datetime, timezone

    today = date.today().isoformat()
    now = datetime.now(timezone.utc)

    active = get_all_active_symbols_today(today)
    if not active:
        logger.info("run_scan: no active_symbols for %s -- using full approved list", today)
        active = get_approved_symbols_with_meta()
    else:
        logger.info("run_scan: %d active symbols for %s", len(active), today)

    for meta in active:
        liquid_hours = meta.get("liquid_hours")
        if liquid_hours and not is_liquid_at(now, liquid_hours):
            continue
        try:
            scan_symbol(meta["symbol"], symbol_meta=meta, ib_client=ib_client)
        except Exception as exc:
            logger.error("scan_symbol failed for %s: %s", meta["symbol"], exc)
