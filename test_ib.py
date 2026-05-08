from ib_insync import *

ib = IB()

ib.connect(
    host="127.0.0.1",
    port=4002,
    clientId=2,
    readonly=True,
)

# 3 = delayed data
ib.reqMarketDataType(3)

contract = Stock("AAPL", "SMART", "USD")
ib.qualifyContracts(contract)

ticker = ib.reqMktData(contract)

ib.sleep(5)

print("MARKET PRICE:", ticker.marketPrice())
print("LAST:", ticker.last)
print("DELAYED LAST:", ticker.close)
print("BID:", ticker.bid)
print("ASK:", ticker.ask)

ib.disconnect()
