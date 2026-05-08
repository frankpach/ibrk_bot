from ib_insync import IB
import asyncio

async def close_orphan():
    ib = IB()
    await ib.connectAsync('127.0.0.1', 4002, clientId=99, timeout=10)
    
    # Get positions
    positions = ib.positions()
    print(f"Positions: {len(positions)}")
    for p in positions:
        print(f"  {p.contract.symbol}: {p.position}")
    
    # Close AAPL if open
    aapl = [p for p in positions if p.contract.symbol == 'AAPL']
    if aapl:
        pos = aapl[0]
        from ib_insync import MarketOrder
        order = MarketOrder('SELL', abs(pos.position))
        trade = ib.placeOrder(pos.contract, order)
        print(f"Close order sent: SELL {abs(pos.position)} AAPL")
        await asyncio.sleep(2)
        print(f"Order status: {trade.orderStatus.status}")
    else:
        print("No AAPL position found")
    
    ib.disconnect()

asyncio.run(close_orphan())
