# app/alerts/manager.py
"""
Gestiona alertas de precio configuradas por el usuario via Telegram.
Verifica cada 2 minutos si el precio se movio mas del umbral.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.notifications.telegram import notify

logger = logging.getLogger(__name__)

from app.config.settings import API_BASE  # noqa: F401


@dataclass
class AlertConfig:
    id: Optional[int]
    symbol: str
    threshold_pct: float  # ej: 0.05 = 5%


def parse_alert_command(symbol: str, threshold_str: str) -> Optional[AlertConfig]:
    """
    Parsea /alerta TSLA 5% y retorna AlertConfig.
    Retorna None si el formato es invalido.
    """
    try:
        pct_str = threshold_str.strip().rstrip("%")
        pct = float(pct_str) / 100.0
        if pct <= 0 or pct > 1.0:
            return None
        return AlertConfig(id=None, symbol=symbol.upper(), threshold_pct=pct)
    except (ValueError, AttributeError):
        return None


def check_alert_triggered(
    alert: AlertConfig,
    current_price: float,
    prev_close: float,
) -> tuple[bool, float]:
    """
    Verifica si el precio se movio mas del umbral vs el cierre anterior.
    Retorna (triggered, pct_change).
    """
    if prev_close <= 0:
        return False, 0.0
    pct_change = (current_price - prev_close) / prev_close
    triggered = abs(pct_change) >= alert.threshold_pct
    return triggered, round(pct_change, 4)


def _get_price_and_prev_close(symbol: str) -> tuple[float, float]:
    """Obtiene precio actual y cierre anterior via FastAPI."""
    try:
        data = httpx.get(f"{API_BASE}/price/free/{symbol}", timeout=15).json()
        current = float(data.get("market_price", 0.0) or 0.0)
        prev_close = float(data.get("close", current) or current)
        return current, prev_close
    except Exception as e:
        logger.error(f"Could not fetch price for {symbol}: {e}")
        return 0.0, 0.0


def check_all_alerts(db_get_alerts, db_mark_triggered):
    """
    Verifica todas las alertas activas y notifica las que se dispararon.
    db_get_alerts: callable -> list[AlertConfig]
    db_mark_triggered: callable(alert_id) -> None
    """
    alerts = db_get_alerts()
    if not alerts:
        return

    for alert in alerts:
        current_price, prev_close = _get_price_and_prev_close(alert.symbol)
        if current_price <= 0:
            continue

        triggered, pct_change = check_alert_triggered(alert, current_price, prev_close)

        if triggered:
            direction = "subio" if pct_change > 0 else "bajo"
            notify(
                f"ALERTA: <b>{alert.symbol}</b> {direction} {abs(pct_change):.1%}\n"
                f"Precio: ${current_price:.2f}\n"
                f"Umbral configurado: {alert.threshold_pct:.0%}"
            )
            db_mark_triggered(alert.id)
            logger.info(f"Alert triggered for {alert.symbol}: {pct_change:.1%}")
