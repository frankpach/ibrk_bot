# app/notifications/approval.py
"""ApprovalManager — async non-blocking order approval via Telegram callbacks."""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PendingApproval:
    symbol: str
    action: str
    units: float
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    estimated_risk_usd: float
    deadline: float
    approved: Optional[bool] = None
    message_id: Optional[int] = None


class ApprovalManager:
    """
    Async approval system using Telegram CallbackQueryHandler.
    Replaces synchronous polling loop.
    """

    def __init__(self, bot=None, chat_id: str | None = None, timeout: int = 300):
        self.bot = bot
        self.chat_id = chat_id
        self.timeout = timeout
        self._pending: dict[str, PendingApproval] = {}

    def register_bot(self, bot, chat_id: str):
        """Register bot instance."""
        self.bot = bot
        self.chat_id = chat_id

    async def request_approval(
        self,
        symbol: str,
        action: str,
        units: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        estimated_risk_usd: float,
    ) -> bool:
        """
        Send approval request and wait for callback.
        Returns True if approved, False if rejected or timeout.
        """
        if self.bot is None or self.chat_id is None:
            logger.warning("Bot not configured, auto-rejecting")
            return False

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        symbol = symbol.upper()
        deadline = time.time() + self.timeout

        pending = PendingApproval(
            symbol=symbol,
            action=action,
            units=units,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            estimated_risk_usd=estimated_risk_usd,
            deadline=deadline,
        )
        self._pending[symbol] = pending

        message = (
            f"Nueva orden pendiente de aprobacion\n\n"
            f"Simbolo: <b>{symbol}</b>\n"
            f"Accion: <b>{action}</b>\n"
            f"Unidades: <b>{units}</b>\n"
            f"Precio entrada: <b>${entry_price:.2f}</b>\n"
            f"Stop-loss: <b>${stop_loss_price:.2f}</b>\n"
            f"Take-profit: <b>${take_profit_price:.2f}</b>\n"
            f"Riesgo estimado: <b>${estimated_risk_usd:.2f}</b>\n\n"
            f"Tienes {self.timeout // 60} minutos para responder."
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Aprobar", callback_data=f"approve_{symbol}"),
                InlineKeyboardButton("Cancelar", callback_data=f"cancel_{symbol}"),
            ]
        ])

        try:
            msg = await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            pending.message_id = msg.message_id
            logger.info(f"Approval request sent for {symbol} {action}")
        except Exception as e:
            logger.error(f"Failed to send approval request: {e}")
            del self._pending[symbol]
            return False

        # Wait for callback or timeout
        check_interval = 0.5
        elapsed = 0
        while elapsed < self.timeout:
            if pending.approved is not None:
                break
            await asyncio.sleep(check_interval)
            elapsed += check_interval

        # Handle result
        if pending.approved is True:
            await self._update_message(symbol, "✅ Aprobado", "Orden ejecutada.")
            del self._pending[symbol]
            return True
        elif pending.approved is False:
            await self._update_message(symbol, "❌ Cancelado", "Orden cancelada por usuario.")
            del self._pending[symbol]
            return False
        else:
            # Timeout
            await self._update_message(symbol, "⏱ Timeout", "Orden cancelada por timeout.")
            del self._pending[symbol]
            return False

    async def handle_callback(self, update, context) -> None:
        """Handle Telegram callback query."""
        query = update.callback_query
        if query is None:
            return

        data = query.data
        if not data:
            return

        # Parse callback data
        parts = data.split("_", 1)
        if len(parts) != 2:
            return

        action_type, symbol = parts
        symbol = symbol.upper()

        # Verify this is a pending approval
        pending = self._pending.get(symbol)
        if pending is None:
            await query.answer("Orden ya no esta pendiente.")
            return

        if action_type == "approve":
            pending.approved = True
            await query.answer("Orden aprobada!")
        elif action_type == "cancel":
            pending.approved = False
            await query.answer("Orden cancelada.")

    async def _update_message(self, symbol: str, status: str, detail: str) -> None:
        """Update the original Telegram message with result."""
        pending = self._pending.get(symbol)
        if pending is None or pending.message_id is None:
            return

        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=pending.message_id,
                text=f"<b>{symbol}</b> — {status}\n{detail}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to update message: {e}")

    def get_pending(self) -> dict:
        """Get pending approvals (for debugging)."""
        return self._pending.copy()


# Singleton
_approval_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager
