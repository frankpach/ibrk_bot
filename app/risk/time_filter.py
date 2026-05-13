# app/risk/time_filter.py
"""TimeFilter — filter entries based on time of day and market conditions."""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.config.settings import MARKET_TZ

logger = logging.getLogger(__name__)


@dataclass
class TimeFilterResult:
    allowed: bool
    reason: str
    size_multiplier: float = 1.0


class TimeFilter:
    """
    Filters trade entries by time of day:
    - Opening chop: 9:30-10:00 ET → blocked
    - Mid-day low volume: 11:30-14:00 ET → reduced size (0.8x)
    - Normal: 10:00-11:30, 14:00-16:00 ET → allowed
    """

    OPENING_CHOP_START = (9, 30)
    OPENING_CHOP_END = (10, 0)
    MID_DAY_START = (11, 30)
    MID_DAY_END = (14, 0)

    def is_entry_allowed(self, now: datetime | None = None) -> TimeFilterResult:
        """Check if entry is allowed at given time."""
        if now is None:
            now = datetime.now(tz=MARKET_TZ)
        
        et = now.astimezone(MARKET_TZ)
        hour = et.hour
        minute = et.minute
        time_val = hour * 60 + minute
        
        opening_start = self.OPENING_CHOP_START[0] * 60 + self.OPENING_CHOP_START[1]
        opening_end = self.OPENING_CHOP_END[0] * 60 + self.OPENING_CHOP_END[1]
        midday_start = self.MID_DAY_START[0] * 60 + self.MID_DAY_START[1]
        midday_end = self.MID_DAY_END[0] * 60 + self.MID_DAY_END[1]
        
        # Weekend check
        if et.weekday() >= 5:
            return TimeFilterResult(False, "weekend", 0.0)
        
        # Opening chop
        if opening_start <= time_val < opening_end:
            return TimeFilterResult(False, "opening_chop", 0.0)
        
        # Mid-day reduced
        if midday_start <= time_val < midday_end:
            return TimeFilterResult(True, "mid_day_reduced", 0.8)
        
        # Normal hours
        return TimeFilterResult(True, "ok", 1.0)

    def get_time_label(self, now: datetime | None = None) -> str:
        """Get human-readable time label for current period."""
        result = self.is_entry_allowed(now)
        if not result.allowed:
            return f"Blocked: {result.reason}"
        if result.size_multiplier < 1.0:
            return f"Reduced ({result.size_multiplier:.0%}): {result.reason}"
        return "Normal trading"
