# app/notifications/telegram.py
"""
Telegram bot para notificaciones de trading y aprobacion humana de ordenes live.

Paper mode: notifica sin esperar respuesta.
Live mode: envia botones Aprobar/Cancelar, espera TELEGRAM_APPROVAL_TIMEOUT_SECONDS.
           Si no hay respuesta cancela automaticamente.
"""
import logging
import time

from app.config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_APPROVAL_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


def _get_bot():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing")
        return None
    from telegram import Bot
    return Bot(token=TELEGRAM_BOT_TOKEN)


def notify(message: str, message_type: str = "generic") -> bool:
    """Envia notificacion simple sin esperar respuesta. Retorna True si enviado."""
    from app.notifications.policy import get_policy
    policy = get_policy()
    if not policy.should_notify(message_type):
        logger.debug(f"Notification suppressed by policy: {message_type}")
        return False

    bot = _get_bot()
    if not bot:
        return False
    try:
        import asyncio
        from telegram.error import TelegramError
        asyncio.run(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="HTML"))
        logger.info(f"Telegram notification sent: {message[:80]}")
        return True
    except Exception as e:
        logger.error(f"Telegram notify failed: {e}")
        return False


def request_approval(
    symbol: str,
    action: str,
    units: int,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
    estimated_risk_usd: float,
) -> bool:
    """
    Envia mensaje con botones Aprobar/Cancelar y espera respuesta.
    Retorna True si aprobado, False si cancelado o timeout.
    """
    bot = _get_bot()
    if not bot:
        logger.warning("Telegram not configured — auto-rejecting order")
        return False

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    result = {"approved": False}

    message = (
        f"Nueva orden pendiente de aprobacion\n\n"
        f"Simbolo: <b>{symbol}</b>\n"
        f"Accion: <b>{action}</b>\n"
        f"Unidades: <b>{units}</b>\n"
        f"Precio entrada: <b>${entry_price:.2f}</b>\n"
        f"Stop-loss: <b>${stop_loss_price:.2f}</b>\n"
        f"Take-profit: <b>${take_profit_price:.2f}</b>\n"
        f"Riesgo estimado: <b>${estimated_risk_usd:.2f}</b>\n\n"
        f"Tienes {TELEGRAM_APPROVAL_TIMEOUT_SECONDS // 60} minutos para responder."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Aprobar", callback_data=f"approve_{symbol}"),
            InlineKeyboardButton("Cancelar", callback_data=f"cancel_{symbol}"),
        ]
    ])

    try:
        import asyncio

        async def send_message():
            msg = await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return msg.message_id

        msg_id = asyncio.run(send_message())
        logger.info(f"Approval request sent for {symbol} {action}, message_id={msg_id}")

        deadline = time.time() + TELEGRAM_APPROVAL_TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                async def check_updates():
                    updates = await bot.get_updates(timeout=10, allowed_updates=["callback_query"])
                    for update in updates:
                        if update.callback_query:
                            data = update.callback_query.data
                            if data == f"approve_{symbol}":
                                result["approved"] = True
                                return True
                            elif data == f"cancel_{symbol}":
                                result["approved"] = False
                                return True
                    return False

                if asyncio.run(check_updates()):
                    break
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                time.sleep(5)

        if result["approved"]:
            notify(f"Orden <b>{action} {units} {symbol}</b> aprobada. Ejecutando...")
        else:
            notify(f"Orden <b>{action} {units} {symbol}</b> cancelada (timeout o rechazo).")

        return result["approved"]

    except Exception as e:
        logger.error(f"Telegram approval request failed: {e}")
        return False
