# Issue 001: Phase 0 — Quick Wins

**Module**: refactor
**Type**: AFK
**Effort**: M
**Blocked by**: None
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema pierde su modo operativo (paper/live) y estado de pausa en cada restart de la Raspberry Pi. Además, la lógica de llamada a OpenCode está duplicada en 3 archivos distintos, haciendo que cualquier cambio en el LLM adapter requiera editar 3 lugares.

**Business impact**: Si la Pi reinicia (corte de luz, actualización de kernel), el operador no sabe en qué modo quedó el sistema. Un restart sin saberlo puede dejar el sistema en modo paper cuando debería estar en live, o viceversa. La duplicación del adapter LLM genera bugs silenciosos cuando los 3 implementaciones divergen.

**Success signal**: Tras un restart de la app, `GET /system/status` devuelve el mismo `mode` e `is_paused` que tenía antes de reiniciar. `grep -r "_call_opencode" app/` devuelve exactamente 1 resultado.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Trader | Desktop + móvil | Casa/Pi via Tailscale | Saber en qué modo está el sistema tras cualquier restart | No puede estar mirando el sistema constantemente |
| Frank | Developer | Desktop + terminal | Local / Pi via SSH | Un solo lugar donde modificar la llamada a OpenCode | Cada bug en producción tiene impacto real |

**Primary user**: Frank — Trader (el estado persistente es crítico para operación segura).

---

## WHAT — Constraints

**Architecture**:
- [ ] `control_settings` es la fuente de verdad para `trading_mode` e `is_paused` — no `settings.py`
- [ ] El adapter OpenCode consolidado debe estar en `app/infrastructure/llm/opencode_adapter.py`
- [ ] No se importa el adapter duplicado de `llm/agent.py`, `analysis/pipeline.py`, `telegram_bot.py`
- [ ] El symbol se valida con `SAFE_SYMBOL_RE` antes de incluirlo en cualquier prompt
- [ ] El context manager `transaction()` usa SQLAlchemy session (no `sqlite3` directo)

**Module-specific rules**:
- [ ] `is_paused` y `trading_mode` se escriben a DB al cambiar, no solo al arrancar
- [ ] Si `control_settings` no existe aún, el bootstrap lee `.env` y crea la tabla + los valores
- [ ] Los secrets no aparecen en logs — usar `[REDACTED]` si se loguea un setting

**Module context**:
- Archivos principales afectados: `app/infrastructure/llm/opencode_adapter.py`, `app/llm/agent.py`, `app/analysis/pipeline.py`, `app/notifications/telegram_bot.py`, `app/system/controller.py`, `app/db/database.py`

---

## HOW — Implementation Approach

**Backend — Consolidar OpenCode adapter** (RF-001):
1. Verificar que `app/infrastructure/llm/opencode_adapter.py` existe y tiene `_call_opencode()`
2. Añadir validación de `OPENCODE_BIN` path al instanciar: `Path(settings.OPENCODE_BIN).resolve().exists()`
3. Añadir `SAFE_SYMBOL_RE = re.compile(r'^[A-Z0-9./=]{1,20}$')` y usarlo antes de construir el prompt
4. En `llm/agent.py`: eliminar `_call_opencode()` local, importar y usar `OpenCodeAdapter`
5. En `analysis/pipeline.py`: igual
6. En `notifications/telegram_bot.py`: igual (timeout diferente — pasar como parámetro al adapter)

**Backend — Transaction context manager** (RF-002):
1. Crear `app/infrastructure/db/session.py` con `@contextmanager get_session(engine) -> Session`
2. El context manager hace `session.commit()` al salir sin excepción, `session.rollback()` con excepción
3. No romper el código existente — el context manager es nuevo, los callers existentes se migran en Fase 2

**Backend — Persistir estado operativo** (RF-003):
1. Crear tabla `control_settings` con Alembic migration o SQL directo (Alembic completo llega en Fase 6, por ahora usar `CREATE TABLE IF NOT EXISTS` en `db_init.py`)
2. En `bootstrap/db_init.py` (nuevo o en `run.py`): leer `PAPER_TRADING_ONLY` e `is_paused` de settings → insertar en `control_settings` si no existen
3. En `app/system/controller.py`: al llamar `set_mode()` y `pause()`/`resume()`, escribir a `control_settings` además de mutar la variable en memoria
4. Al arrancar `SystemController`, leer `trading_mode` e `is_paused` de `control_settings` en lugar de solo de `settings.py`

**Backend — Logging estructurado** (RF-004):
1. Añadir `structlog` como dependencia (`pip install structlog`)
2. Configurar en `run.py` o `bootstrap/logging_setup.py`
3. Reemplazar `logging.getLogger()` por `structlog.get_logger()` en módulos críticos: `llm/loop.py`, `positions/manager.py`, `system/controller.py`
4. Añadir `symbol=` y `trade_id=` como campos bound al logger en los use cases (Fase 2 completará esto)

**Events**:
- Publishes: none (el event bus se crea en Fase 3)
- Consumes: none

---

## Code Search (MANDATORY antes de escribir código)

- [x] Adapter existente verificado: `app/infrastructure/llm/opencode_adapter.py` — existe, no se usa
- [x] Duplicados verificados: `_call_opencode()` en `agent.py:73`, `pipeline.py:282`, `telegram_bot.py:37`
- [x] `control_settings` table: no existe aún — crear nueva
- [x] `SystemController` verificado: `app/system/controller.py` (90 LOC) — muta `settings.py` directamente
- [x] `structlog` en requirements.txt: verificar si ya existe

**Reuse decision**:
- Reuse as-is: `opencode_adapter.py` (ya tiene la implementación correcta)
- Extend: `SystemController.set_mode()` (añadir escritura a DB)
- Build new: tabla `control_settings`, `bootstrap/db_init.py`, `infrastructure/db/session.py`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-001, RF-002, RF-003, RF-004 |
| Architecture map | `docs/dev/artifacts/refactor/03-architecture-map.md` | OpenCode adapter location |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | Subprocess hardening rules |
| Design concept | `docs/dev/artifacts/refactor/01-design-concept.md` | Bootstrap .env → control_settings |

---

## Acceptance Criteria

- [ ] `grep -r "_call_opencode\|def _call_opencode" app/llm/ app/analysis/ app/notifications/` → 0 resultados
- [ ] `app/infrastructure/llm/opencode_adapter.py` tiene `SAFE_SYMBOL_RE` y lo usa
- [ ] `app/infrastructure/llm/opencode_adapter.py` valida `OPENCODE_BIN` path al instanciar
- [ ] Symbol con caracteres especiales (`;`, `\n`) pasado al adapter → `ValueError`
- [ ] Tabla `control_settings` creada en DB al arrancar la app
- [ ] `trading_mode` e `is_paused` en `control_settings` tras el primer arranque
- [ ] Cambiar modo → valor persiste en `control_settings` → restart → mismo modo al arrancar
- [ ] `structlog` configurado — los logs incluyen `event=` key
- [ ] Todos los tests existentes pasan sin regresiones

## Definition of Done

- [ ] Todos los acceptance criteria verificados
- [ ] Tests de unidad para `OpenCodeAdapter.analyze_signal()` con symbol inválido → ValueError
- [ ] Test de integración: arrancar app → leer `trading_mode` de `control_settings`
- [ ] Mypy sin errores nuevos en archivos modificados
- [ ] Issue movido a `done/`
- [ ] `.state/project-map.yaml` `phase_0` → `issues_completed: 1`
