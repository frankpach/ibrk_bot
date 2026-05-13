# Issue 006: DailyDiscovery + ReturnEvaluator + Endpoints + MCP tools

**Module**: dev-plan
**Type**: AFK
**Effort**: L
**Blocked by**: 004, 005
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema solo vigila los mismos 10 símbolos todos los días. No hay forma de saber si una decisión pasada fue correcta. Frank no puede ver el análisis de candidatos via API ni MCP. El LLM no puede pedir un análisis completo de un símbolo nuevo.

**Business impact**: Sin discovery diario, el sistema nunca encuentra nuevas oportunidades. Sin ReturnEvaluator, no hay validación cuantitativa del sistema. Sin endpoints y MCP tools, el sistema es una caja negra.

**Success signal**: Cada mañana a las 8am ET Frank recibe notificación si algún símbolo nuevo entró al universo. El MCP tool `candidate_analysis("NFLX")` retorna el AnalysisResult completo. `/candidate-decisions` muestra retornos reales vs SPY.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Sistema | Bot Pi | Pi | 8am ET | Descubrir candidatos nuevos | Batch silencioso, < 5 min |
| Frank | Trader | iPhone | Telegram | Saber qué entró/salió del universo | Solo notificado si hay cambio |
| LLM | Analista | subprocess | On-demand | Llamar candidate_analysis via MCP | Misma API que otros tools |

**Primary user**: Sistema autónomo (discovery) + LLM via MCP.

---

## WHAT — Constraints

- [ ] DailyDiscovery: solo días de mercado (lunes-viernes), 8am ET via APScheduler cron
- [ ] Batch silencioso para candidatos — sin notify_fn (no spam a Frank durante discovery)
- [ ] SPY y QQQ nunca salen del universo (protección hardcodeada)
- [ ] Rotación: notifica ANTES de ejecutar, ejecuta automáticamente
- [ ] ReturnEvaluator: determinístico, sin LLM
- [ ] Nuevos endpoints en FastAPI siguiendo el patrón existente

---

## HOW — Implementation Approach

**run.py** — agregar jobs:
```python
from app.analysis.admission import run_daily_discovery
from app.analysis.evaluator import run_return_evaluator

scheduler.add_job(
    lambda: run_daily_discovery(data_layer),
    "cron", day_of_week="mon-fri", hour=8, minute=0, timezone=MARKET_TZ,
    id="daily_discovery"
)
scheduler.add_job(
    lambda: run_return_evaluator(data_layer),
    "cron", hour=6, minute=0, timezone=MARKET_TZ,
    id="return_evaluator"
)
```

**app/analysis/admission.py** (nuevo):
- `run_daily_discovery(data_layer)`:
  1. `data_layer.run_scanner("HOT_BY_VOLUME")` + `"TOP_PERC_GAIN"` + `"MOST_ACTIVE"`
  2. Une, deduplica, filtra símbolos ya en universo, top 20 por volumen
  3. Para cada candidato: `AnalysisPipeline(symbol, data_layer, AnalysisContext("daily_discovery"), notify_fn=None).run()`
  4. Candidatos con score >= 70 → candidatos de watchlist
  5. `universe_rotation(candidates, current_universe)`
- `universe_rotation(candidates, current_universe)`:
  - Si `mejor_candidato.score > 75` y `peor_universo.watchlist_score < 40`:
    - Notifica Frank: "🔄 {nuevo} (score:{s}) entra al universo. {viejo} (watchlist:{w}) sale."
    - Actualiza `symbol_config` en DB
    - Actualiza `ALLOWED_SYMBOLS` en memory
  - SPY y QQQ protegidos

**app/analysis/evaluator.py** (nuevo):
- `run_return_evaluator(data_layer)`:
  - `get_candidate_decisions_for_evaluation(days_ago=7)` → decisiones sin future_return_7d
  - Para cada: obtiene precio actual + SPY price en fecha de decisión
  - Calcula return_7d y alpha_vs_spy_7d
  - `update_candidate_decision_returns(...)`
  - Repite para days_ago=30

**app/api/main.py** — agregar endpoints:
```python
@app.get("/candidate-analysis/{symbol}")
def candidate_analysis_endpoint(symbol: str):
    # Crea AnalysisPipeline(mode="on_demand"), corre, retorna AnalysisResult como dict

@app.get("/analysis/indicator/{symbol}/{indicator_name}")
def single_indicator(symbol: str, indicator_name: str):
    # IBDataLayer.get_ohlcv + IndicatorEngine.compute_single_indicator

@app.get("/universe/watchlist")
def universe_watchlist():
    # Retorna símbolos con watchlist_scores

@app.get("/candidate-decisions")
def candidate_decisions(limit: int = 20):
    # Retorna decisiones con retornos calculados

@app.get("/symbol-parameters/{symbol}")
def symbol_params(symbol: str):
    # get_or_create_symbol_parameters(symbol)
```

**app/mcp/server.py** — agregar tools:
```python
@mcp.tool()
def candidate_analysis(symbol: str) -> dict:
    """Análisis completo de un símbolo via pipeline. Funciona con cualquier ticker."""
    return _get(f"/candidate-analysis/{symbol.upper()}")

@mcp.tool()
def compute_indicator(symbol: str, indicator_name: str) -> dict:
    """Calcula un solo indicador para un símbolo."""
    return _get(f"/analysis/indicator/{symbol.upper()}/{indicator_name}")

@mcp.tool()
def get_universe_watchlist() -> list:
    """Símbolos del universo con sus watchlist scores."""
    return _get("/universe/watchlist")
```

---

## Code Search

- [ ] `run.py` — patrón de scheduler.add_job existente para replicar
- [ ] `app/api/main.py` — patrón de endpoints existentes
- [ ] `app/mcp/server.py` — patrón de tools existentes (`_get()`, `_post()`)
- [ ] `app/db/database.py` — `get_approved_symbols()`, `approve_symbol()` para universe rotation

**Reuse decision**:
- Reuse as-is: APScheduler pattern, endpoint pattern, MCP tool pattern, `_get()`/`_post()`
- Build new: admission.py, evaluator.py, 5 nuevos endpoints, 3 nuevos MCP tools

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/dev-plan/08-prd.md | REQ-13 (DailyDiscovery), REQ-14 (ReturnEvaluator), REQ-15 (endpoints), REQ-16 (MCP) |
| Interface design | docs/dev/artifacts/dev-plan/06-interface-design.md | Workflow 3 (discovery/rotation), Workflow 5 (return evaluator) |

---

## Acceptance Criteria

- [ ] AC-13.1: Job `daily_discovery` corre a 8am ET lunes-viernes, no en fines de semana
- [ ] AC-13.2: Frank recibe notificación solo si hay rotación efectiva
- [ ] AC-13.3: Con MockIBClient el job completa sin errores
- [ ] AC-13.4: SPY y QQQ permanecen en universo bajo cualquier circunstancia
- [ ] AC-14.1: Decisión de hace 7 días tiene `future_return_7d` poblado después del job
- [ ] AC-14.2: `alpha_vs_spy_7d` positivo si el símbolo superó a SPY
- [ ] AC-15.1: `GET /candidate-analysis/NFLX` retorna JSON con `quant_score` y `recommendation` en < 90s
- [ ] AC-15.2: `GET /analysis/indicator/AAPL/rsi_14` retorna float 0-100
- [ ] AC-16.1: OpenCode puede llamar `candidate_analysis("NFLX")` via MCP y recibe AnalysisResult
- [ ] 95 tests existentes siguen pasando + nuevos tests para endpoints y admission

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `pytest tests/` → todos PASS
- [ ] DailyDiscovery corre correctamente en Pi (verificado manualmente lunes siguiente)
- [ ] MCP tool `candidate_analysis` disponible en OpenCode
- [ ] Issue movido a `done/`
