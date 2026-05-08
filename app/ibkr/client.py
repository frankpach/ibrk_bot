import asyncio
import threading

from ib_insync import IB, Stock

from app.config.settings import (
    IB_HOST,
    IB_PORT,
    IB_CLIENT_ID,
    MARKET_DATA_TYPE,
    READ_ONLY,
)
from app.ibkr.contract_factory import build_contract


class IBKRClient:
    """
    All ib_insync calls run inside a dedicated thread that owns the event loop.
    Public methods are fully sync-safe from any calling thread.
    """

    def __init__(self, client_id: int = None):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.ib = IB()
        self._lock = threading.Lock()
        self._client_id = client_id if client_id is not None else IB_CLIENT_ID
        self._run_sync(self._connect_async())

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_sync(self, coro):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=30)

    async def _connect_async(self):
        if not self.ib.isConnected():
            await self.ib.connectAsync(
                host=IB_HOST,
                port=IB_PORT,
                clientId=self._client_id,
                readonly=READ_ONLY,
            )
            # sendMsg must run inside the loop thread — call via loop directly
            self._loop.call_soon(
                lambda: self.ib.reqMarketDataType(MARKET_DATA_TYPE)
            )

    async def _get_price_async(
        self,
        symbol: str,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> dict:
        await self._connect_async()
        contract = build_contract(symbol, sec_type, exchange, currency)
        # qualifyContractsAsync is a true coroutine — safe to await inside loop
        await self.ib.qualifyContractsAsync(contract)
        ticker = self.ib.reqMktData(contract)
        await asyncio.sleep(5)
        self.ib.cancelMktData(contract)
        return {
            "symbol": symbol.upper(),
            "market_price": ticker.marketPrice(),
            "last": ticker.last,
            "bid": ticker.bid,
            "ask": ticker.ask,
        }

    def get_stock_price(
        self,
        symbol: str,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> dict:
        with self._lock:
            return self._run_sync(
                self._get_price_async(symbol, sec_type, exchange, currency)
            )

    async def _get_account_async(self) -> dict:
        await self._connect_async()
        summary = await self.ib.accountSummaryAsync()
        result = {"net_liquidation": 0.0, "buying_power": 0.0, "cash_balance": 0.0, "currency": "USD"}
        for item in summary:
            if item.tag == "NetLiquidation":
                result["net_liquidation"] = float(item.value)
                result["currency"] = item.currency
            elif item.tag == "BuyingPower":
                result["buying_power"] = float(item.value)
            elif item.tag == "TotalCashValue":
                result["cash_balance"] = float(item.value)
        return result

    def get_account(self) -> dict:
        with self._lock:
            return self._run_sync(self._get_account_async())

    async def _get_portfolio_async(self) -> list:
        await self._connect_async()
        items = self.ib.portfolio()
        return [
            {
                "symbol": item.contract.symbol,
                "quantity": item.position,
                "avg_cost": item.averageCost,
                "market_value": item.marketValue,
                "unrealized_pnl": item.unrealizedPNL,
            }
            for item in items
        ]

    def get_portfolio(self) -> list:
        with self._lock:
            return self._run_sync(self._get_portfolio_async())

    async def _place_order_async(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> dict:
        await self._connect_async()
        from ib_insync import Order
        contract = build_contract(symbol, sec_type, exchange, currency)
        await self.ib.qualifyContractsAsync(contract)
        order = Order(
            action=action.upper(),
            totalQuantity=quantity,
            orderType=order_type.upper(),
        )
        if order_type.upper() == "LMT":
            if limit_price is None:
                raise ValueError("limit_price is required for LMT orders")
            order.lmtPrice = float(limit_price)
        trade = self.ib.placeOrder(contract, order)
        await asyncio.sleep(1)
        return {
            "order_id": str(trade.order.orderId),
            "symbol": symbol.upper(),
            "action": action.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "status": trade.orderStatus.status,
        }

    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> dict:
        with self._lock:
            return self._run_sync(
                self._place_order_async(
                    symbol, action, quantity, order_type,
                    limit_price, sec_type, exchange, currency,
                )
            )

    def disconnect(self):
        async def _disc():
            if self.ib.isConnected():
                self.ib.disconnect()
        self._run_sync(_disc())
