# Issue RE-002: TrailingStopManager

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: M
**Blocked by**: RE-001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Cuando una posición sube 5%, el stop-loss sigue en -2.5% del precio de entrada. Si el precio cae, se pierden todas las ganancias. El sistema no protege ganancias flotantes.

**Business impact**: Trades ganadores se convierten en perdedores. El profit factor se degrada. Frank ve cómo ganancias se evaporan sin acción del sistema.

**Success signal**: AAPL sube 5% → SL se mueve a breakeven. AAPL sube 10% → trailing stop activa en 50% de la ganancia. Si cae, cierra con +4.6%, no con -2.5%.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot | Pi | Cada 2 min | Proteger ganancias automáticamente | Sin modificar schema DB |
| Frank | Trader | iPhone | Telegram | Saber que sus ganancias están protegidas | Notificación solo cuando SL cambia |

---

## WHAT — Constraints

- [ ] Breakeven Rule: P&L% > 1.5 × original_SL% → mover SL a entry ± 0.3%
- [ ] Trailing Rule: P&L% > 3.0 × original_SL% → trailing a 50% de ganancia máxima
- [ ] Nunca mover SL hacia atrás (peorar)
- [ ] Computar dinámicamente en `check_positions()` — no cambiar schema DB
- [ ] Notificar a Frank solo cuando SL cambia efectivamente
- [ ] Si trailing stop toca → cerrar con "TRAILING_STOP" como razón

**Module-specific rules**:
- [ ] No agregar columnas a tabla trades (opcional: agregar `current_stop_price` si se prefiere)
- [ ] Mantiene SL original como referencia (no lo sobrescribe en DB)

---

## HOW — Implementation Approach

**app/risk/trailing_stop.py**:
```python
@dataclass
class StopUpdateResult:
    new_stop_price: float | None
    reason: str | None
    should_close: bool

class TrailingStopManager:
    BREAKEVEN_MULTIPLIER = 1.5
    TRAILING_MULTIPLIER = 3.0
    BREAKEVEN_BUFFER = 0.003
    TRAILING_PCT = 0.5
    
    def update_stop_levels(self, trade: Trade, current_price: float) -> StopUpdateResult: ...
```

**app/positions/manager.py** (modificar):
- En `check_positions()`, antes de evaluar SL/TP:
```python
stop_result = trailing_stop_manager.update_stop_levels(trade, price)
if stop_result.new_stop_price:
    effective_stop = max(stop_result.new_stop_price, trade.stop_loss_price)  # never worse
    if stop_result.reason:
        notify(f"{trade.symbol}: SL ajustado a ${effective_stop:.2f} ({stop_result.reason})")
else:
    effective_stop = trade.stop_loss_price
```
- Evaluar `price <= effective_stop` para BUY (y `>=` para SELL)
- Si trailing stop cierra: exit_reason = "TRAILING_STOP"

---

## Code Search

- [ ] `app/positions/manager.py` — `check_positions()` loop a modificar
- [ ] `app/db/models.py` — `Trade` dataclass
- [ ] `app/notifications/telegram.py` — `notify()` para alertas de SL cambiado

**Reuse decision**:
- Reuse as-is: `Trade` model, `notify()`, `close_trade()`
- Build new: `TrailingStopManager`
- Extend: `check_positions()`

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/risk-engine-v2/08-prd.md | REQ-02 |
| Interface design | docs/dev/artifacts/risk-engine-v2/06-interface-design.md | TrailingStopManager, StopUpdateResult |

---

## Acceptance Criteria

- [ ] AC-02.1: Entry $100, SL $97.5. Price $104 (+4% > 3.75%) → SL ajusta a $100.3
- [ ] AC-02.2: Price $110 (+10% > 7.5%) → trailing activa en $105. Caída a $104.9 → cierra
- [ ] AC-02.3: SL nunca se mueve hacia atrás
- [ ] AC-02.4: Notificación solo cuando SL cambia (no cada 2 min)
- [ ] AC-02.5: Cierre por trailing stop → exit_reason = "TRAILING_STOP"

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: breakeven trigger, trailing trigger, no backward movement
- [ ] Issue movido a `done/`
