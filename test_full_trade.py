import json
import urllib.request
import time

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
print("TEST COMPLETO: COMPRA -> VERIFICACION -> CIERRE")
print("="*60)

# 1. PLACE ORDER
print("\n[1/6] Colocando orden BUY AAPL...")
order_data = {
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 1,
    "order_type": "MKT",
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.06
}
status, result = api_request('/orders/place', order_data, 'POST')
print(f"Status: {status}")
if status == 200:
    print(f"✅ Orden colocada!")
    print(f"   Order ID: {result.get('order_id')}")
    print(f"   Symbol: {result.get('symbol')}")
    print(f"   Action: {result.get('action')}")
    print(f"   Units: {result.get('units')}")
    print(f"   Entry: ${result.get('entry_price')}")
    print(f"   SL: ${result.get('stop_loss_price')}")
    print(f"   TP: ${result.get('take_profit_price')}")
else:
    print(f"❌ Error: {result}")
    exit(1)

# 2. CHECK OPEN TRADES
print("\n[2/6] Verificando trades abiertos...")
time.sleep(2)
status, result = api_request('/trades')
if status == 200 and result:
    print(f"✅ Hay {len(result)} trade(s) abierto(s):")
    for t in result:
        print(f"   ID: {t.get('id')} | {t.get('symbol')} | {t.get('action')} | Qty: {t.get('quantity')} | Status: {t.get('status')}")
else:
    print(f"⚠️ No hay trades abiertos o error: {result}")

# 3. CHECK PORTFOLIO
print("\n[3/6] Verificando portfolio...")
time.sleep(2)
status, result = api_request('/portfolio')
if status == 200:
    print(f"✅ Portfolio tiene {len(result)} posicion(es):")
    for p in result:
        print(f"   {p.get('symbol')}: {p.get('quantity')} @ ${p.get('avg_cost', 0):.2f} (Market: ${p.get('market_price', 0):.2f})")
else:
    print(f"⚠️ Error: {result}")

# 4. CLOSE POSITION
print("\n[4/6] Cerrando posicion AAPL...")
time.sleep(2)
status, result = api_request('/orders/close/AAPL', method='POST')
if status == 200:
    print(f"✅ Posicion cerrada!")
    print(f"   Symbol: {result.get('symbol')}")
    print(f"   Exit: ${result.get('exit_price')}")
    print(f"   P&L: ${result.get('pnl_usd')}")
else:
    print(f"❌ Error al cerrar: {result}")

# 5. VERIFY TRADES CLOSED
print("\n[5/6] Verificando trades cerrados...")
time.sleep(2)
status, result = api_request('/trades/closed')
if status == 200 and result:
    print(f"✅ Hay {len(result)} trade(s) cerrado(s):")
    for t in result[:3]:
        print(f"   ID: {t.get('id')} | {t.get('symbol')} | {t.get('action')} | P&L: ${t.get('pnl_usd')} | Reason: {t.get('exit_reason')}")
else:
    print(f"⚠️ No hay trades cerrados: {result}")

# 6. FINAL PORTFOLIO
print("\n[6/6] Portfolio final...")
time.sleep(2)
status, result = api_request('/portfolio')
if status == 200:
    aapl_pos = [p for p in result if p.get('symbol') == 'AAPL']
    if aapl_pos:
        print(f"⚠️ AAPL aun en portfolio: {aapl_pos[0].get('quantity')}")
    else:
        print(f"✅ AAPL ya no esta en el portfolio")

print("\n" + "="*60)
print("TEST COMPLETADO")
print("="*60)
