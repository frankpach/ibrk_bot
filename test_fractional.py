import json
import urllib.request

API_BASE = 'http://127.0.0.1:8088'

def api_request(endpoint, data=None, method='GET'):
    url = f'{API_BASE}{endpoint}'
    if data:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method=method
        )
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))
    except Exception as e:
        return None, str(e)

print("="*60)
print("TEST: Preview BUY AAPL con capital $500")
print("="*60)

# 1. PREVIEW con fraccionales
print("\n[1/3] Preview de orden BUY AAPL...")
preview_data = {
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 1,
    "order_type": "MKT",
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.06
}
status, result = api_request('/orders/preview', preview_data, 'POST')
print(f"Status: {status}")
if status == 200:
    print(f"Approved: {result.get('approved')}")
    print(f"Current Price: ${result.get('current_price')}")
    print(f"Recommended Units: {result.get('recommended_units')}")
    print(f"Estimated Value: ${result.get('estimated_value')}")
    print(f"Estimated Risk: ${result.get('estimated_risk_usd')}")
    print(f"Stop Loss: ${result.get('stop_loss_price')}")
    print(f"Take Profit: ${result.get('take_profit_price')}")
    units = result.get('recommended_units', 0)
    price = result.get('current_price', 1)
    if units != int(units):
        print(f"\n✅ FRACCIONAL: {units} unidades = ${units * price:.2f} invertidos")
    else:
        print(f"\n⚠️ ENTERO: {units} unidades = ${units * price:.2f} invertidos")
else:
    print(f"❌ Error: {result}")

# 2. Precio de NVDA (mas cara)
print("\n[2/3] Preview de orden BUY NVDA...")
preview_data["symbol"] = "NVDA"
status, result = api_request('/orders/preview', preview_data, 'POST')
if status == 200:
    units = result.get('recommended_units', 0)
    price = result.get('current_price', 1)
    print(f"NVDA @ ${price} -> {units} unidades = ${units * price:.2f}")
    if units != int(units):
        print("✅ Usa fraccionales")
    else:
        print("⚠️ Entero")

# 3. Precio de SPY
print("\n[3/3] Preview de orden BUY SPY...")
preview_data["symbol"] = "SPY"
status, result = api_request('/orders/preview', preview_data, 'POST')
if status == 200:
    units = result.get('recommended_units', 0)
    price = result.get('current_price', 1)
    print(f"SPY @ ${price} -> {units} unidades = ${units * price:.2f}")
    if units != int(units):
        print("✅ Usa fraccionales")
    else:
        print("⚠️ Entero")

print("\n" + "="*60)
