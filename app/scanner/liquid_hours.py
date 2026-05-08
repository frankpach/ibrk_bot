"""Schedule/window evaluator for trading sessions.

Supported liquid_hours codes:
- None or "24x7"  -> always liquid (CRYPTO behaviour).
- "US_RTH"        -> 09:30-16:00 America/New_York, Mon-Fri.
- "US_EXT"        -> 04:00-20:00 America/New_York, Mon-Fri (pre/post market).
- "FX"            -> Sun 22:00 UTC - Fri 22:00 UTC (continuous).
- "GLOBEX"        -> Sun 23:00 UTC - Fri 22:00 UTC, daily 60-min halt 22-23 UTC.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")


def is_liquid_at(now: datetime, liquid_hours: str | None) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    code = (liquid_hours or "24x7").upper()

    if code == "24X7":
        return True

    if code in {"US_RTH", "US_EXT"}:
        ny = now.astimezone(_NY)
        if ny.weekday() >= 5:  # Sat/Sun
            return False
        t = ny.time()
        if code == "US_RTH":
            return time(9, 30) <= t < time(16, 0)
        return time(4, 0) <= t < time(20, 0)

    if code == "FX":
        utc = now.astimezone(timezone.utc)
        wd = utc.weekday()  # Mon=0 ... Sun=6
        if wd == 5:
            return False
        if wd == 4 and utc.time() >= time(22, 0):
            return False
        if wd == 6 and utc.time() < time(22, 0):
            return False
        return True

    if code == "GLOBEX":
        utc = now.astimezone(timezone.utc)
        wd = utc.weekday()
        if wd == 5:
            return False
        if wd == 4 and utc.time() >= time(22, 0):
            return False
        if wd == 6 and utc.time() < time(23, 0):
            return False
        # Daily 22:00-23:00 UTC halt
        if time(22, 0) <= utc.time() < time(23, 0):
            return False
        return True

    # Unknown code -> conservative: closed
    return False
