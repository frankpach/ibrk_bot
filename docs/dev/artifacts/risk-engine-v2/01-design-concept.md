# Design Concept: risk-engine-v2

## Problem Statement

El motor de riesgo actual es estático y no adaptativo:
- Stop-loss y take-profit son fijos al entrar, nunca se ajustan.
- El tamaño de posición usa fórmula lineal simple sin considerar win rate histórico ni volatilidad actual.
- No hay filtro de régimen de mercado: opera igual cuando VIX=12 que cuando VIX=40.
- No hay filtro de hora del día: entra a las 9:31 AM (opening volatility) igual que a las 11:00 AM.
- El slippage no se considera en el cálculo de riesgo.
- Las órdenes de entrada siempre son MKT, sin awareness de spread.

Esto resulta en:
- Stops tocados por ruido del opening (churn).
- Ganancias que se evaporan porque no se protegen (no trailing stop).
- Posiciones demasiado grandes en alta volatilidad (sobreapalancamiento implícito).

## Solution

Un motor de riesgo adaptativo con:
1. **Trailing Stop + Breakeven Stop**: protege ganancias flotantes.
2. **Dynamic Position Sizing**: ajusta tamaño por win rate, volatilidad (ATR%), y confianza del score.
3. **Market Regime Filter**: usa VIX para ajustar SL, TP, y tamaño de posición.
4. **Time-of-Day Filter**: evita entradas en opening chop y mid-day low volume.
5. **Slippage Buffer**: reduce tamaño de posición para compensar slippage estimado.
6. **LMT orders para entradas**: MKT solo para emergencias/salidas.

## Target Users

- **Sistema Autónomo (Bot)**: Aplica reglas de riesgo antes de cada orden.
- **Frank (Trader)**: Observa mejor P&L y menos stops por ruido.

## Key Differentiators

- Riesgo realista: slippage buffer hace que el 2% de riesgo sea creíble.
- Protección de ganancias: trailing stop mejora el risk/reward efectivo.
- Filtro macro: no operar en crisis = evitar catastrofes.
- Filtro temporal: evitar el 70% de entradas que terminan en stop por chop.

## Out of Scope

- Machine learning para predicción de movimiento.
- Options greeks o hedging con opciones.
- Portfolio-level optimization (Markowitz, etc.).

## Success Metrics

- Reducción de stops tocados por ruido (opening/mid-day) en 40%.
- Mejora del profit factor de 1.2 a > 1.5.
- 0 operaciones en días con VIX > 35 (si no hay short permitido).
- Tiempo medio en trades ganadores aumenta (trailing stop funciona).

## Open Questions

- ¿Short selling está permitido en el sistema? (Afecta VIX filter).
- ¿Qué数据源 para VIX? IBKR tiene VIX como símbolo.
- ¿Ajustar parámetros de régimen manualmente o dejar que el post-mortem los aprenda?
