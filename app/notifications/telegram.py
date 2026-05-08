# app/notifications/telegram.py
"""Notificaciones vía Telegram (opcional)."""
import logging
import os

from app.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def request_approval(
    symbol: str,
    action: str,
    units: int,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
    estimated_risk_usd: float,
    timeout_sec: int = 300,
) -> bool:
    """Solicita aprobación humana vía Telegram.

    Si no está configurado, retorna True automáticamente (modo autónomo).
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured – auto-approving order")
        return True

    try:
        import httpx
        msg = (
            f"🚨 *Aprobación requerida*\n"
            f"*{action}* {units} x {symbol} @ ${entry_price}\n"
            f"SL: ${stop_loss_price} | TP: ${take_profit_price}\n"
            f"Riesgo estimado: ${estimated_risk_usd:.2f}\n\n"
            f"Responde /approve o /reject en {timeout_sec}s"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        httpx.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        # TODO: implementar polling de respuesta real
        logger.info("Telegram approval requested (auto-approving for now)")
        return True
    except Exception as e:
        logger.error(f"Telegram approval failed: {e}")
        return False
