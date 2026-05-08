# Issue 004: QuantScorer + HardRules + DB tables + AnalysisPipeline

**Module**: dev-plan
**Type**: AFK
**Effort**: XL
**Blocked by**: 002
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Cuando Frank escribe `/analizar NFLX`, el LLM recibe 3 números y texto libre, improvisa el análisis, y Frank no sabe si tardará 5 segundos o 5 minutos. Si se traba, no hay notificación. El sistema no tiene score numérico — la decisión es opaca.

**Business impact**: Sin el pipeline unificado con score visible y watchdog, el análisis on-demand es poco confiable. Sin las nuevas tablas DB, no hay DecisionMemory ni aprendizaje de parámetros.

**Success signal**: `AnalysisPipeline("NFLX").run()` retorna `AnalysisResult(score=72, recommendation="PROPOSE", feature_snapshot_id=<int>)` con progress streaming a Telegram y watchdog de 10 minutos.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Frank | Trader | iPhone | Telegram | Ver progreso del análisis, score claro | Quiere respuesta en < 90s |
| Sistema | Bot Pi | Pi | 24/7 | Pipeline confiable con watchdog | Latencia LLM 30-60s |

**Primary user**: Frank via Telegram.

---

## WHAT — Constraints

- [ ] QuantScorer: pesos globales como hipótesis inicial, multiplicadores por símbolo [0.5x, 1.5x]
- [ ] HardRules: sin LLM, determinístico. Si falla → NO llamar LLM
- [ ] AnalysisPipeline: watchdog total 10 min, timeouts por paso
- [ ] Progress streaming via `notify_fn` — Frank siempre sabe dónde está el análisis
- [ ] LLM recibe JSON estructurado (FeatureSet + QuantScore + HardRulesResult) — NO texto libre
- [ ] `feature_snapshot_id` siempre guardado en DB al completarse
- [ ] 4 nuevas tablas DB: feature_snapshots, symbol_parameters, candidate_decisions, watchlist_scores
- [ ] Todas las nuevas tablas con `CREATE TABLE IF NOT EXISTS` en init_db()

**Module-specific rules**:
- [ ] Un solo call LLM por pipeline
- [ ] HardRules falla → pipeline retorna REJECTED sin LLM
- [ ] SL siempre en [0.5%, 8%], multiplicadores en [0.5, 1.5]

---

## HOW — Implementation Approach

**app/analysis/scorer.py**:
- `QuantScore` dataclass: total, momentum, trend, volume, volatility, portfolio_fit, sentiment, recommendation, weights_used
- `GLOBAL_WEIGHTS` dict con los 6 pesos sumando 1.0
- `THRESHOLDS = {"rejected": 49, "watchlist": 69, "propose": 84, "priority": 100}`
- `compute_score(features, symbol, portfolio)` → QuantScore
  - Carga multiplicadores de DB via `get_or_create_symbol_parameters(symbol)`
  - effective_weight = global * multiplier, normalizado
  - Dimension scores (0-1) calculados desde FeatureSet según lógica del PRD REQ-05
- `update_weights_attenuated(symbol, dimension, suggested_multiplier, confidence, learning_rate=0.15, min_trade_count=5)` → bool

**app/analysis/hard_rules.py**:
- `HardRulesResult` dataclass: passed, failures, warnings, earnings_in_days
- `check_all(symbol, features, portfolio, earnings_date, capital)` → HardRulesResult
- Reglas según PRD REQ-06: liquidez, earnings gate (< 3d = fail, < 7d = warning), correlación, capital

**app/db/models.py** — agregar 4 dataclasses:
- `FeatureSnapshot`, `SymbolParameter`, `CandidateDecision`, `WatchlistScore`

**app/db/database.py** — agregar tablas en init_db() y funciones CRUD:
- `init_feature_snapshots_table()`, `init_symbol_parameters_table()`, `init_candidate_decisions_table()`, `init_watchlist_scores_table()`
- CRUD: `insert_feature_snapshot`, `get_feature_snapshot`, `insert_candidate_decision`, `update_candidate_decision_returns`, `get_candidate_decisions_for_evaluation`, `get_or_create_symbol_parameters`, `update_symbol_parameters`, `upsert_watchlist_score`

**app/analysis/pipeline.py** — AnalysisPipeline clase:
- `AnalysisContext(mode: str)` dataclass
- `ParameterSuggestion` dataclass
- `AnalysisResult` dataclass (ver interface design)
- Clase `AnalysisPipeline` con:
  - `__init__(symbol, data_layer, context, notify_fn=None)`
  - `current_step: str = "init"`
  - `run()` → AnalysisResult con watchdog `threading.Timer(600)`
  - Pasos: `_fetch_data → _compute_indicators → _score → _check_hard_rules → _llm_interpret (si passed) → _persist`
  - Timeouts individuales por paso via threading.Timer
  - `_notify_progress(message)` si notify_fn existe
  - Prompt estructurado para LLM (ver interface design RF-07.7)

---

## Code Search

- [ ] `app/db/database.py` — patrón CRUD existente para replicar en nuevas tablas
- [ ] `app/llm/agent.py` — `_call_opencode()` para reutilizar en pipeline
- [ ] `app/notifications/telegram.py` — `notify()` para notify_fn
- [ ] `app/system/controller.py` — threading pattern como referencia para watchdog
- [ ] `app/analysis/data.py` — IBDataLayer (de issue 002) como dependency

**Reuse decision**:
- Reuse as-is: `_call_opencode()`, `notify()`, `get_connection()` DB pattern
- Build new: todos los nuevos módulos de analysis/, 4 tablas DB

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/dev-plan/08-prd.md | REQ-05 a REQ-09 con todos los ACs |
| Interface design | docs/dev/artifacts/dev-plan/06-interface-design.md | AnalysisPipeline code, workflows 1-4 |
| Architecture map | docs/dev/artifacts/dev-plan/03-architecture-map.md | DB patterns, threading patterns |

---

## Acceptance Criteria

- [ ] AC-05.1: FeatureSet con RSI=28, MACD_cross=True, vol=1.8x → score >= 70
- [ ] AC-05.2: FeatureSet neutro → score 40-60
- [ ] AC-05.3: `update_weights_attenuated` con trade_count=3 → False (no actualiza)
- [ ] AC-05.4: `update_weights_attenuated` con trade_count=6, suggested=1.3, conf=0.8 → new_mult = 1.036
- [ ] AC-05.5: Ningún multiplicador puede superar 1.5 o bajar de 0.5
- [ ] AC-06.1: earnings en 2 días → HardRulesResult.passed = False
- [ ] AC-06.2: earnings en 5 días → passed=True, warnings incluye "Earnings en 5 días"
- [ ] AC-06.4: HardRules sin LLM — función pura
- [ ] AC-07.1: `pipeline.run()` con MockIBClient completa en < 5s (sin LLM)
- [ ] AC-07.2: notify_fn recibe >= 2 mensajes durante análisis completo
- [ ] AC-07.3: IB desconectado → `failed_at_step="fetch_data"`, no excepción
- [ ] AC-07.4: `hard_rules.passed=False` → LLM NUNCA llamado
- [ ] AC-07.5: `result.feature_snapshot_id` es int válido en DB
- [ ] AC-09.1: `init_db()` crea 4 nuevas tablas sin errores
- [ ] AC-09.2: Tablas existentes no modificadas
- [ ] AC-09.3: `get_or_create_symbol_parameters("NUEVO")` retorna defaults
- [ ] 95 tests existentes siguen pasando

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `pytest tests/` → todos PASS incluyendo nuevos tests para scorer, hardrules, pipeline
- [ ] Cobertura >= 80% en todos los módulos nuevos
- [ ] `AnalysisPipeline.run()` con MockIBClient + `notify_fn=print` muestra progreso en consola
- [ ] Issue movido a `done/`
