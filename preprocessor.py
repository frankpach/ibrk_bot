# app/scanner/preprocessor.py
import logging
from datetime import datetime
import pandas as pd
from app.config.settings import MARKET_TZ, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE, MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE
from app.db.database import get_approved_symbols, insert_signal
from app.db.models import Signal

logger = logging.getLogger(__name__)


def classify_signal(rsi: float, macd_crossover: bool, volume_ratio: float) -> str:
    conditions = [rsi < 30 or rsi > 70, macd_crossover, volume_ratio > 1.5]
    count = sum(conditions)
    if count == 3:
        return "STRONG"
    if count == 2:
        return "MEDIUM"
    return "WEAK"


def _is_market_hours(now: datetime) -> bool:
    et = now.astimezone(MARKET_TZ)
    if et.weekday() >= 5:
        return False
    open_t = et.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    close_t = et.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    return open_t <= et <= close_t


def scan_symbol(symbol: str, ib_client) -> str | None:
    try:
        from ib_insync import Stock
        contract = Stock(symbol, "SMART", "USD")
        bars = ib_client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr="30 D",
            barSizeSetting="1 day", whatToShow="TRADES",
            useRTH=True, formatDate=1,
        )
        if not bars or len(bars) < 15:
            logger.warning(f"Not enough bars for {symbol}")
            return None

        df = pd.DataFrame([{"close": b.close, "volume": b.volume} for b in bars])
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = float((100 - 100 / (1 + rs)).iloc[-1])

        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_crossover = (
            (macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]) or
            (macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1])
        )

        avg_vol = df["volume"].rolling(20).mean().iloc[-1]
        volume_ratio = float(df["volume"].iloc[-1] / avg_vol) if avg_vol > 0 else 1.0

        strength = classify_signal(rsi=rsi, macd_crossover=macd_crossover, volume_ratio=volume_ratio)

        if strength in ("STRONG", "MEDIUM"):
            insert_signal(Signal(
                id=None, symbol=symbol, strength=strength,
                rsi=round(rsi, 2), macd=round(float(macd_line.iloc[-1]), 4),
                volume_ratio=round(volume_ratio, 2),
                extra_indicators="{}", created_at=datetime.now(tz=MARKET_TZ),
            ))
            logger.info(f"Signal {strength} for {symbol} RSI:{rsi:.1f} Vol:{volume_ratio:.2f}")
            return strength

        return None
    except Exception as e:
        logger.error(f"Error scanning {symbol}: {e}")
        return None


def run_scan(ib_client):
    now = datetime.now(tz=MARKET_TZ)
    if not _is_market_hours(now):
        logger.debug("Outside market hours - skipping scan")
        return
    symbols = get_approved_symbols()
    logger.info(f"Scanning {len(symbols)} symbols")
    for symbol in symbols:
        scan_symbol(symbol, ib_client)
