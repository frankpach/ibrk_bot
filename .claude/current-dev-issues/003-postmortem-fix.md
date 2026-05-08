# Issue 003: PostMortem v2 — Fix BUG-001 + ajustes estructurados

**Module**: dev-plan
**Type**: AFK
**Effort**: S
**Blocked by**: 001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema dice que "aprende" de cada trade, pero el post-mortem nunca ha corrido en producción. `postmortem.py` usa `openai.OpenAI` con `LLM_API_KEY` vacía — cada vez que se cierra un trade, el post-mortem falla silenciosamente y no guarda ningún patrón real.

**Business impact**: Sin post-mortem funcionando, el sistema no aprende nada de sus trades. Los patrones en DB son solo de tests manuales, no del sistema real. Los ajustes paramétricos atenuados (el corazón del aprendizaje) nunca se aplican.

**Success signal**: Después de que se cierra un trade, Frank recibe en Telegram "Post-mortem AAPL: patrón guardado. 1 ajuste aplicado." y un nuevo registro aparece en la tabla `patterns`.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot Pi | Pi | Después de cada trade | Aprender del resultado | OpenCode disponible via subprocess |
| Frank | Trader | iPhone | Telegram | Saber que el sistema aprendió | Mensaje conciso, no técnico |

**Primary user**: Sistema autónomo post-cierre de trade.

---

## WHAT — Constraints

- [ ] Eliminar completamente `from openai import OpenAI` y uso de `LLM_API_KEY`
- [ ] Usar `_call_opencode(prompt)` de `app/llm/agent.py` — misma función que ya funciona
- [ ] El prompt incluye el `FeatureSet` al momento de entrada si `feature_snapshot_id` está en el trade (puede ser None si el trade es anterior al sistema nuevo)
- [ ] Parseo de JSON estructurado con degradación graceful: si falla → guarda solo pattern_text como texto libre
- [ ] `QuantScorer.update_weights_attenuated()` se llama por cada sugerencia con confidence >= 0.5
- [ ] Notificar a Frank via Telegram con resumen

**Module-specific rules**:
- [ ] Límites duros en ajustes: SL en [0.5%, 8%], multiplicadores en [0.5x, 1.5x]
- [ ] Ventana mínima 5 trades — si `trade_count < 5`, no aplica ajustes de pesos (solo guarda el patrón)

---

## HOW — Implementation Approach

**app/llm/postmortem.py** — reescribir completamente:

```python
from app.llm.agent import _call_opencode  # reutilizar función existente
from app.config.settings import MARKET_TZ

def run_postmortem(trade: Trade, feature_snapshot=None):
    # Build prompt con trade + feature_snapshot (si disponible)
    # JSON esperado:
    # {
    #   "pattern_text": "...",
    #   "suggestions": [
    #     {"dimension": "stop_loss_pct", "suggested": 0.028, "confidence": 0.7, "reason": "..."},
    #     {"dimension": "momentum_mult", "suggested_multiplier": 1.2, "confidence": 0.6, "reason": "..."}
    #   ]
    # }
    
    response = _call_opencode(prompt)
    
    # Parse — degradación graceful si falla
    try:
        data = json.loads(response)
        pattern_text = data.get("pattern_text", response.strip())
        suggestions = data.get("suggestions", [])
    except (json.JSONDecodeError, KeyError):
        pattern_text = response.strip()[:200]
        suggestions = []
    
    # Guardar patrón
    insert_pattern(Pattern(...))
    
    # Aplicar ajustes atenuados
    adjustments_applied = 0
    for s in suggestions:
        if s.get("confidence", 0) >= 0.5:
            from app.analysis.scorer import update_weights_attenuated
            ok = update_weights_attenuated(
                symbol=trade.symbol,
                dimension=s["dimension"],
                suggested_multiplier=s.get("suggested_multiplier", s.get("suggested", 1.0)),
                confidence=s["confidence"],
            )
            if ok:
                adjustments_applied += 1
    
    # Notificar Frank
    notify(
        f"Post-mortem <b>{trade.symbol}</b>: patrón guardado.\n"
        f"{adjustments_applied} ajuste(s) aplicado(s)."
    )
```

**Nota**: `update_weights_attenuated` de `app/analysis/scorer.py` — se implementa en Issue 004. Este issue puede usar un stub mínimo hasta que 004 esté listo, o bloquearse en 004.

**Decisión de bloqueo**: Issue 003 se puede implementar con `QuantScorer` como stub (solo guarda sugerencias en log, no aplica). Se completa al 100% cuando Issue 004 existe.

---

## Code Search

- [ ] `app/llm/postmortem.py` — reemplazar completamente (importa openai, usa LLM_API_KEY vacía)
- [ ] `app/llm/agent.py` — `_call_opencode()` ya existe y funciona
- [ ] `app/notifications/telegram.py` — `notify()` ya existe
- [ ] `app/db/database.py` — `insert_pattern()` ya existe

**Reuse decision**:
- Reuse as-is: `_call_opencode()` de agent.py, `insert_pattern()`, `notify()`
- Build new: estructura del prompt, parseo JSON, lógica de ajuste

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/dev-plan/08-prd.md | REQ-08 con ACs, estructura JSON esperada |
| Interface design | docs/dev/artifacts/dev-plan/06-interface-design.md | Workflow 4 post-mortem |

---

## Acceptance Criteria

- [ ] AC-08.1: `run_postmortem(trade)` no lanza excepción con `LLM_API_KEY=""` (ya no la necesita)
- [ ] AC-08.2: Un Pattern queda en DB después de ejecutar `run_postmortem` con OpenCode disponible
- [ ] AC-08.3: Frank recibe notificación Telegram con "Post-mortem {symbol}: patrón guardado"
- [ ] AC-08.4: Con OpenCode no disponible → retorna gracefully sin crash, loguea error
- [ ] AC-08.5: `from openai import OpenAI` eliminado completamente del archivo
- [ ] `test_postmortem.py` (3 tests existentes) siguen pasando

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `postmortem.py` no importa openai SDK
- [ ] Tests nuevos para parseo JSON y degradación graceful
- [ ] Issue movido a `done/`
