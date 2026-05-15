# app/application/use_cases/close_position.py
"""ClosePositionUseCase — idempotent position closure."""
from dataclasses import dataclass

from app.application.ports.broker_port import IBrokerPort
from app.application.ports.notification_port import INotificationPort
from app.infrastructure.db.compat import get_open_trades, close_trade
from app.ibkr.dedup import PreflightChecker, get_deduplicator
from app.ibkr.fill_tracker import get_fill_price_fallback


@dataclass
class ClosePositionCommand:
    trade_id: int
    reason: str = "MANUAL_CLOSE"
    requested_by: str = "system"


@dataclass
class ClosePositionResult:
    success: bool
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    error: str = None


class ClosePositionUseCase:
    def __init__(self, broker: IBrokerPort, notifier: INotificationPort = None):
        self._broker = broker
        self._notifier = notifier

    def execute(self, cmd: ClosePositionCommand) -> ClosePositionResult:
        open_trades = get_open_trades()
        trade = next((t for t in open_trades if t.id == cmd.trade_id), None)
        if trade is None:
            # Idempotent: already closed or never existed
            return ClosePositionResult(success=True, error="Trade already closed or not found")

        try:
            price_data = self._broker.get_price(trade.symbol)
            current_price = float(price_data)
        except Exception as exc:
            return ClosePositionResult(success=False, error=f"Could not fetch price: {exc}")

        close_action = "SELL" if trade.action == "BUY" else "BUY"
        qty = trade.remaining_quantity or trade.quantity

        try:
            from app.ibkr.client import get_client
            ib = get_client()
            dedup = get_deduplicator()
            dedup_action = f"{close_action}_{trade.id}_{cmd.reason}"
            if dedup.is_duplicate(trade.symbol, dedup_action):
                return ClosePositionResult(success=False, error="Duplicate close blocked")

            preflight = PreflightChecker(ib).check(trade.symbol, close_action, qty, "MKT")
            if not preflight.ok:
                return ClosePositionResult(success=False, error=f"Preflight failed: {preflight.reason}")

            order_result = ib.place_order(
                symbol=trade.symbol, action=close_action, quantity=qty, order_type="MKT",
            )
            dedup.record(trade.symbol, dedup_action)
            try:
                fill_price = get_fill_price_fallback(ib, order_result.get("order_id", ""), trade.symbol)
            except Exception:
                fill_price = current_price
        except Exception as exc:
            return ClosePositionResult(success=False, error=f"IBKR close failed: {exc}")

        pnl_pct = (fill_price - trade.entry_price) / trade.entry_price
        if trade.action == "SELL":
            pnl_pct = -pnl_pct
        pnl_usd = pnl_pct * trade.entry_price * qty
        close_trade(trade.id, fill_price, cmd.reason, round(pnl_usd, 2), round(pnl_pct, 4), exit_fill_price=fill_price)

        if self._notifier:
            self._notifier.notify(
                f"Posición cerrada: <b>{trade.action} {trade.symbol}</b>\n"
                f"Razón: {cmd.reason}\nP&L: {pnl_pct:.2%} (${pnl_usd:.2f})"
            )
        return ClosePositionResult(success=True, pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4))
