# app/ibkr/client.py
"""Cliente IBKR con fallback a mock para desarrollo y reconexión automática."""
import logging
import os
from typing import Any

from app.config.settings import (
    IB_GATEWAY_HOST, IB_GATEWAY_PORT, IB_CLIENT_ID,
    PAPER_TRADING_ONLY,
)

logger = logging.getLogger(__name__)


class _MockIB:
    """Mock de ib_insync para desarrollo sin conexión a TWS/Gateway."""

    def __init__(self):
        self._connected = False
        self._portfolio: list[dict] = []
        self._orders: list[dict] = []
        self._next_order_id = 1000

    def isConnected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int, clientId: int, timeout: float = 10):
        logger.warning(f"MOCK IB: connect({host}, {port}, {clientId})")
        self._connected = True

    def disconnect(self):
        self._connected = False

    def reqAccountSummary(self, reqId: int, groupName: str, tags: str):
        return []

    def reqPositions(self):
        return []


class IBKRClient:
    """Wrapper sobre ib_insync con reconexión y modo mock."""

    def __init__(self, client_id: int | None = None):
        self.client_id = client_id or IB_CLIENT_ID
        self.ib: Any = None
        self._mock = False
        self._connect()

    def _connect(self):
        try:
            from ib_insync import IB, Stock, MarketOrder, LimitOrder
            self.ib = IB()
            self.ib.connect(IB_GATEWAY_HOST, IB_GATEWAY_PORT, clientId=self.client_id, timeout=10)
            logger.info(f"Connected to IB Gateway {IB_GATEWAY_HOST}:{IB_GATEWAY_PORT}")
        except Exception as exc:
            logger.warning(f"Could not connect to IB Gateway ({exc}). Falling back to MOCK.")
            self.ib = _MockIB()
            self.ib.connect(IB_GATEWAY_HOST, IB_GATEWAY_PORT, self.client_id)
            self._mock = True

    def _ensure_connected(self):
        if not self.ib.isConnected():
            logger.warning("IB disconnected – attempting reconnect...")
            self._connect()

    # ── Precios ──
    def get_stock_price(self, symbol: str) -> dict[str, Any]:
        self._ensure_connected()
        if self._mock:
            import random
            price = round(random.uniform(50, 500), 2)
            return {"market_price": price, "bid": price - 0.01, "ask": price + 0.01, "mock": True}

        from ib_insync import Stock
        contract = Stock(symbol, "SMART", "USD")
        ticker = self.ib.reqMktData(contract, snapshot=True)
        self.ib.sleep(2)
        price = ticker.last or ticker.close or ticker.marketPrice()
        if price is None or price <= 0:
            raise RuntimeError(f"No price data for {symbol}")
        return {"market_price": round(float(price), 2), "bid": ticker.bid, "ask": ticker.ask}

    # ── Cuenta ──
    def get_account(self) -> dict[str, Any]:
        self._ensure_connected()
        if self._mock:
            return {"net_liquidation": 100_000.0, "available_funds": 50_000.0, "mock": True}

        summary = self.ib.accountSummary()
        data = {item.tag: item.value for item in summary}
        return {
            "net_liquidation": float(data.get("NetLiquidation", 0)),
            "available_funds": float(data.get("AvailableFunds", 0)),
            "maint_margin_req": float(data.get("MaintMarginReq", 0)),
        }

    # ── Portafolio ──
    def get_portfolio(self) -> list[dict[str, Any]]:
        self._ensure_connected()
        if self._mock:
            return self.ib._portfolio

        positions = self.ib.positions()
        return [
            {
                "symbol": p.contract.symbol,
                "quantity": int(p.position),
                "market_price": float(p.marketPrice) if p.marketPrice else 0.0,
                "avg_cost": float(p.avgCost) if p.avgCost else 0.0,
            }
            for p in positions
            if p.position != 0
        ]

    # ── Órdenes ──
    def place_order(self, symbol: str, action: str, quantity: int, order_type: str = "MKT", limit_price: float | None = None) -> dict[str, Any]:
        self._ensure_connected()
        if self._mock:
            self.ib._next_order_id += 1
            order_id = str(self.ib._next_order_id)
            self.ib._portfolio.append({
                "symbol": symbol, "quantity": quantity if action == "BUY" else -quantity,
                "market_price": 0.0, "avg_cost": 0.0,
            })
            return {"order_id": order_id, "status": "submitted", "mock": True}

        from ib_insync import Stock, MarketOrder, LimitOrder
        contract = Stock(symbol, "SMART", "USD")
        if order_type.upper() == "MKT":
            order = MarketOrder(action.upper(), quantity)
        elif order_type.upper() == "LMT" and limit_price is not None:
            order = LimitOrder(action.upper(), quantity, limit_price)
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(1)
        return {
            "order_id": trade.order.orderId,
            "status": trade.orderStatus.status if trade.orderStatus else "unknown",
        }

    def close_position(self, symbol: str, quantity: int, action: str, order_type: str = "MKT", limit_price: float | None = None) -> dict[str, Any]:
        """Envía orden de cierre para una posición existente."""
        return self.place_order(symbol, action, quantity, order_type, limit_price)

    # ── Sincronización ──
    def sync_positions(self) -> list[dict[str, Any]]:
        """Retorna posiciones reales de IBKR para sincronizar con DB local."""
        return self.get_portfolio()

    # ── Historial de barras ──
    def req_historical_data(self, symbol: str, duration: str = "30 D", bar_size: str = "1 day") -> list[Any]:
        self._ensure_connected()
        if self._mock:
            import random
            base = random.uniform(50, 500)
            return [
                type("Bar", (), {
                    "close": base + random.uniform(-5, 5),
                    "volume": random.randint(1_000_000, 10_000_000),
                })()
                for _ in range(30)
            ]

        from ib_insync import Stock
        contract = Stock(symbol, "SMART", "USD")
        bars = self.ib.reqHistoricalData(
            contract, endDateTime="", durationStr=duration,
            barSizeSetting=bar_size, whatToShow="TRADES",
            useRTH=True, formatDate=1,
        )
        return bars or []
