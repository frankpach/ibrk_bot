# app/notifications/policy.py
"""NotificationPolicy — controls notification levels and digest generation."""
import logging
from dataclasses import dataclass
from typing import Literal, Optional

logger = logging.getLogger(__name__)


NotificationLevel = Literal["critical_only", "normal", "verbose"]


@dataclass
class NotificationPolicy:
    level: NotificationLevel = "normal"

    # Message types by level
    CRITICAL_TYPES = {
        "circuit_breaker", "position_closed", "fatal_error",
        "approval_request", "order_failed", "ib_disconnected_long",
    }
    NORMAL_TYPES = CRITICAL_TYPES | {
        "position_opened", "ib_disconnected", "ib_reconnected",
        "daily_digest", "regime_change", "drawdown_alert",
    }

    def should_notify(self, message_type: str) -> bool:
        """Check if a message type should be sent at current level."""
        if self.level == "verbose":
            return True
        if self.level == "critical_only":
            return message_type in self.CRITICAL_TYPES
        # normal
        return message_type in self.NORMAL_TYPES

    def set_level(self, level: NotificationLevel) -> None:
        """Change notification level."""
        if level not in ("critical_only", "normal", "verbose"):
            raise ValueError(f"Invalid level: {level}")
        self.level = level
        logger.info(f"Notification level changed to {level}")


class DigestGenerator:
    """Generates periodic digest summaries instead of individual alerts."""

    def __init__(self):
        self._suppressing = False

    def generate_digest(
        self,
        open_trades: list,
        daily_pnl: float,
        signals_processed: int,
        system_status: str,
    ) -> str:
        """Generate a digest message."""
        lines = ["📊 Resumen del sistema", ""]
        
        if open_trades:
            lines.append(f"Posiciones abiertas: {len(open_trades)}")
            for t in open_trades:
                pnl = getattr(t, 'pnl_usd', None) or 0
                emoji = "🟢" if pnl >= 0 else "🔴"
                lines.append(f"  {emoji} {t.symbol}: ${pnl:.2f}")
        else:
            lines.append("Sin posiciones abiertas")
        
        lines.append("")
        pnl_emoji = "🟢" if daily_pnl >= 0 else "🔴"
        lines.append(f"{pnl_emoji} P&L día: ${daily_pnl:.2f}")
        lines.append(f"Señales procesadas: {signals_processed}")
        lines.append(f"Estado: {system_status}")
        
        return "\n".join(lines)

    def is_suppressed(self, message_type: str) -> bool:
        """Check if non-critical alerts are suppressed during digest window."""
        if not self._suppressing:
            return False
        return message_type not in NotificationPolicy.CRITICAL_TYPES

    def start_suppression(self) -> None:
        """Start suppressing non-critical alerts (during digest)."""
        self._suppressing = True

    def end_suppression(self) -> None:
        """End suppression."""
        self._suppressing = False


# Singletons
_policy_instance: Optional[NotificationPolicy] = None
_digest_instance: Optional[DigestGenerator] = None


def get_policy() -> NotificationPolicy:
    global _policy_instance
    if _policy_instance is None:
        _policy_instance = NotificationPolicy()
    return _policy_instance


def get_digest_generator() -> DigestGenerator:
    global _digest_instance
    if _digest_instance is None:
        _digest_instance = DigestGenerator()
    return _digest_instance
