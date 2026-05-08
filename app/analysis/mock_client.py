# app/analysis/mock_client.py
"""
MockIBClient — same public interface as IBKRClient but never connects to IB.
Activated when IB_MOCK=true in environment. Returns deterministic synthetic data.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import random


@dataclass
class MockBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    barCount: int = 100
    average: float = 0.0


@dataclass
class MockNewsItem:
    time: str
    providerCode: str
    articleId: str
    headline: str
    extraData: str = ""


class MockIBHandle:
    """Mimics the ib_insync IB object interface used by IBDataLayer."""

    def __init__(self):
        self._rng = random.Random(42)  # deterministic seed

    def isConnected(self) -> bool:
        return True

    def reqHistoricalData(
        self,
        contract,
        endDateTime: str,
        durationStr: str,
        barSizeSetting: str,
        whatToShow: str,
        useRTH: bool,
        formatDate: int,
        keepUpToDate: bool = False,
        chartOptions: list = None,
    ) -> list:
        """Returns deterministic synthetic OHLCV bars."""
        rng = random.Random(42)

        # Parse duration to get number of bars
        if "D" in durationStr:
            n = int(durationStr.split()[0])
        elif "W" in durationStr:
            n = int(durationStr.split()[0]) * 5
        else:
            n = 30

        # Base price per symbol
        symbol = getattr(contract, "symbol", "AAPL")
        base_prices = {
            "AAPL": 285.0, "MSFT": 420.0, "SPY": 580.0, "QQQ": 490.0,
            "TSLA": 250.0, "NVDA": 950.0, "AMZN": 195.0, "GOOGL": 175.0,
            "META": 490.0, "JPM": 220.0,
        }
        base = base_prices.get(symbol, 100.0)

        bars = []
        price = base
        base_date = datetime(2026, 4, 1)

        if whatToShow in ("HISTORICAL_VOLATILITY", "OPTION_IMPLIED_VOLATILITY"):
            # Return volatility series (close = volatility value 0.1-0.4)
            for i in range(n):
                d = (base_date + timedelta(days=i)).strftime("%Y%m%d")
                vol = 0.20 + rng.uniform(-0.05, 0.05)
                bars.append(MockBar(
                    date=d, open=vol, high=vol + 0.01, low=vol - 0.01,
                    close=round(vol, 4), volume=0,
                ))
            return bars

        # Standard OHLCV bars
        for i in range(n):
            d = (base_date + timedelta(days=i)).strftime("%Y%m%d")
            change = rng.uniform(-0.02, 0.025)
            price = max(price * (1 + change), base * 0.5)
            high = price * (1 + rng.uniform(0, 0.01))
            low = price * (1 - rng.uniform(0, 0.01))
            vol = int(rng.uniform(500_000, 2_000_000))
            bars.append(MockBar(
                date=d,
                open=round(price * (1 + rng.uniform(-0.005, 0.005)), 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(price, 2),
                volume=vol,
            ))

        return bars

    def reqScannerData(self, subscription, scannerSubscriptionOptions=None, scannerSubscriptionFilterOptions=None) -> list:
        """Returns fixed list of mock scan results."""
        return ["NFLX", "SHOP", "PLTR", "COIN", "RBLX",
                "UBER", "SNAP", "PINS", "DASH", "RKLB"]

    def reqHistoricalNews(self, reqId, conId, providerCodes, startDateTime, endDateTime, totalResults, historicalNewsOptions=None) -> list:
        return [
            MockNewsItem(
                time="2026-05-01 10:00:00",
                providerCode="BRFG",
                articleId="BRFG$123",
                headline="Stock shows strong momentum amid positive market conditions",
            ),
            MockNewsItem(
                time="2026-05-02 09:30:00",
                providerCode="DJNL",
                articleId="DJNL$456",
                headline="Analysts maintain buy rating with revised price target",
            ),
        ]

    def reqFundamentalData(self, contract, reportType, fundamentalDataOptions=None) -> str:
        """Returns minimal XML with earnings date 15 days from now."""
        future_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ReportSnapshot>
  <CalendarData>
    <Earnings>
      <EarningsDate>{future_date}</EarningsDate>
    </Earnings>
  </CalendarData>
</ReportSnapshot>"""

    def accountSummary(self) -> list:
        return []

    async def accountSummaryAsync(self) -> list:
        from ib_insync import AccountValue
        return [
            AccountValue(account="DUM775081", tag="NetLiquidation", value="500.00", currency="USD", modelCode=""),
            AccountValue(account="DUM775081", tag="BuyingPower", value="500.00", currency="USD", modelCode=""),
            AccountValue(account="DUM775081", tag="TotalCashValue", value="500.00", currency="USD", modelCode=""),
        ]

    def portfolio(self) -> list:
        return []

    def placeOrder(self, contract, order):
        """Returns a mock trade object."""
        class MockOrderStatus:
            status = "Submitted"

        class MockOrder:
            orderId = 1

        class MockTrade:
            order = MockOrder()
            orderStatus = MockOrderStatus()

        return MockTrade()

    def reqMarketDataType(self, marketDataType: int):
        pass

    async def qualifyContractsAsync(self, *contracts):
        return list(contracts)

    def cancelOrder(self, order):
        pass

    def disconnect(self):
        pass


class MockIBClient:
    """
    Drop-in replacement for IBKRClient when IB_MOCK=true.
    Never opens network connections. Returns deterministic synthetic data.
    Same public interface as IBKRClient.
    """

    def __init__(self, client_id: int = None):
        self.ib = MockIBHandle()
        self._lock = __import__("threading").Lock()

    def get_stock_price(self, symbol: str) -> dict:
        prices = {
            "AAPL": 287.50, "MSFT": 421.00, "SPY": 581.00, "QQQ": 491.00,
            "TSLA": 252.00, "NVDA": 952.00, "AMZN": 196.00, "GOOGL": 176.00,
            "META": 492.00, "JPM": 221.00,
        }
        price = prices.get(symbol.upper(), 100.0)
        return {
            "symbol": symbol.upper(),
            "market_price": price,
            "last": price,
            "bid": round(price - 0.01, 2),
            "ask": round(price + 0.01, 2),
        }

    def get_account(self) -> dict:
        return {
            "net_liquidation": 500.0,
            "buying_power": 500.0,
            "cash_balance": 500.0,
            "currency": "USD",
        }

    def get_portfolio(self) -> list:
        return []

    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: Optional[float] = None,
    ) -> dict:
        return {
            "order_id": "mock_001",
            "symbol": symbol.upper(),
            "action": action.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            "status": "Submitted",
        }

    def disconnect(self):
        pass
