# Persona Journey: risk-engine-v2

## Persona 1: Sistema Autónomo (Bot)

**Goal**: Operar con disciplina de riesgo adaptativa, maximizando ganancias y minimizando drawdown.

**Journey: Evaluar entrada en NVDA a las 9:32 AM**

1. **Scanner detecta**: Señal STRONG en NVDA.
2. **Time-of-Day Filter**: 9:32 AM = opening volatility. Bloquea entrada.
3. **Log**: "NVDA entrada bloqueada: opening chop (9:30-10:00). Reintentar en 30 min."
4. **10:05 AM**: Señal sigue válida.
5. **Time-of-Day**: Ahora sí permite entrada.
6. **Market Regime**: VIX = 18 (normal). No hay ajuste.
7. **Dynamic Sizing**: win_rate_NVDA=65%, ATR%=2.8, score=78.
   - Base size: $200 / 2.5% = $8,000 → con capital $500 = 0.625 shares
   - Win rate adj: 0.5 + 0.65 = 1.15x
   - Volatility adj: 2.0 / 2.8 = 0.71x
   - Confidence adj: 78 / 75 = 1.04x
   - Final size: 0.625 × 1.15 × 0.71 × 1.04 = 0.53 shares
8. **Slippage Buffer**: spread = 0.3%. Ajusta LMT a precio + 0.1%.
9. **Orden LMT colocada**: BUY 0.53 NVDA @ $214.95 LMT.

**Journey: Posición AAPL sube +3.5%**

1. **Posición abierta**: AAPL @ $175, SL $170.75 (3%).
2. **Precio actual**: $181.13 (+3.5%).
3. **Breakeven Rule**: 3.5% > 1.5 × 3% = 4.5%? No. No mover SL.
4. **Día siguiente, precio**: $183.75 (+5.0%).
5. **Breakeven Rule**: 5.0% > 4.5%? Sí.
6. **Mover SL**: $175.50 (breakeven + 0.3%).
7. **Notificación**: "AAPL: SL movido a breakeven +0.3% ($175.50). Posición protegida."
8. **Precio cae a $176**: No toca SL.
9. **Precio sube a $190**: 8.6% ganancia.
10. **Trailing Stop**: 8.6% > 3 × 3% = 9%? No (cerca).
11. **Precio sube a $192.5**: 10% ganancia.
12. **Trailing Stop**: 10% > 9%. Activar trailing a 50% de ganancia = $183.75.
13. **Precio cae a $183**: Toca trailing stop.
14. **Cierre automático**: SELL MKT @ $183. Ganancia: +4.6%.

**Pain Points (antes)**
- SL fijo en $170.75: si el precio tocaba $170.50, cerraba con -2.5% cuando había ganado +5%.
- Tamaño fijo: arriesgaba lo mismo en TSLA (ATR 4%) que en SPY (ATR 1%).
- Entradas MKT a las 9:31: slippage de 0.5%-1% en el precio.

## Persona 2: Frank (Trader / Operator)

**Goal**: Ver que el sistema protege su capital y sus ganancias sin intervención manual.

**Journey: Revisar posiciones al mediodía**

1. **/posiciones**: Muestra AAPL con SL dinámico.
   ```
   AAPL: 0.53 acc @ $175.00
   SL actual: $175.50 (breakeven +0.3%) 🔒
   TP original: $185.50
   Trailing: inactivo (necesita +9%)
   P&L flotante: +$4.20
   ```
2. **Frank está tranquilo**: Sabe que si cae, cierra en breakeven, no en pérdida.
3. **No recibe spam**: El sistema no le notifica cada 2 min sobre el precio.

**Journey: Día de alta volatilidad (VIX 32)**

1. **Scanner detecta señal en NVDA**.
2. **Market Regime**: VIX=32 (>25). Entrada bloqueada.
3. **Notificación (una vez)**: "⚠️ Régimen de alta volatilidad (VIX 32). Nuevas entradas pausadas. Posiciones actuales con SL ampliado +50%."
4. **Frank entiende**: El sistema está siendo conservador porque el mercado está loco.
5. **SL ampliado**: NVDA SL pasa de 2.5% a 3.75% para evitar salidas por ruido.

**Device & Environment**
- **Frank**: iPhone, Telegram, revisa 2-3 veces al día.
- **Bot**: Raspberry Pi, APScheduler, IB Gateway.

## Critical Flows

1. `signal_detected` → time_filter → regime_filter → dynamic_size → slippage_buffer → LMT_order.
2. `price_update` → breakeven_check → trailing_check → auto_close_if_triggered.
3. `market_open` → VIX_check → regime_update → notify_if_changed.
4. `position_closed` → postmortem → adjust_win_rate → update_symbol_params.
