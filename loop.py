# app/llm/loop.py
"""
Procesa señales técnicas pendientes pasándolas por el LLM y ejecutando órdenes.
Corre cada 15 min via APScheduler en run.py.
"""
import logging

import httpx

from app.db.database import get_pending_signals, mark_signal_processed
from app.llm.agent import LLMDecision, analyze_signal

logger = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:8088"


def process_pending_signals():
    """Lee señales STRONG/MEDIUM pendientes y ejecuta el ciclo LLM -> orden."""
    signals = get_pending_signals()
    if not signals:
        logger.debug("No pending signals to process")
        return

    logger.info(f"Processing {len(signals)} pending signal(s)")

    for signal in signals:
        try:
            decision = analyze_signal(
                symbol=signal.symbol,
                strength=signal.strength,
                rsi=signal.rsi,
                macd=signal.macd,
                volume_ratio=signal.volume_ratio,
                signal_id=signal.id,
            )

            if decision.action in ("BUY", "SELL"):
                _execute_order(signal.symbol, decision)
            else:
                logger.info(f"LLM ignored signal for {signal.symbol}: {decision.justification}")

        except Exception as e:
            logger.error(f"Error processing signal {signal.id} for {signal.symbol}: {e}")
        finally:
            mark_signal_processed(signal.id)


def _execute_order(symbol: str, decision: LLMDecision):
    """Envía la orden a FastAPI — el risk validator siempre se aplica ahí."""
    payload = {
        "symbol": symbol,
        "action": decision.action,
        "quantity": 1,
        "order_type": "MKT",
        "stop_loss_pct": decision.stop_loss_pct,
        "take_profit_pct": decision.take_profit_pct,
    }
    try:
        r = httpx.post(f"{API_BASE}/orders/place", json=payload, timeout=30)
        if r.status_code == 403:
            logger.warning(f"Order rejected by risk validator for {symbol}: {r.json()}")
        elif r.status_code == 200:
            result = r.json()
            logger.info(f"Order placed: {symbol} {decision.action} — {result}")
        else:
            logger.error(f"Unexpected status {r.status_code} for {symbol}: {r.text}")
    except Exception as e:
        logger.error(f"Failed to place order for {symbol}: {e}")
