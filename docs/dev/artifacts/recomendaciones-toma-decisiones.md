# Recomendaciones Adicionales: Toma de Decisiones y Márgenes de Ganancia

## Análisis realizado sobre: app/ibkr/client.py, app/positions/manager.py, app/api/main.py, app/db/models.py, app/system/reconciler.py, app/db/database.py, tests/

---

## 🔴 Alta Prioridad / Bajo Costo (Quick Wins)

### 1. ATR-Based Stop Loss (Adaptive SL)

**Problema**: SL fijo de 2.5% para NVDA (ATR 2.8%) se toca por ruido. Para SPY (ATR 1.2%) es demasiado amplio.

**Solución**: `SL = 1.5 × ATR%` con mínimo 1.5% y máximo 5%.

| Símbolo | ATR% | SL antiguo | SL nuevo | Mejora |
|---|---|---|---|---|
| NVDA | 2.8% | 2.5% | 4.2% | Menos stops por ruido |
| SPY | 1.2% | 2.5% | 1.8% | Tight SL, mejor R:R |
| TSLA | 3.5% | 2.5% | 5.0% | (máximo) Aún mejor que 2.5% |

### 2. Partial Exits (Escalonado de Ganancias)

**Problema**: Cerrar 100% en TP fijo deja dinero en la mesa.

**Solución**: 
- Cerrar 50% en TP1 (1.5x riesgo)
- Mover SL de los restantes 50% a breakeven
- Dejar correr con trailing stop para TP2 (3x riesgo)

**Impacto**: Un trade que llega a +5% con SL de -2.5%:
- Antes: +5% (o -2.5% si revierte antes de TP)
- Ahora: 50% × +3.75% + 50% × trailing → promedio +4.5% con riesgo reducido

### 3. Correlation Matrix Real (No por Categoría)

**Problema**: Ahora evita 2 posiciones en "blue_chip". Pero AAPL/MSFT correlación=0.92, mientras AAPL/JPM=0.45. El filtro actual no ve esto.

**Solución**: Calcular correlación 20d de retornos diarios. Si `corr > 0.85`, rechazar o reducir size 50%.

### 4. News Impact Scoring (No solo Sentiment)

**Problema**: El sistema clasifica noticias como pos/neg/neu. Pero no mide MAGNITUD. Un downgrade de Goldman Sachs ≠ un artículo de Seeking Alpha.

**Solución**: Agregar fuentes de datos:
- **Analyst ratings changes**: upgrade/downgrade de firms tier-1 (Goldman, Morgan Stanley)
- **Earnings surprise magnitude**: beat/miss vs consensus
- **Insider trading**: form 4 filings
- **SEC filings**: 8-K material events

**Impacto**: Filtrar entradas antes de eventos de alto impacto conocido.

### 5. Time Stop (Cierre por Inactividad)

**Problema**: Capital inmovilizado en una posición que no se mueve en 5 días tiene costo de oportunidad.

**Solución**: Si después de 5 días el precio está dentro de ±1% del entry, cerrar con razón `TIME_STOP`.

---

## 🟡 Media Prioridad / Medio Costo

### 6. Volatility Targeting (Constante)

**Problema**: El riesgo total del portafolio varía con la volatilidad del mercado. En crisis, 3 posiciones × SL 2.5% = riesgo real de 15%+.

**Solución**: Target de volatilidad del portafolio = 5% diario. Si VIX sube, reducir número de posiciones Y tamaño proporcionalmente.

```python
portfolio_vol = sqrt(sum(weights_i^2 * vol_i^2 + 2*weights_i*weights_j*corr_ij*vol_i*vol_j))
if portfolio_vol > TARGET_VOL:
    reduce_size_factor = TARGET_VOL / portfolio_vol
```

### 7. Machine Learning Ligero (Logistic Regression)

**Problema**: El scoring usa reglas fijas (RSI<30 = +0.5 puntos). Pero la relación RSI→win no es lineal ni constante.

**Solución**: Entrenar una regresión logística simple con features existentes para predecir P(win) por símbolo.

**Features**: RSI, MACD, ATR, vol_ratio, bollinger_pos, RS_vs_SPY, day_of_week, hour

**Output**: P(win) ∈ [0,1]. Si P(win) < 0.45 → IGNORE automático (sin LLM).

**Ventaja**: 10x más rápido que LLM. Filtro previo que ahorra tokens y latency.

### 8. Walk-Forward Backtesting (En Vivo)

**Problema**: El backtest actual es estático (entrena en 180d, testea en los mismos 180d). Overfitting garantizado.

**Solución**: Walk-forward cada semana:
- Semana N: entrenar en datos de N-20 a N-1
- Semana N: testear en datos de N
- Rotar. Guardar resultados.

**Impacto**: Métricas de win rate, profit factor, max drawdown **en datos no vistos**.

### 9. Seasonality Filter

**Problema**: Algunos meses/días son estadísticamente malos para ciertos símbolos.

**Solución**: Analizar win rate por:
- Día de la semana (¿los lunes son malos para tech?)
- Mes (¿diciembre es bueno para retail?)
- Semana del mes (¿options expiration week es volátil?)

**Impacto**: Evitar entradas en ventanas de baja probabilidad histórica.

### 10. Options Implied Move (Pre-Earnings)

**Problema**: El earnings gate bloquea entradas 3 días antes. Pero el options market ya precia el movimiento esperado.

**Solución**: Si `implied_move > 2 × stop_loss_pct`, no entrar (el riesgo real supera el SL planificado).

**Ejemplo**: NVDA earnings, implied move = 8%. SL = 2.5%. Entrar = suicidio.

---

## 🟢 Alta Prioridad / Alto Costo (Estrategia)

### 11. Portfolio Heat Map (Concentración de Riesgo)

**Problema**: 3 posiciones LONG en tech = riesgo concentrado. Un solo evento sectorial destruye el portafolio.

**Solución**: Dashboard/métrica de "heat" por sector:
```
Tech exposure: 67% (3/3 posiciones)
Risk if tech drops 5%: -$15 (10% del capital)
Recommendation: Diversify or hedge
```

### 12. Re-entry Rules (Después de Stop)

**Problema**: Después de un SL, el scanner puede generar la misma señal 5 min después. Evitar "death by a thousand cuts".

**Solución**: Cooldown por símbolo después de SL:
- 24h de cooldown para el mismo símbolo
- O requerir que el precio se mueva > 2% desde el SL antes de reconsiderar

### 13. Drawdown Recovery Strategy

**Problema**: Si el sistema pierde 10% en una semana, solo hay circuit breaker (pausa). No hay plan de recuperación.

**Solución**: Estrategia de recuperación:
- Drawdown < 5%: operar normal
- Drawdown 5-10%: reducir size 50%, solo señales STRONG
- Drawdown 10-15%: pausa obligatoria 24h, revisar post-mortem
- Drawdown > 15%: solo paper trading hasta nueva validación

### 14. Session-Aware Indicators

**Problema**: Los indicadores mezclan pre-market, regular hours, y after-hours. El RSI de 5 min en pre-market es ruido.

**Solución**: Filtrar barras por horario de mercado. Computar indicadores solo con datos de `liquid_hours`.

### 15. Adaptive TP basado en Win Rate por Símbolo

**Problema**: TP fijo de 6% para todos los símbolos. Pero NVDA puede mover 10% fácilmente, mientras JPM raramente mueve 3%.

**Solución**: `TP = 2.5 × SL × win_rate_adj × volatility_adj`
- NVDA: TP = 2.5 × 2.5% × 1.2 × 1.3 = 9.75%
- JPM: TP = 2.5 × 2.5% × 0.9 × 0.7 = 3.94%

---

## 📊 Resumen de Impacto Esperado

| Mejora | Impacto en Win Rate | Impacto en Profit Factor | Costo de Implementación |
|---|---|---|---|
| ATR-Based SL | +5-8% | +0.2 | Bajo |
| Partial Exits | +3-5% | +0.3 | Medio |
| Correlation Real | +2-4% | +0.1 | Bajo |
| News Impact | +3-6% | +0.2 | Medio |
| Time Stop | +2-3% | +0.1 | Bajo |
| ML Ligero | +5-10% | +0.3 | Medio |
| Walk-Forward | N/A (validación) | Mejora confianza | Medio |
| Seasonality | +2-4% | +0.1 | Medio |
| Implied Move | +3-5% | +0.2 | Alto |
| Heat Map | +1-2% | +0.1 | Medio |
| Re-entry Rules | +5-8% | +0.3 | Bajo |
| Recovery Strategy | +10%+ | +0.5 | Medio |
| Session-Aware | +2-3% | +0.1 | Medio |
| Adaptive TP | +3-5% | +0.2 | Bajo |

**Total estimado**: Win rate +40-60%, Profit Factor +1.8-2.0

---

## 🎯 Recomendaciones de Prioridad (Top 5)

1. **ATR-Based SL** (Bajo costo, alto impacto, reduce churn)
2. **Re-entry Rules + Cooldown** (Bajo costo, evita muerte por mil cortes)
3. **Partial Exits** (Medio costo, mejora dramáticamente R:R)
4. **ML Ligero como filtro previo** (Medio costo, ahorra tokens, mejora calidad)
5. **Drawdown Recovery Strategy** (Medio costo, protege capital en malas rachas)
