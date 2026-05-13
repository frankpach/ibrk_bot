# Issue RE-003: MarketRegimeDetector + TimeFilter

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: S
**Blocked by**: —
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema opera igual cuando el mercado está tranquilo (VIX 12) que cuando hay pánico (VIX 40). En crisis, los stops se tocan por ruido y las posiciones son demasiado grandes.

**Business impact**: Drawdowns catastróficos en días de alta volatilidad. El circuit breaker se activa frecuentemente porque el sistema no se adapta.

**Success signal**: VIX sube a 32 → el sistema reduce tamaños 50% y amplía SLs 30%. VIX sube a 40 → bloquea nuevas entradas.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot | Pi | Cada 15 min / pre-entrada | Detectar régimen y ajustar | Usar solo VIX, no múltiples fuentes |
| Frank | Trader | iPhone | Telegram | Saber por qué no entra | Notificación una sola vez por cambio de régimen |

---

## WHAT — Constraints

- [ ] VIX vía `IBDataLayer.get_ohlcv("VIX", "5 D", "1 day")`
- [ ] Regímenes: low_vol (<15), normal (15-25), high_vol (25-35), crisis (≥35)
- [ ] Ajustes: size_mult, sl_mult, entry_blocked
- [ ] Chequear antes de cada entrada
- [ ] Chequear cada 15 min para cambios de régimen
- [ ] TimeFilter: no entry 9:30-10:00 ET, reduced 11:30-14:00 ET

**Module-specific rules**:
- [ ] No agregar tablas DB (in-memory state)
- [ ] Usar MARKET_TZ de settings
- [ ] VIX cacheado por IBDataLayer (TTL 900s)

---

## HOW — Implementation Approach

**app/risk/market_regime.py**:
```python
@dataclass
class MarketRegime:
    vix_level: float
    regime: Literal["low_vol", "normal", "high_vol", "crisis"]

@dataclass
class RegimeAdjustments:
    position_size_multiplier: float
    sl_widening_multiplier: float
    entry_blocked: bool

class MarketRegimeDetector:
    REGIME_THRESHOLDS = [15, 25, 35]
    ADJUSTMENTS = {
        "low_vol": RegimeAdjustments(1.2, 0.9, False),
        "normal": RegimeAdjustments(1.0, 1.0, False),
        "high_vol": RegimeAdjustments(0.5, 1.3, False),
        "crisis": RegimeAdjustments(0.0, 1.5, True),
    }
    
    def get_regime(self) -> MarketRegime: ...
    def get_adjustments(self) -> RegimeAdjustments: ...
```

**app/risk/time_filter.py**:
```python
class TimeFilter:
    OPENING_CHOP = (9, 30, 10, 0)
    MID_DAY = (11, 30, 14, 0)
    
    def is_entry_allowed(self, now=None) -> tuple[bool, str]: ...
```

**app/risk/validator.py** (modificar):
- `validate_order()` llama `time_filter.is_entry_allowed()` y `regime.get_adjustments()`
- Si entry_blocked → reject
- Si mid_day → ajustar size_mult en resultado

**run.py** (modificar):
- Agregar job cada 15 min para chequeo de régimen:
```python
scheduler.add_job(check_regime_change, "interval", minutes=15, id="regime_checker")
```

---

## Code Search

- [ ] `app/risk/validator.py` — `validate_order()` a extender
- [ ] `app/analysis/data.py` — `IBDataLayer.get_ohlcv()` para VIX
- [ ] `app/config/settings.py` — `MARKET_TZ`
- [ ] `run.py` — patrón de scheduler.add_job

**Reuse decision**:
- Reuse as-is: `IBDataLayer`, `MARKET_TZ`, APScheduler
- Build new: `MarketRegimeDetector`, `TimeFilter`
- Extend: `validate_order()`

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/risk-engine-v2/08-prd.md | REQ-03, REQ-04, REQ-07 |
| Interface design | docs/dev/artifacts/risk-engine-v2/06-interface-design.md | MarketRegimeDetector, TimeFilter |

---

## Acceptance Criteria

- [ ] AC-03.1: VIX=32 → entry ok, size × 0.5, SL × 1.3
- [ ] AC-03.2: VIX=38 → entry blocked, notifica "crisis"
- [ ] AC-03.3: Cambio normal→high_vol → SLs existentes ampliados 30% una vez
- [ ] AC-04.1: 9:35 ET → `is_entry_allowed()` = (False, "opening_chop")
- [ ] AC-04.2: 10:05 ET → (True, "ok")
- [ ] AC-04.3: 12:00 ET → (True, "mid_day_reduced") con size 0.8x

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: regime detection, time filtering, adjustments
- [ ] Issue movido a `done/`
