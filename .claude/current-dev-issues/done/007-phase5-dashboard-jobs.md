# Issue 007: Phase 5 — Dashboard Read Models y Background Jobs

**Module**: refactor
**Type**: AFK
**Effort**: M
**Blocked by**: 006
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: `GET /dashboard/data` ejecuta una función de 270 líneas que agrega datos de 10+ tablas secuencialmente, bloqueando el request thread hasta 500ms. Análisis LLM y backtest bloquean el request hasta 60s — el browser queda colgado.

**Business impact**: Un dashboard que tarda 500ms en cada poll degrada la experiencia durante mercado activo. Un endpoint que puede tardar 60s es un timeout garantizado y bloquea el thread del servidor para todos los demás requests.

**Success signal**: `GET /dashboard/data` p95 < 100ms. `POST /jobs/llm-analysis` responde en < 100ms siempre, sin importar qué tan lento sea OpenCode.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Trader | Desktop | Mercado activo | Dashboard cargando rápido en cada poll | No puede esperar 500ms para ver posiciones |
| Frank | Developer | Desktop | Local | Lanzar análisis LLM sin que el browser se cuelgue | No puede depender de timeouts del browser |

**Primary user**: Frank — Trader.

---

## WHAT — Constraints

**Architecture**:
- [ ] `DashboardDataQuery` no importa ningún use case de escritura — solo lectura
- [ ] Los jobs en `BackgroundJobRunner` corren en `ThreadPoolExecutor(max_workers=3)` — no asyncio
- [ ] Timeout por job: 60s para LLM analysis y backtest; 300s para opportunity scan
- [ ] Un job marcado como `running` por más de su timeout → se marca `failed` con error `"timeout"`
- [ ] El endpoint `/jobs/{id}` es públicamente accesible (sin auth) — los resultados no son sensibles

**Module-specific rules**:
- [ ] `DashboardDataQuery` puede leer de múltiples tablas — pero no puede hacer writes ni llamar use cases
- [ ] `background_jobs` tabla es la única fuente de verdad para el estado de un job
- [ ] `BackgroundJobRunner` nunca borra jobs — solo cambia su status
- [ ] Jobs con status `success` o `failed` de más de 7 días: se pueden limpiar con un job de mantenimiento (no en este issue)

**Module context**:
- Archivos a modificar: `app/api/dashboard.py` (reemplazar función de 270 líneas)
- Nuevos archivos: `app/infrastructure/db/read_models/dashboard_query.py`, `app/application/services/job_runner.py`, `app/interfaces/api/routes/jobs_routes.py`
- Nueva tabla: `background_jobs`

---

## HOW — Implementation Approach

**DashboardDataQuery** (RF-501):
1. `app/infrastructure/db/read_models/dashboard_query.py`
2. Queries SQLAlchemy (o raw SQL con `connection.execute()` si SQLAlchemy completo llega en Fase 6):
   - Query 1: `trades` (open) + `signals` (pending) + `patterns` (recent) — JOIN optimizado
   - Query 2: `news_cache` + `scanner_results` + `daily_watchlist` — caché de mercado
   - Query 3: `account_snapshots` (latest) + `position_snapshots` (open) — P&L
3. Devuelve `DashboardView` dataclass — no dicts crudos
4. Reemplaza la función de 270 líneas en `GET /dashboard/data` handler
5. **Target**: < 100ms en SQLite con WAL mode en Raspberry Pi

**Background Jobs** (RF-502):
1. Tabla `background_jobs` creada con migración (compatible con Fase 6)
2. `app/application/services/job_runner.py`:
   ```python
   class BackgroundJobRunner:
       def __init__(self, engine, max_workers=3):
           self._pool = ThreadPoolExecutor(max_workers=max_workers)
           self._engine = engine
       
       def submit(self, job_type: str, fn: Callable, **params) -> str:
           job_id = str(uuid4())
           self._save_job(job_id, job_type, PENDING, params)
           self._pool.submit(self._run, job_id, fn, params)
           return job_id
       
       def _run(self, job_id, fn, params):
           self._update_status(job_id, RUNNING, started_at=now())
           try:
               result = fn(**params)
               self._update_status(job_id, SUCCESS, result=result, completed_at=now())
           except TimeoutError:
               self._update_status(job_id, FAILED, error="timeout", completed_at=now())
           except Exception as e:
               self._update_status(job_id, FAILED, error=str(e), completed_at=now())
   ```
3. Los jobs LLM y backtest wrappean llamadas existentes con timeout via `concurrent.futures.wait()`

**Jobs routes** (RF-502):
```python
POST /jobs/llm-analysis  { symbol }  → { job_id }  # respuesta < 100ms
POST /jobs/backtest      { symbol }  → { job_id }
POST /jobs/opportunity-scan          → { job_id }
GET  /jobs/{job_id}                  → { status, progress_pct, result?, error? }
GET  /jobs?type=llm-analysis&status=running
```

**Migración de endpoints existentes**:
- `GET /candidate-analysis/{symbol}` → ahora devuelve `{ job_id }` en lugar de esperar resultado
- `GET /backtest/{symbol}` → ahora devuelve `{ job_id }` con link a `GET /jobs/{job_id}`
- El frontend del dashboard actualiza para hacer polling

**Read models para reportes** (RF-503):
- `GET /reports` y `GET /reports/{id}` leen de `analysis_reports` — ya es correcto, verificar que no hace joins innecesarios

**Events**:
- Publishes: `LLMAnalysisCompleted` (via event bus cuando job de análisis termina con éxito)
- Consumes: none

---

## Code Search (MANDATORY)

- [x] Función de 270 líneas en `dashboard.py`: líneas ~670-940 — reemplazar con `DashboardDataQuery`
- [x] `/candidate-analysis/{symbol}` handler: `api/main.py:X` — convertir a async job
- [x] `/backtest/{symbol}` handler — convertir a async job
- [x] `background_jobs` table: no existe aún — crear

**Reuse decision**:
- Reuse as-is: `BacktestEngine` (llamarlo desde el job thread), `OpenCodeLLMAdapter` (Issue 001)
- Replace: función de 270 líneas → `DashboardDataQuery`
- Build new: `BackgroundJobRunner`, `jobs_routes.py`, `DashboardDataQuery`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-501, RF-502, RF-503, performance targets |
| Interface design | `docs/dev/artifacts/refactor/06-interface-design.md` | Job API design |

---

## Acceptance Criteria

- [ ] `GET /dashboard/data` p95 < 100ms (medir con `time curl http://localhost:8088/dashboard/data`)
- [ ] `DashboardDataQuery` no tiene más de 3 queries a DB
- [ ] `DashboardDataQuery` no importa ningún use case de escritura
- [ ] `POST /jobs/llm-analysis { "symbol": "AAPL" }` responde en < 100ms con `{ job_id }`
- [ ] `GET /jobs/{job_id}` refleja `status: running` mientras el job corre
- [ ] `GET /jobs/{job_id}` refleja `status: success` y `result` cuando termina
- [ ] Job LLM que tarda > 60s → status `failed` con `error: "timeout"`
- [ ] `GET /health` responde < 100ms mientras hay 3 jobs corriendo en el ThreadPool
- [ ] El dashboard muestra resultados del analysis LLM cuando el job termina (frontend hace polling)
- [ ] Todos los tests existentes pasan

## Definition of Done

- [ ] Todos los acceptance criteria verificados
- [ ] Test de `DashboardDataQuery`: devuelve datos correctos para DB con datos de test
- [ ] Test de `BackgroundJobRunner`: job exitoso, job fallido, timeout
- [ ] Test: `POST /jobs/llm-analysis` → `GET /jobs/{id}` → status transitions correctas
- [ ] Mypy sin errores nuevos
- [ ] Issue movido a `done/`
