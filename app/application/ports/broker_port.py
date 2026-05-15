# app/application/ports/broker_port.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from app.domain.trading.value_objects import Order, OrderResult, Position, AccountSummary


class IBrokerPort(ABC):
    @abstractmethod
    def get_price(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Decimal:
        ...

    @abstractmethod
    def place_order(self, order: Order) -> OrderResult:
        ...

    @abstractmethod
    def get_portfolio(self) -> list[Position]:
        ...

    @abstractmethod
    def get_account(self) -> AccountSummary:
        ...

    @abstractmethod
    def get_prev_close(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Decimal:
        ...

    @abstractmethod
    def reconnect(self, port: int = 4002) -> None:
        ...
