# app/ibkr/market_hours.py
"""
Parser de liquidHours de IB Gateway.
Convierte el string de IB en intervalos y responde is_liquid_at(hours_str, now).
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


@dataclass
class TradingInterval:
    start: datetime
    end: datetime


def parse_liquid_hours(liquid_hours: str) -> list[TradingInterval]:
    """
    Parsea el string liquidHours de IB en una lista de intervalos.
    Formato: "YYYYMMDD:HHMM-YYYYMMDD:HHMM;YYYYMMDD:CLOSED;..."
    Todos los tiempos se devuelven en ET.
    """
    if not liquid_hours:
        return []

    intervals = []
    for segment in liquid_hours.split(";"):
        segment = segment.strip()
        if not segment or "CLOSED" in segment:
            continue
        try:
            start_str, end_str = segment.split("-")
            start = _parse_ib_datetime(start_str)
            end = _parse_ib_datetime(end_str)
            if start and end:
                intervals.append(TradingInterval(start=start, end=end))
        except Exception as e:
            logger.debug(f"parse_liquid_hours: skip segment {segment!r}: {e}")

    return intervals


def is_liquid_at(liquid_hours: str | None, now: datetime) -> bool:
    """
    Retorna True si  cae dentro de algun intervalo liquido.
    """
    if not liquid_hours:
        return False
    try:
        intervals = parse_liquid_hours(liquid_hours)
        now_et = now.astimezone(ET)
        return any(i.start <= now_et <= i.end for i in intervals)
    except Exception as e:
        logger.error(f"is_liquid_at failed: {e}")
        return False


def _parse_ib_datetime(s: str) -> datetime | None:
    """Convierte 'YYYYMMDD:HHMM' a datetime aware en ET."""
    try:
        date_part, time_part = s.strip().split(":")
        year = int(date_part[:4])
        month = int(date_part[4:6])
        day = int(date_part[6:8])
        hour = int(time_part[:2])
        minute = int(time_part[2:4])
        return datetime(year, month, day, hour, minute, tzinfo=ET)
    except Exception:
        return None
