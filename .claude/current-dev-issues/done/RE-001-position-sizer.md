# Issue RE-001: PositionSizer + SlippageEstimator

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: M
**Blocked by**: —
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema arriesga lo mismo en TSLA (ATR 4%, muy volátil) que en SPY (ATR 1%, estable). Además, las órdenes MKT causan slippage que no se contempla, haciendo que el riesgo real sea mayor que el planificado.

**Business impact**: Posiciones demasiado grandes en alta volatilidad → stops tocados más frecuentemente. Slippage no contemplado → capital erosionado por comisiones + malos fills.

**Success signal**: NVDA con ATR 2.8% tiene tamaño 0.53. SPY con ATR 1.2% tiene tamaño 0.85. Ambos arriesgan el mismo ~$10 real.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot | Pi | Pre-orden | Calcular tamaño óptimo adaptativo | < 1ms por cálculo |
| Frank | Trader | iPhone | Telegram | Ver tamaño justificado en preview | Claro y transparente |

---

## WHAT — Constraints

- [ ] Fórmula: base_size = max_risk / (sl_pct + slippage_buffer)
- [ ] Multiplicadores: win_rate, volatility (ATR), confidence (score)
- [ ] Slippage buffer: default 0.5%, configurable en settings
- [ ] Cap: nunca exceder MAX_POSITION_USD ni capital * MAX_RISK_PCT / sl
- [ ] Resultado incluye: units, risk_usd, slippage_usd, reasons

**Module-specific rules**:
- [ ] Sin modificar IBKRClient
- [ ] Reutilizar SymbolParameter.win_rate si existe
- [ ] Si win_rate no disponible (< 5 trades), usar default 0.5

---

## HOW — Implementation Approach

**app/risk/dynamic_sizing.py**:
```python
@dataclass
class PositionSizeResult:
    units: float
    estimated_risk_usd: float
    estimated_slippage_usd: float
    reasons: list[str]

class PositionSizer:
    def calculate_size(self, symbol, entry_price, stop_loss_pct, capital,
                       atr_pct=None, win_rate=None, score=None) -> PositionSizeResult: ...
```

**app/risk/slippage.py**:
```python
class SlippageEstimator:
    def estimate_slippage_pct(self, symbol: str) -> float:
        # Try to get bid-ask spread from IB
        # Fallback to settings.SLIPPAGE_BUFFER (default 0.005)
```

**app/api/main.py** (modificar):
- `orders_preview()` usa `PositionSizer.calculate_size()` en vez de fórmula directa
- Mostrar slippage estimado en respuesta

---

## Code Search

- [ ] `app/api/main.py` — `orders_preview()` fórmula actual a reemplazar
- [ ] `app/risk/validator.py` — `validate_order()` position size calc
- [ ] `app/db/database.py` — `get_or_create_symbol_parameters()` para win_rate
- [ ] `app/analysis/scorer.py` — `QuantScore.total` para confidence
- [ ] `app/config/settings.py` — agregar `SLIPPAGE_BUFFER`

**Reuse decision**:
- Reuse as-is: `SymbolParameter`, `MAX_POSITION_USD`, `MAX_RISK_PCT`
- Build new: `PositionSizer`, `SlippageEstimator`
- Extend: `orders_preview()`

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/risk-engine-v2/08-prd.md | REQ-01, REQ-05, REQ-07 |
| Interface design | docs/dev/artifacts/risk-engine-v2/06-interface-design.md | PositionSizer, PositionSizeResult |

---

## Acceptance Criteria

- [ ] AC-01.1: NVDA $214, SL=2.5%, ATR=2.8%, WR=65%, score=78 → size ≈ 0.53
- [ ] AC-01.2: SPY $500, SL=2.5%, ATR=1.2%, WR=55%, score=72 → size ≈ 0.85
- [ ] AC-01.3: Con slippage buffer < sin slippage buffer (siempre más conservador)
- [ ] AC-05.1: Spread disponible → usa spread real como buffer
- [ ] AC-05.2: Sin spread → usa default 0.005
- [ ] AC-07.3: `orders_preview()` muestra size, risk, slippage en respuesta

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: sizing formula, slippage estimation, edge cases
- [ ] Issue movido a `done/`
