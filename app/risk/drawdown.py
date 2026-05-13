# app/risk/drawdown.py
"""DrawdownRecovery — adaptive trading based on current drawdown level."""
import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class RecoveryMode:
    mode: Literal["normal", "cautious", "pause", "paper_only"]
    position_size_mult: float
    min_signal_strength: str  # NONE, WEAK, MEDIUM, STRONG
    entry_blocked: bool


class DrawdownRecovery:
    """
    Adapts trading behavior based on drawdown level:
    - < 5%: normal operation
    - 5-10%: cautious (50% size, only STRONG signals)
    - 10-15%: pause for 24h
    - > 15%: paper trading only
    """

    THRESHOLDS = {
        "normal": 0.05,
        "cautious": 0.10,
        "pause": 0.15,
        "paper_only": 0.20,
    }

    MODES = {
        "normal": RecoveryMode("normal", 1.0, "WEAK", False),
        "cautious": RecoveryMode("cautious", 0.5, "STRONG", False),
        "pause": RecoveryMode("pause", 0.0, "STRONG", True),
        "paper_only": RecoveryMode("paper_only", 0.0, "STRONG", True),
    }

    def get_mode(self, drawdown_pct: float) -> RecoveryMode:
        """Determine recovery mode from drawdown percentage."""
        if drawdown_pct < self.THRESHOLDS["normal"]:
            return self.MODES["normal"]
        elif drawdown_pct < self.THRESHOLDS["cautious"]:
            return self.MODES["cautious"]
        elif drawdown_pct < self.THRESHOLDS["pause"]:
            return self.MODES["pause"]
        else:
            return self.MODES["paper_only"]

    def should_block_entry(self, drawdown_pct: float) -> tuple[bool, str]:
        """Check if entries should be blocked."""
        mode = self.get_mode(drawdown_pct)
        if mode.entry_blocked:
            return True, f"Drawdown {drawdown_pct:.1%}: {mode.mode} mode active"
        return False, "ok"

    def get_size_multiplier(self, drawdown_pct: float) -> float:
        """Get position size multiplier."""
        return self.get_mode(drawdown_pct).position_size_mult

    def get_min_signal_strength(self, drawdown_pct: float) -> str:
        """Get minimum required signal strength."""
        return self.get_mode(drawdown_pct).min_signal_strength
