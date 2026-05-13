# Issue 005: Migraciones — agent.py + loop.py + telegram_bot /analizar

**Module**: dev-plan
**Type**: AFK
**Effort**: M
**Blocked by**: 004
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El comando `/analizar NFLX` actualmente solo obtiene el precio y manda texto libre al LLM. El análisis automático del scanner pasa 3 números sueltos al LLM. El LLM no tiene el FeatureSet estructurado — improvisa.

**Business impact**: Sin estas migraciones, el pipeline (issue 004) existe pero nadie lo usa. El análisis sigue siendo prompt-centric.

**Success signal**: `/analizar NFLX` usa `AnalysisPipeline` con progress streaming y retorna score + narrativa estructurada. El scanner automático pasa `FeatureSet` al LLM en vez de 3 floats.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Frank | Trader | iPhone | Telegram | Ver análisis completo con score y progreso | Quiere < 90s con feedback |
| Sistema | Bot Pi | Pi | 24/7 | Análisis automático feature-centric | Latencia LLM, rate limits |

**Primary user**: Frank via Telegram.

---

## WHAT — Constraints

- [ ] `analyze_signal()` en agent.py debe mantener la misma firma para no romper loop.py
- [ ] `cmd_analizar` en telegram_bot.py debe mostrar progreso streaming usando notify_fn del pipeline
- [ ] `OPENCODE_BIN` y `OPENCODE_MODEL` ya vendrán de settings (issue 001)
- [ ] No cambiar la interfaz pública de `LLMDecision` — loop.py la usa

---

## HOW — Implementation Approach

**app/llm/agent.py** — refactor:
- Eliminar `_get_context()` — el contexto viene del pipeline
- `analyze_signal(symbol, strength, rsi, macd, volume_ratio, signal_id)` ahora:
  1. Crea `AnalysisPipeline(symbol, data_layer=get_data_layer(), context=AnalysisContext("auto_signal"))`
  2. Llama `pipeline.run()`
  3. Convierte `AnalysisResult` → `LLMDecision` (para backwards compat con loop.py)
- Agregar `get_data_layer()` helper que retorna el IBDataLayer singleton de run.py
- SYMBOL_CATEGORIES y STRATEGY_CONTEXTS se mantienen pero se mueven a una función `get_strategy_context(symbol)` que consulta `SymbolConfig.category` de DB si existe
- Función `_call_opencode()` se mantiene — la usa el pipeline internamente

**app/llm/loop.py** — agregar watchdog por señal:
- `process_pending_signals()` llama `analyze_signal()` que ya usa el pipeline con watchdog interno
- Agregar timeout externo de 120s por señal (via threading.Timer) como capa extra de protección
- Si timeout → marcar señal como procesada con `mark_signal_processed()` + loguear error

**app/notifications/telegram_bot.py — cmd_analizar**:
- Reescribir para usar `AnalysisPipeline` con `notify_fn=notify`
- El pipeline envía sus propios mensajes de progreso
- El resultado muestra: score/100, recommendation, narrativa LLM, confidence
- Si `recommendation in ("PROPOSE", "PRIORITY")` y símbolo no en universo:
  - Muestra: "Score: 72/100 [PROPONER INCLUSIÓN]"
  - Ofrece: `/proponer {symbol} {razon_del_llm}`
- Si `recommendation in ("BUY", "SELL")` y símbolo en universo:
  - Muestra score + narrativa
  - Ofrece preview con `/si` para ejecutar

---

## Code Search

- [ ] `app/llm/agent.py` — función `_get_context()` a eliminar, `analyze_signal()` a refactorizar
- [ ] `app/llm/loop.py` — usa `analyze_signal()` → firma debe mantenerse
- [ ] `app/notifications/telegram_bot.py` — `cmd_analizar` actual a reemplazar
- [ ] `app/analysis/pipeline.py` — pipeline de issue 004 como dependency

**Reuse decision**:
- Reuse as-is: `_call_opencode()`, `notify()`, `LLMDecision` dataclass (backwards compat)
- Extend: `analyze_signal()` (delega a pipeline), `cmd_analizar` (usa pipeline con streaming)
- Remove: `_get_context()`, hardcoded API calls en agent

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/dev-plan/08-prd.md | REQ-12 (agent migration) |
| Interface design | docs/dev/artifacts/dev-plan/06-interface-design.md | Workflow 1 (on-demand), Workflow 2 (auto-signal) |

---

## Acceptance Criteria

- [ ] AC-12.1: `analyze_signal("AAPL", "STRONG", 28.5, -0.12, 1.8, 1)` retorna `LLMDecision` sin cambio de interfaz para loop.py
- [ ] AC-12.2: `OPENCODE_BIN` hardcodeado desaparece de agent.py
- [ ] `/analizar AAPL` en Telegram muestra al menos 2 mensajes de progreso antes del resultado final
- [ ] `/analizar NFLX` (fuera del universo) muestra score + recomendación + opción de proponer
- [ ] `test_signal_loop.py` (4 tests) pasan sin cambios
- [ ] `test_mcp_server.py` (10 tests) pasan sin cambios
- [ ] 95 tests existentes siguen pasando

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `cmd_analizar` usa AnalysisPipeline, no prompt libre
- [ ] `agent.py` sin `_get_context()`, sin API_BASE hardcodeado, sin OPENCODE_BIN hardcodeado
- [ ] Issue movido a `done/`
