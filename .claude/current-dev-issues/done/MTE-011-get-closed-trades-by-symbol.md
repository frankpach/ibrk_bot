# Issue MTE-011: DB Helper — get_closed_trades_by_symbol() + get_patterns_for_symbol()

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: XS
**Blocked by**: MTE-005
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: MTE-008 y MTE-009 necesitan `get_closed_trades_by_symbol()` y `get_patterns_for_symbol()` — funciones que no existen en `database.py`. Sin estas helpers, el learning cycle y el postmortem stats no pueden funcionar.

**Business impact**: Bloquea MTE-008 y MTE-009.

**Success signal**: `get_closed_trades_by_symbol("AAPL", limit=10)` retorna los últimos 10 trades cerrados de AAPL como lista de objetos Trade.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Motor Autónomo | Sistema | Raspberry Pi | Producción | Acceso a historial por símbolo | Queries rápidas en SQLite |

---

## WHAT — Constraints

- [ ] Solo agregar funciones a `app/db/database.py` — no crear archivos nuevos
- [ ] Retornar objetos `Trade` y `Pattern` (ya existen en models.py) — no dicts
- [ ] `limit` con default 10 para trades, 3 para patterns

---

## HOW — Implementation Approach

**`app/db/database.py`** — agregar al final del archivo:

```python
def get_closed_trades_by_symbol(symbol: str, limit: int = 10) -> list:
    """Returns closed trades for a symbol, most recent first."""
    from app.db.models import Trade
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM trades
           WHERE symbol=? AND status='CLOSED'
           ORDER BY closed_at DESC
           LIMIT ?""",
        (symbol.upper(), limit)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append(Trade(
            id=r["id"], symbol=r["symbol"], action=r["action"],
            quantity=r["quantity"], entry_price=r["entry_price"],
            stop_loss_price=r["stop_loss_price"],
            take_profit_price=r["take_profit_price"],
            stop_loss_pct=r["stop_loss_pct"],
            take_profit_pct=r["take_profit_pct"],
            signal_strength=r["signal_strength"],
            llm_justification=r["llm_justification"],
            status=r["status"],
            exit_price=r["exit_price"],
            exit_reason=r["exit_reason"],
            pnl_usd=r["pnl_usd"],
            pnl_pct=r["pnl_pct"],
            opened_at=r["opened_at"],
            closed_at=r["closed_at"],
            feature_snapshot_id=r["feature_snapshot_id"] if "feature_snapshot_id" in r.keys() else None,
        ))
    return result


def get_patterns_for_symbol(symbol: str, limit: int = 3) -> list:
    """Returns most recent patterns for a symbol."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM patterns
           WHERE symbol=?
           ORDER BY updated_at DESC
           LIMIT ?""",
        (symbol.upper(), limit)
    ).fetchall()
    conn.close()
    return [Pattern(
        id=r["id"], symbol=r["symbol"], pattern_text=r["pattern_text"],
        win_count=r["win_count"], loss_count=r["loss_count"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    ) for r in rows]
```

---

## Code Search

- [x] `app/db/database.py:402-458` — `get_trades_by_status()`, `close_trade()` — patrón a seguir
- [x] `app/db/models.py:27-55` — Trade dataclass campos confirmados
- [x] `app/db/models.py` — Pattern dataclass confirmado

**Reuse decision**:
- Reuse as-is: patrón de queries existentes, `Trade` y `Pattern` dataclasses
- Build new: `get_closed_trades_by_symbol()`, `get_patterns_for_symbol()`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-07, REQ-09 (necesitan estas helpers) |

---

## Acceptance Criteria

- [ ] AC-11.1: `get_closed_trades_by_symbol("AAPL", 5)` retorna máx 5 Trade objects con `status='CLOSED'`
- [ ] AC-11.2: Si no hay trades → retorna lista vacía (no error)
- [ ] AC-11.3: `get_patterns_for_symbol("AAPL", 3)` retorna máx 3 Pattern objects
- [ ] AC-11.4: Si no hay patterns → retorna lista vacía
- [ ] AC-11.5: `pytest tests/db/test_database.py` pasa sin regresiones

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] Tests: query con datos, query sin datos, límite respetado
- [ ] Issue movido a `done/`
