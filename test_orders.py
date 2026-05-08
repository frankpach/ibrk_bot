import json
import urllib.request

# Test 1: Preview BUY order
print("="*60)
print("TEST 1: Preview BUY order AAPL")
print("="*60)

preview_data = {
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 1,
    "order_type": "MKT",
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.06
}

req = urllib.request.Request(
    'http://127.0.0.1:8088/orders/preview',
    data=json.dumps(preview_data).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode('utf-8'))
        print(f"Status: {response.status}")
        print(f"Approved: {result.get('approved')}")
        print(f"Units: {result.get('recommended_units')}")
        print(f"Entry: ${result.get('current_price')}")
        print(f"SL: ${result.get('stop_loss_price')}")
        print(f"TP: ${result.get('take_profit_price')}")
        print(f"Risk: ${result.get('estimated_risk_usd')}")
        if result.get('reasons'):
            print(f"Reasons: {result.get('reasons')}")
except Exception as e:
    print(f"ERROR: {e}")

print()
