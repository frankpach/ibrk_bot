# Issue MTE-009: Postmortem con Contexto Estadístico

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: S
**Blocked by**: MTE-008
**Requires review**: false
**Iteración**: 2

---

## WHY — The Human Problem

**User pain**: El LLM en el postmortem analiza cada trade de forma aislada — no sabe si AAPL históricamente pierde por SL estrecho, ni qué patrones se encontraron antes. Las sugerencias de ajuste son genéricas y no calibradas a la realidad del símbolo.

**Business impact**: Los ajustes de parámetros sugeridos por el LLM no están fundamentados en evidencia estadística. El postmortem puede sugerir ampliar el SL en un símbolo que históricamente gana con SL ajustado.

**Success signal**: El prompt del LLM incluye: "win_rate últimos 10 trades: 60%, SL activado en 30% de los trades". El LLM usa esa evidencia para sugerencias más precisas.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Motor Autónomo | Sistema | Raspberry Pi | Post-trade | Ajustes de parámetros basados en evidencia | No agregar latencia > 1s al postmortem |

---

## WHAT — Constraints

- [ ] Archivo nuevo `app/ml/postmortem_stats.py` — no modificar `postmortem.py` más allá de llamar la nueva función
- [ ] Si hay < 3 trades del símbolo → retornar None (no enriquecer el prompt)
- [ ] No hacer requests a IBKR — solo leer de SQLite
- [ ] `get_closed_trades_by_symbol()` ya debe existir en database.py

---

## HOW — Implementation Approach

**`app/ml/postmortem_stats.py`** (nuevo, ~60 líneas):

```python
from dataclasses import dataclass, field
from app.db.database import get_closed_trades_by_symbol, get_patterns_for_symbol

@dataclass
class PostmortemContext:
    win_rate_last_10: float
    avg_pnl_wins_pct: float
    avg_pnl_losses_pct: float
    sl_hit_rate: float
    tp_hit_rate: float
    most_common_exit: str
    patterns_last_3: list = field(default_factory=list)

    def to_prompt_str(self) -> str:
        return (
            f"Historial de {self.most_common_exit} más común. "
            f"Win rate últimos 10: {self.win_rate_last_10:.0%}. "
            f"SL activado en {self.sl_hit_rate:.0%} de trades. "
            f"TP en {self.tp_hit_rate:.0%}. "
            f"Avg win: {self.avg_pnl_wins_pct:.1%}, avg loss: {self.avg_pnl_losses_pct:.1%}. "
            + (f"Patrones previos: {'; '.join(self.patterns_last_3)}" if self.patterns_last_3 else "")
        )

def enrich_postmortem_context(symbol: str) -> PostmortemContext | None:
    trades = get_closed_trades_by_symbol(symbol, limit=10)
    if len(trades) < 3:
        return None
    wins = [t for t in trades if (t.pnl_pct or 0) > 0]
    losses = [t for t in trades if (t.pnl_pct or 0) <= 0]
    sl_exits = [t for t in trades if t.exit_reason == "STOP_LOSS"]
    tp_exits = [t for t in trades if t.exit_reason == "TAKE_PROFIT"]
    from collections import Counter
    most_common = Counter(t.exit_reason for t in trades if t.exit_reason).most_common(1)
    patterns = get_patterns_for_symbol(symbol, limit=3)
    return PostmortemContext(
        win_rate_last_10=len(wins)/len(trades),
        avg_pnl_wins_pct=sum(t.pnl_pct for t in wins)/len(wins) if wins else 0,
        avg_pnl_losses_pct=sum(t.pnl_pct for t in losses)/len(losses) if losses else 0,
        sl_hit_rate=len(sl_exits)/len(trades),
        tp_hit_rate=len(tp_exits)/len(trades),
        most_common_exit=most_common[0][0] if most_common else "UNKNOWN",
        patterns_last_3=[p.pattern_text[:80] for p in patterns],
    )
```

**`app/llm/postmortem.py`** — en `run_postmortem()`, antes de llamar al LLM:
```python
from app.ml.postmortem_stats import enrich_postmortem_context
ctx = enrich_postmortem_context(trade.symbol)
ctx_str = f"\nHISTORICAL CONTEXT: {ctx.to_prompt_str()}" if ctx else ""
# Agregar ctx_str al prompt del LLM
```

---

## Code Search

- [x] `app/llm/postmortem.py:48-144` — `run_postmortem()` leído
- [x] `app/db/database.py:655-668` — `get_patterns_for_week()` existe — necesito `get_patterns_for_symbol()`

**Reuse decision**:
- Reuse as-is: `get_closed_trades_by_symbol()` (verificar que existe), `notify()`
- Build new: `PostmortemContext`, `enrich_postmortem_context()`, `get_patterns_for_symbol()`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-09, AC-09.1 a AC-09.4 |
| Interface design | `docs/dev/artifacts/mtf-learning-engine/06-interface-design.md` | Flujo 5 |

---

## Acceptance Criteria

- [ ] AC-09.1: Con 5 trades de AAPL → `enrich_postmortem_context("AAPL")` retorna `PostmortemContext`
- [ ] AC-09.2: Con < 3 trades → retorna None (no crashea `run_postmortem()`)
- [ ] AC-09.3: El prompt del LLM incluye las estadísticas cuando contexto no es None
- [ ] AC-09.4: `patterns_last_3` tiene máx 3 entradas; lista vacía si no hay patrones

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] Test: `enrich_postmortem_context()` con 0, 2, y 10 trades
- [ ] `pytest tests/llm/test_postmortem_extended.py` pasa
- [ ] Issue movido a `done/`
