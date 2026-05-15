# app/application/ports/notification_port.py
from abc import ABC, abstractmethod
from typing import Optional


class INotificationPort(ABC):
    @abstractmethod
    def notify(self, message: str) -> None:
        ...

    @abstractmethod
    def request_approval(self, symbol: str, action: str, units: float, entry_price: float,
                         stop_loss_price: float, take_profit_price: float,
                         estimated_risk_usd: float) -> bool:
        ...
