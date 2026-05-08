# app/llm/loop.py
"""
Procesa señales técnicas pendientes pasándolas por el LLM y ejecutando órdenes.
Corre cada 15 min via APScheduler en run.py.
"""
import logging

import httpx

from app.db.database import get_pending_signals, get_open_trades, mark_signal_processed
from app.llm.agent import LLMDecision, analyze_signal
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)

from app.config.settings import API_BASE  # noqa: F401


def process_pending_signals():
    """Lee señales STRONG/MEDIUM pendientes y ejecuta el ciclo LLM -> orden."""
    signals = get_pending_signals()
    if not signals:
        logger.debug("No pending signals to process")
        return

    logger.info(f"Processing {len(signals)} pending signal(s)")

    # Skip signals for symbols that already have an open position
    open_trades = get_open_trades()
    open_symbols = {t.symbol.upper() for t in open_trades}
    if open_symbols:
        logger.info(f"Open positions (will skip new signals): {open_symbols}")

    for signal in signals:
        if signal.symbol.upper() in open_symbols:
            logger.info(f"Skipping signal for {signal.symbol} — position already open")
            mark_signal_processed(signal.id)
            continue
        try:
            notify(
                f"Señal detectada: <b>{signal.symbol}</b> [{signal.strength}]\n"
                f"RSI: {signal.rsi} | MACD: {signal.macd} | Vol: {signal.volume_ratio}x\n"
                f"Consultando al LLM..."
            )

            decision = analyze_signal(
                symbol=signal.symbol,
                strength=signal.strength,
                rsi=signal.rsi,
                macd=signal.macd,
                volume_ratio=signal.volume_ratio,
                signal_id=signal.id,
            )

            if decision.action in ("BUY", "SELL"):
                notify(
                    f"LLM decide: <b>{decision.action} {signal.symbol}</b> [{decision.confidence}]\n"
                    f"SL: {decision.stop_loss_pct:.1%} | TP: {decision.take_profit_pct:.1%}\n"
                    f"{decision.justification}"
                )
                _execute_order(signal.symbol, decision)
            else:
                notify(
                    f"LLM ignora señal <b>{signal.symbol}</b>\n"
                    f"{decision.justification}"
                )
                logger.info(f"LLM ignored signal for {signal.symbol}: {decision.justification}")

        except Exception as e:
            logger.error(f"Error processing signal {signal.id} for {signal.symbol}: {e}")
            notify(f"Error procesando señal <b>{signal.symbol}</b>: {e}")
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
            detail = r.json()
            reasons = detail.get("detail", {}).get("reasons", [str(detail)])
            notify(f"Orden rechazada <b>{symbol}</b>:\n" + "\n".join(f"• {x}" for x in reasons))
            logger.warning(f"Order rejected by risk validator for {symbol}: {detail}")
        elif r.status_code == 200:
            result = r.json()
            notify(
                f"Orden ejecutada: <b>{decision.action} {result.get('units', '?')} {symbol}</b>\n"
                f"Entrada: ${result.get('entry_price', '?')}\n"
                f"Stop-loss: ${result.get('stop_loss_price', '?')}\n"
                f"Take-profit: ${result.get('take_profit_price', '?')}\n"
                f"Order ID: {result.get('order_id', '?')}"
            )
            logger.info(f"Order placed: {symbol} {decision.action} — {result}")
        else:
            logger.error(f"Unexpected status {r.status_code} for {symbol}: {r.text}")
            notify(f"Error al colocar orden <b>{symbol}</b>: HTTP {r.status_code}")
    except Exception as e:
        logger.error(f"Failed to place order for {symbol}: {e}")
        notify(f"Fallo al colocar orden <b>{symbol}</b>: {e}")
