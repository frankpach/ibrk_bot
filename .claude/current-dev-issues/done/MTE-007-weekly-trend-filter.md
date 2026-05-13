# Issue MTE-007: Weekly Trend Filter + Fix Multi-Market en Preprocessor

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: M
**Blocked by**: MTE-006
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El scanner genera señales STRONG en activos en downtrend semanal claro (SMA20w < SMA50w). Además, el preprocessor solo funciona para equities US porque hardcodea `Stock(symbol, "SMART", "USD")` — futuros, forex y crypto reciben contratos incorrectos.

**Business impact**: (1) Señales STRONG en downtrend macro tienen win rate significativamente menor. (2) Futuros (ES, NQ) y crypto (BTC) no se escanean correctamente — órdenes pueden fallar por contrato inválido.

**Success signal**: Una señal STRONG en activo con SMA20w < SMA50w se degrada a MEDIUM. ES (futuro) se escanea con contrato FUT/CME/USD correcto.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Motor Autónomo | Sistema | Raspberry Pi | Producción | Señales filtradas por tendencia macro | Fallback si weekly falla |

---

## WHAT — Constraints

- [ ] Si fetch semanal falla (timeout, rate limit) → continuar con `weekly_trend = "NEUTRAL"` — nunca bloquear el scan
- [ ] Veto parcial: STRONG → MEDIUM en bearish, MEDIUM → WEAK en bearish. No eliminar señales completamente.
- [ ] Usar `build_contract()` de `app/ibkr/contract_factory.py` — no crear contratos manualmente
- [ ] Usar `get_use_rth(sec_type)` del contract_factory para `useRTH`
- [ ] `symbol_meta` ya llega a `scan_symbol()` con sec_type, exchange, currency — solo usarlo

---

## HOW — Implementation Approach

**`app/scanner/preprocessor.py`**:

```python
def _weekly_trend_filter(df_weekly) -> str:
    """Retorna BULLISH/BEARISH/NEUTRAL según SMA20/SMA50 semanal."""
    if df_weekly is None or len(df_weekly) < 20:
        return "NEUTRAL"
    try:
        sma20 = df_weekly["close"].rolling(20).mean().iloc[-1]
        sma50 = df_weekly["close"].rolling(50).mean().iloc[-1] if len(df_weekly) >= 50 else sma20
        close = df_weekly["close"].iloc[-1]
        if close > sma20 and sma20 > sma50:
            return "BULLISH"
        if close < sma20 and sma20 < sma50:
            return "BEARISH"
    except Exception:
        pass
    return "NEUTRAL"


def scan_symbol(symbol: str, ib_client=None, symbol_meta: dict | None = None) -> dict:
    meta = symbol_meta or {"symbol": symbol, "sec_type": "STK", "exchange": "SMART",
                           "currency": "USD", "liquid_hours": "US_RTH"}
    
    # FIX: usar build_contract con meta completo
    from app.ibkr.contract_factory import build_contract, get_use_rth
    sec_type = meta.get("sec_type", "STK")
    contract = build_contract(symbol, sec_type, meta.get("exchange", "SMART"),
                              meta.get("currency", "USD"))
    use_rth = get_use_rth(sec_type)
    
    # ... fetch daily y hourly usando use_rth ...
    
    # NUEVO: fetch semanal con timeout corto
    df_weekly = None
    try:
        bars_w = ib_client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr="1 Y",
            barSizeSetting="1 week", whatToShow="TRADES",
            useRTH=use_rth, formatDate=1,
        )
        if bars_w and len(bars_w) >= 20:
            df_weekly = pd.DataFrame([{"close": b.close} for b in bars_w])
    except Exception as e:
        logger.warning(f"Weekly fetch failed for {symbol}: {e}")
    
    weekly_trend = _weekly_trend_filter(df_weekly)
    
    # Clasificar multi-TF (ya existente)
    strength = classify_multitimeframe(sig_daily, sig_hourly, sig_5min)
    
    # NUEVO: veto parcial por tendencia macro
    if weekly_trend == "BEARISH":
        if strength == "STRONG":
            strength = "MEDIUM"
            logger.info(f"{symbol}: STRONG→MEDIUM por downtrend semanal")
        elif strength == "MEDIUM":
            strength = "WEAK"
            logger.info(f"{symbol}: MEDIUM→WEAK por downtrend semanal")
    
    # Incluir weekly_trend en extra_indicators
    extra = json.dumps({
        "daily": sig_daily, "hourly": sig_hourly, "5min": sig_5min,
        "weekly_trend": weekly_trend
    })
    insert_signal(Signal(..., extra_indicators=extra))
```

---

## Code Search

- [x] `app/scanner/preprocessor.py:58-129` — `scan_symbol()` completo leído
- [x] `app/ibkr/contract_factory.py` — `build_contract()`, `get_use_rth()` existen
- [x] `app/analysis/data.py:77-135` — `get_ohlcv()` — patrón de fetch a replicar

**Reuse decision**:
- Reuse as-is: `classify_multitimeframe()`, `classify_signal()`, `build_contract()`, `get_use_rth()`
- Build new: `_weekly_trend_filter()`, lógica de veto
- Fix: construcción de contrato (Stock → build_contract), useRTH dinámico

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-05, AC-05.1 a AC-05.6 |
| Architecture map | `docs/dev/artifacts/mtf-learning-engine/03-architecture-map.md` | GAP-02, GAP-03 |
| Why Decisions | `docs/dev/artifacts/mtf-learning-engine/05-why-decisions.md` | WD-04 |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | C-04, C-10 |

---

## Acceptance Criteria

- [ ] AC-05.1: SMA20w > SMA50w y close > SMA20w → `_weekly_trend_filter()` retorna "BULLISH"
- [ ] AC-05.2: En downtrend semanal (BEARISH), señal STRONG se degrada a MEDIUM
- [ ] AC-05.3: En downtrend semanal, señal MEDIUM se degrada a WEAK
- [ ] AC-05.4: Si fetch semanal falla → scan continúa con strength original sin error
- [ ] AC-05.5: `scan_symbol("ES", ib_client, {"sec_type": "FUT", "exchange": "CME", ...})` usa contrato FUT/CME correcto
- [ ] AC-05.6: `extra_indicators` del Signal incluye campo `"weekly_trend"`
- [ ] AC-05.7: `pytest tests/scanner/test_preprocessor_multi_market.py` pasa

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] Tests de `scan_symbol()` actualizados para weekly_trend y multi-market
- [ ] Issue movido a `done/`
