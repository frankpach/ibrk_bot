import asyncio
import logging
import math
import threading

from ib_insync import IB, Stock

logger = logging.getLogger(__name__)

from app.config.settings import (
    IB_HOST,
    IB_PORT,
    IB_CLIENT_ID,
    MARKET_DATA_TYPE,
    READ_ONLY,
)
from app.ibkr.contract_factory import build_contract


_client_instance = None
_client_lock = threading.Lock()


def _safe_number(value, default: float = 0.0) -> float:
    """Return a JSON-safe float, replacing NaN/inf/None with a default."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(num) or math.isinf(num):
        return default
    return num


class IBKRClient:
    """
    All ib_insync calls run inside a dedicated thread that owns the event loop.
    Public methods are fully sync-safe from any calling thread.

    SINGLETON: use get_client() instead of IBKRClient() to avoid multiple connections.
    """

    def __new__(cls, client_id: int = None):
        global _client_instance
        if _client_instance is not None:
            return _client_instance
        with _client_lock:
            if _client_instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                _client_instance = instance
            return _client_instance

    def __init__(self, client_id: int = None):
        if getattr(self, "_initialized", False):
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.ib = IB()
        self._lock = threading.Lock()
        self._client_id = client_id if client_id is not None else IB_CLIENT_ID
        # Retry connection up to 3 times — clientId may be briefly held by previous instance
        _connected = False
        for attempt in range(3):
            try:
                self._run_sync(self._connect_async())
                _connected = True
                break
            except Exception as e:
                import time
                logger.warning(f"IB Gateway connect attempt {attempt+1}/3 failed: {e}")
                if attempt < 2:
                    time.sleep(5)
        if not _connected:
            logger.error("Could not connect to IB Gateway after 3 attempts — starting in offline mode")
        self._initialized = True

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
        market_price = _safe_number(ticker.marketPrice())
        last = _safe_number(ticker.last)
        bid = _safe_number(ticker.bid)
        ask = _safe_number(ticker.ask)
        if market_price <= 0:
            market_price = last or bid or ask or 0.0
        return {
            "symbol": symbol.upper(),
            "market_price": market_price,
            "last": last,
            "bid": bid,
            "ask": ask,
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
                "quantity": _safe_number(item.position),
                "avg_cost": _safe_number(item.averageCost),
                "market_price": _safe_number(item.marketPrice),
                "market_value": _safe_number(item.marketValue),
                "unrealized_pnl": _safe_number(item.unrealizedPNL),
            }
            for item in items
        ]

    def get_portfolio(self) -> list:
        with self._lock:
            return self._run_sync(self._get_portfolio_async())

    async def _get_executions_async(self, since_days: int = 7) -> list:
        """Retorna fills/ejecuciones reales de IBKR en los ultimos N dias."""
        await self._connect_async()
        from ib_insync import ExecutionFilter
        filt = ExecutionFilter()
        self.ib.reqExecutions(filt)
        await asyncio.sleep(1.5)
        fills = self.ib.fills()
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        result = []
        for f in fills:
            exec_time_str = getattr(f.execution, "time", "")
            try:
                exec_time = datetime.fromisoformat(exec_time_str.replace("Z", "+00:00"))
            except Exception:
                exec_time = cutoff
            if exec_time < cutoff:
                continue
            result.append({
                "symbol": f.contract.symbol,
                "sec_type": f.contract.secType,
                "action": f.execution.side,
                "quantity": f.execution.shares,
                "price": f.execution.price,
                "time": exec_time_str,
                "commission": getattr(f.commissionReport, "commission", 0.0),
                "realized_pnl": getattr(f.commissionReport, "realizedPNL", None),
            })
        result.sort(key=lambda x: x["time"], reverse=True)
        return result

    async def _get_commissions_async(self, since_days: int = 30) -> list:
        """Obtiene historial de comisiones y fees reales de IBKR."""
        await self._connect_async()
        from ib_insync import ExecutionFilter
        filt = ExecutionFilter()
        self.ib.reqExecutions(filt)
        await asyncio.sleep(1.5)
        fills = self.ib.fills()
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        result = []
        total_commission = 0.0
        total_realized_pnl = 0.0
        for f in fills:
            exec_time_str = getattr(f.execution, "time", "")
            try:
                exec_time = datetime.fromisoformat(exec_time_str.replace("Z", "+00:00"))
            except Exception:
                exec_time = cutoff
            if exec_time < cutoff:
                continue
            comm = getattr(f.commissionReport, "commission", 0.0)
            pnl = getattr(f.commissionReport, "realizedPNL", 0.0)
            total_commission += comm
            total_realized_pnl += pnl
            result.append({
                "symbol": f.contract.symbol,
                "action": f.execution.side,
                "quantity": f.execution.shares,
                "price": f.execution.price,
                "time": exec_time_str,
                "commission": round(comm, 2),
                "realized_pnl": round(pnl, 2) if pnl is not None else None,
            })
        result.sort(key=lambda x: x["time"], reverse=True)
        return {
            "fills": result,
            "total_commission": round(total_commission, 2),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "fill_count": len(result),
        }

    def get_commissions(self, since_days: int = 30) -> dict:
        with self._lock:
            return self._run_sync(self._get_commissions_async(since_days))

    def get_executions(self, since_days: int = 7) -> list:
        with self._lock:
            return self._run_sync(self._get_executions_async(since_days))

    async def _place_order_async(
        self,
        symbol: str,
        action: str,
        quantity: float,
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
        quantity: float,
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
        global _client_instance
        _client_instance = None


def get_client() -> IBKRClient:
    """Return the singleton IBKRClient instance."""
    return IBKRClient()
