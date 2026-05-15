# app/llm/loop.py
"""
Procesa señales técnicas pendientes pasándolas por el LLM y ejecutando órdenes.
Corre cada 15 min via APScheduler en run.py.
"""
from datetime import datetime

import structlog

from app.infrastructure.db.compat import get_pending_signals, get_open_trades, mark_signal_processed, insert_trade
from app.llm.agent import LLMDecision, analyze_signal
from app.application.ports.broker_port import IBrokerPort
from app.application.ports.notification_port import INotificationPort
from app.domain.trading.value_objects import Order

logger = structlog.get_logger(__name__)


class LLMSignalProcessor:
    """Processes pending LLM signals. All dependencies injected via constructor."""

    def __init__(self, broker: IBrokerPort, notifier: INotificationPort, dedup) -> None:
        self._broker = broker
        self._notifier = notifier
        self._dedup = dedup

    def process_pending_signals(self) -> None:
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
                self._notifier.notify(
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

                order_placed = False
                if decision.action in ("BUY", "SELL"):
                    self._notifier.notify(
                        f"LLM decide: <b>{decision.action} {signal.symbol}</b> [{decision.confidence}]\n"
                        f"SL: {decision.stop_loss_pct:.1%} | TP: {decision.take_profit_pct:.1%}\n"
                        f"{decision.justification}"
                    )
                    order_placed = self._execute_order(signal.symbol, decision)
                else:
                    self._notifier.notify(
                        f"LLM ignora señal <b>{signal.symbol}</b>\n"
                        f"{decision.justification}"
                    )
                    logger.info(f"LLM ignored signal for {signal.symbol}: {decision.justification}")
                    order_placed = True  # Procesada correctamente aunque no haya orden

            except Exception as e:
                logger.error(f"Error processing signal {signal.id} for {signal.symbol}: {e}")
                self._notifier.notify(f"Error procesando señal <b>{signal.symbol}</b>: {e}")
                # No marcamos como procesada para reintentar en el proximo ciclo
                continue

            if order_placed:
                mark_signal_processed(signal.id)
            else:
                logger.warning(f"Signal {signal.id} {signal.symbol} not marked processed — order failed")

    def _execute_order(self, symbol: str, decision: LLMDecision) -> bool:
        """Envía la orden directamente via IBrokerPort."""
        from app.config.settings import (
            ENTRY_SLIPPAGE_BUFFER, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD,
            REQUIRE_HUMAN_APPROVAL, PAPER_TRADING_ONLY, MARKET_TZ,
        )
        from app.api.capital import get_operating_capital
        from app.risk.validator import validate_order
        from app.risk.lmt_orders import calculate_limit_price
        from app.ibkr.dedup import PreflightChecker
        from app.notifications.order_monitor import OrderExecutionMonitor
        from app.db.models import Trade

        symbol = symbol.upper()
        order_type = "LMT"
        limit_price = None

        try:
            price_data = self._broker.get_price(symbol)
            current_price = float(price_data)
        except Exception as exc:
            logger.warning(f"Could not fetch price for {symbol}: {exc}")
            order_type = "MKT"
            current_price = 0.0

        if current_price and decision.action == "BUY":
            limit_price = round(current_price * (1 + ENTRY_SLIPPAGE_BUFFER), 2)
        elif current_price and decision.action == "SELL":
            limit_price = round(current_price * (1 - ENTRY_SLIPPAGE_BUFFER), 2)

        try:
            account = self._broker.get_account()
            capital = get_operating_capital(account.net_liquidation)
        except Exception as exc:
            logger.warning(f"Could not fetch account: {exc}")
            capital = 500.0

        try:
            portfolio = self._broker.get_portfolio()
            active_positions = len(portfolio)
        except Exception as exc:
            logger.warning(f"Could not fetch portfolio: {exc}")
            active_positions = 0

        result = validate_order(
            symbol=symbol, action=decision.action, quantity=1,
            order_type=order_type, stop_loss_pct=decision.stop_loss_pct,
            capital=capital, active_positions=active_positions,
            now=datetime.now(tz=MARKET_TZ),
        )

        max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
        max_position_usd = min(max_risk_usd / decision.stop_loss_pct, MAX_POSITION_USD) if decision.stop_loss_pct > 0 else 0
        units = max_position_usd / current_price if current_price > 0 else 0.0
        units = round(units, 4)
        buying_power = account.buying_power
        estimated_cost = units * current_price

        if units <= 0:
            self._notifier.notify(f"Preview <b>{symbol}</b>: tamaño de posición = 0 (precio muy alto para capital)")
            logger.warning(f"Preview {symbol}: units = 0")
            return False
        if estimated_cost > buying_power:
            self._notifier.notify(f"Preview <b>{symbol}</b>: sin buying power suficiente")
            logger.warning(f"Preview {symbol}: insufficient buying power")
            return False

        if not result.approved:
            self._notifier.notify(f"Orden rechazada <b>{symbol}</b>:\n" + "\n".join(f"• {x}" for x in result.reasons))
            logger.warning(f"Order rejected by risk validator for {symbol}: {result.reasons}")
            return False

        entry_order_type = order_type.upper()
        if entry_order_type == "MKT":
            limit_price = calculate_limit_price(current_price, decision.action)
            entry_order_type = "LMT"

        # Pre-flight checks
        from app.ibkr.client import get_client as _get_ib_client
        ib_client = _get_ib_client()
        preflight = PreflightChecker(ib_client).check(symbol, decision.action, units, entry_order_type, limit_price)
        if not preflight.ok:
            self._notifier.notify(f"Preflight falló <b>{symbol}</b>: {preflight.reason}")
            logger.error(f"Preflight failed for {symbol}: {preflight.reason}")
            return False

        # Deduplication
        if self._dedup.is_duplicate(symbol, decision.action):
            self._notifier.notify(f"Orden duplicada bloqueada <b>{symbol}</b>")
            logger.warning(f"Duplicate order blocked for {symbol}")
            return False

        # Place and monitor order
        monitor = OrderExecutionMonitor(ib_client)
        order = Order(
            symbol=symbol,
            action=decision.action,
            quantity=units,
            order_type=entry_order_type,
            limit_price=limit_price,
        )
        order_result = monitor.place_and_monitor(
            symbol=symbol,
            action=decision.action,
            quantity=units,
            order_type=entry_order_type,
            limit_price=limit_price,
        )

        if not order_result.success:
            self._notifier.notify(f"Fallo al colocar orden <b>{symbol}</b>: {order_result.reason}")
            logger.error(f"Order placement failed for {symbol}: {order_result.reason}")
            return False

        self._dedup.record(symbol, decision.action)
        fill_price = order_result.fill_price or current_price

        # Insert trade
        price_for_sl = fill_price or current_price
        if decision.action == "BUY":
            stop_loss_price = round(price_for_sl * (1 - decision.stop_loss_pct), 2)
            take_profit_price = round(price_for_sl * (1 + decision.take_profit_pct), 2)
        else:
            stop_loss_price = round(price_for_sl * (1 + decision.stop_loss_pct), 2)
            take_profit_price = round(price_for_sl * (1 - decision.take_profit_pct), 2)

        insert_trade(Trade(
            id=None, symbol=symbol, action=decision.action, quantity=units,
            entry_price=price_for_sl, stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price, stop_loss_pct=decision.stop_loss_pct,
            take_profit_pct=decision.take_profit_pct, signal_strength="MANUAL",
            llm_justification="Placed via signal loop", status="OPEN",
            exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
            opened_at=datetime.now(tz=MARKET_TZ), closed_at=None,
            order_id=order_result.order_id,
            trade_status="FILLED",
            entry_fill_price=fill_price,
            remaining_quantity=units,
        ))

        self._notifier.notify(
            f"Orden ejecutada: <b>{decision.action} {units} {symbol}</b>\n"
            f"Entrada: ${price_for_sl}\n"
            f"Stop-loss: ${stop_loss_price}\n"
            f"Take-profit: ${take_profit_price}\n"
            f"Order ID: {order_result.order_id}"
        )
        logger.info(f"Order placed: {symbol} {decision.action} {units}")
        return True


def process_pending_signals() -> None:
    """APScheduler entry point. Delegates to Container-wired processor."""
    from app.container import get_container
    c = get_container()
    dedup = c.order_deduplicator
    LLMSignalProcessor(
        broker=c.broker,
        notifier=c.notifier,
        dedup=dedup,
    ).process_pending_signals()
