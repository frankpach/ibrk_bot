from app.ibkr.client import IBKRClient

client = IBKRClient()

print(client.get_stock_price("AAPL"))

client.disconnect()

