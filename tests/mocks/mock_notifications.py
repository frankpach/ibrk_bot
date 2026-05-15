# tests/mocks/mock_notifications.py
from app.application.ports.notification_port import INotificationPort


class MockNotificationAdapter(INotificationPort):
    def __init__(self):
        self.messages: list[str] = []
        self.approval_responses: list[dict] = []

    def notify(self, message: str) -> None:
        self.messages.append(message)

    def request_approval(self, symbol, action, units, entry_price,
                         stop_loss_price, take_profit_price, estimated_risk_usd) -> bool:
        self.approval_responses.append({
            "symbol": symbol, "action": action, "units": units,
        })
        return True
