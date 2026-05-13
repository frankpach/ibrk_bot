import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from app.risk.time_filter import TimeFilter, TimeFilterResult

ET = ZoneInfo("America/New_York")


class TestTimeFilter:
    def test_opening_chop_blocked(self):
        f = TimeFilter()
        # 9:35 ET
        dt = datetime(2024, 1, 15, 9, 35, tzinfo=ET)
        result = f.is_entry_allowed(dt)
        assert result.allowed is False
        assert result.reason == "opening_chop"
        assert result.size_multiplier == 0.0

    def test_normal_morning(self):
        f = TimeFilter()
        # 10:30 ET
        dt = datetime(2024, 1, 15, 10, 30, tzinfo=ET)
        result = f.is_entry_allowed(dt)
        assert result.allowed is True
        assert result.reason == "ok"
        assert result.size_multiplier == 1.0

    def test_mid_day_reduced(self):
        f = TimeFilter()
        # 12:00 ET
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=ET)
        result = f.is_entry_allowed(dt)
        assert result.allowed is True
        assert result.reason == "mid_day_reduced"
        assert result.size_multiplier == 0.8

    def test_afternoon_normal(self):
        f = TimeFilter()
        # 15:00 ET
        dt = datetime(2024, 1, 15, 15, 0, tzinfo=ET)
        result = f.is_entry_allowed(dt)
        assert result.allowed is True
        assert result.reason == "ok"

    def test_weekend_blocked(self):
        f = TimeFilter()
        # Saturday
        dt = datetime(2024, 1, 13, 12, 0, tzinfo=ET)
        result = f.is_entry_allowed(dt)
        assert result.allowed is False
        assert result.reason == "weekend"

    def test_get_time_label(self):
        f = TimeFilter()
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=ET)
        label = f.get_time_label(dt)
        assert "Reduced" in label
