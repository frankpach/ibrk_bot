# app/infrastructure/notifications/telegram_adapter.py
"""TelegramNotificationAdapter — wraps existing policy + throttler + telegram + approval."""
from app.application.ports.notification_port import INotificationPort
from app.notifications.telegram import notify
from app.notifications.approval import get_approval_manager


class TelegramNotificationAdapter(INotificationPort):
    """
    Adapter that wraps the existing notification system (policy, throttler,
    telegram module, approval manager) without rewriting their internals.
    """

    def notify(self, message: str) -> None:
        notify(message)

    def request_approval(
        self,
        symbol: str,
        action: str,
        units: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        estimated_risk_usd: float,
    ) -> bool:
        manager = get_approval_manager()
        # The ApprovalManager uses async methods; bridge to sync for the port
        import asyncio
        try:
            return asyncio.run(
                manager.request_approval(
                    symbol=symbol,
                    action=action,
                    units=units,
                    entry_price=entry_price,
                    stop_loss_price=stop_loss_price,
                    take_profit_price=take_profit_price,
                    estimated_risk_usd=estimated_risk_usd,
                )
            )
        except RuntimeError:
            # If already inside an event loop (e.g. tests), use the sync fallback
            from app.notifications.telegram import request_approval as sync_request_approval
            return sync_request_approval(
                symbol=symbol,
                action=action,
                units=int(units),
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                estimated_risk_usd=estimated_risk_usd,
            )
