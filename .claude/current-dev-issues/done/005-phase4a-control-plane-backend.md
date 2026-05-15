# Issue 005: Phase 4a — Control Plane Backend

**Module**: refactor
**Type**: AFK
**Effort**: M
**Blocked by**: 004
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Para cambiar `max_risk_pct` o añadir una API key, el operador debe hacer SSH a la Pi, editar `.env`, y reiniciar el servicio — proceso de 3-5 minutos con riesgo de error. No hay validación, no hay audit trail, y el sistema queda inoperativo durante el restart.

**Business impact**: Durante mercado activo, 3-5 minutos de downtime para ajustar un parámetro de riesgo es inaceptable. La ausencia de audit trail hace imposible saber quién cambió qué y cuándo.

**Success signal**: `PUT /control/settings/max_risk_pct` con el nuevo valor → el próximo ciclo del RiskService usa el valor nuevo sin restart. El audit log tiene la entrada con el valor anterior y el nuevo.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Trader | Desktop | Mercado activo | Ajustar parámetros en segundos desde el browser | No puede hacer SSH durante mercado |
| Frank | Developer | Desktop | Local/Pi | Ver historial de cambios de configuración | El control plane debe ser seguro por defecto |

**Primary user**: Frank — Trader.

---

## WHAT — Constraints

**Architecture**:
- [ ] `UpdateControlSettingUseCase` es el único punto de escritura para `control_settings` — ningún route handler escribe directamente
- [ ] Los campos `is_secret=True` se cifran con `SecretManager` antes de persistir — nunca plain text en DB
- [ ] La API nunca devuelve el valor de campos `is_secret=True` — devuelve `"••••••••"` siempre
- [ ] `GET /control/status` y `GET /control/settings` son públicos (sin auth)
- [ ] `PUT /control/settings/*` de infraestructura/secrets requiere `X-Admin-Key`
- [ ] Los errores de validación devuelven HTTP 422 con detalle del campo y razón

**Module-specific rules**:
- [ ] `SettingValidator` rechaza: valores fuera de rango, tipos incorrectos, enums inválidos
- [ ] Settings con `requires_restart=True`: persisten en DB pero devuelven `restart_required: true` en response
- [ ] `SECRET_ENCRYPTION_KEY` nunca entra en `control_settings` — solo en `.env.secret`
- [ ] Si al descifrar un secret falla → devolver `{ decryption_failed: true }` en `GET /control/settings/{key}` (no error 500)

**Module context**:
- Nuevos archivos: `app/interfaces/api/routes/control_routes.py`, `app/application/use_cases/update_control_setting.py`, `app/application/services/setting_validator.py`, `app/infrastructure/system/secret_manager.py`

---

## HOW — Implementation Approach

**SecretManager** (RF-302 parcial):
1. `app/infrastructure/system/secret_manager.py`:
   ```python
   class SecretManager:
       def __init__(self): 
           key = os.environ["SECRET_ENCRYPTION_KEY"]
           self._fernet = Fernet(key.encode())
       def encrypt(self, value: str) -> str: ...
       def decrypt(self, encrypted: str) -> str: ...
   ```
2. Si `SECRET_ENCRYPTION_KEY` no está en env → `RuntimeError` claro al instanciar

**SettingValidator** (RF-409 parcial):
1. `app/application/services/setting_validator.py`
2. Registro de settings con tipo, rango, enum, `is_secret`, `requires_restart`:
   ```python
   SETTING_REGISTRY = {
       "max_risk_pct": SettingDef(type=float, min=0.001, max=0.10, hot_reload=True),
       "max_positions": SettingDef(type=int, min=1, max=20, hot_reload=True),
       "capital_cap": SettingDef(type=float, min=100.0, hot_reload=True),
       "database_url": SettingDef(type=str, is_secret=False, requires_restart=True),
       "telegram_bot_token": SettingDef(type=str, is_secret=True, requires_restart=True),
       "llm_api_key": SettingDef(type=str, is_secret=True, hot_reload=True),
       # ... resto
   }
   ```

**UpdateControlSettingUseCase** (RF-409):
1. Input: `UpdateSettingCommand(key, value, changed_by, ip_address)`
2. Flujo: `SettingValidator.validate(key, value)` → cifrar si `is_secret` → persist en `control_settings` → publish `ControlSettingChanged`
3. `HotReloadHandler`: si `requires_restart=False`, aplica valor en caliente al `RiskService` o `SystemController`
4. Devuelve `UpdateSettingResult(key, requires_restart, message)`

**Control routes** (RF-401-409 backend):
```python
# control_routes.py
GET  /control/status          → sin auth → GetSystemStatusQuery
GET  /control/settings        → sin auth → GetAllSettingsQuery (secrets como "••••••••")
GET  /control/settings/{key}  → sin auth → GetSettingQuery
PUT  /control/settings/{key}  → Control o Admin Key (según registry) → UpdateControlSettingUseCase
GET  /control/jobs            → sin auth → GetSchedulerStatusQuery
POST /control/jobs/{job_id}/trigger → Control Key → TriggerJobUseCase
POST /control/pause           → Control Key → PauseSystemUseCase
POST /control/resume          → Control Key → ResumeSystemUseCase
POST /control/mode/{mode}     → Admin Key → ChangeTradingModeUseCase
POST /control/circuit-breaker/reset → Control Key → ResetCircuitBreakerUseCase
GET  /control/audit           → Control Key → GetAuditLogQuery (paginado)
POST /control/symbols/approve/{symbol} → Admin Key → ApproveSymbolUseCase
```

**Auth middleware** (RF-408):
- `require_control_key(x_control_key: str = Header(None))` — FastAPI Depends
- `require_admin_key(x_admin_key: str = Header(None))` — FastAPI Depends
- Ambas claves se leen de `control_settings` (o `.env` si `control_settings` no tiene la clave)

**GetSchedulerStatusQuery**:
- Consulta APScheduler para cada job: `next_run_time`, `last_run_time`, `status`
- Devuelve lista de jobs con `{ job_id, name, last_run, next_run, last_status, last_error }`
- Los `last_run_time` y `last_error` se guardan en `control_settings` por job (clave `job_status_{job_id}`)

**Events**:
- Publishes: `ControlSettingChanged` (via event bus) → `AuditLogHandler`, `HotReloadHandler`
- Consumes: none

---

## Code Search (MANDATORY)

- [x] `app/api/auth.py`: 10 LOC — `require_control_key` ya existe, extender con `require_admin_key`
- [x] `control_settings` table: creada en Issue 001 — usar aquí
- [x] `audit_log` table: creada en Issue 004 — usar aquí
- [x] `cryptography` en requirements: verificar si ya instalada, sino añadir

**Reuse decision**:
- Reuse as-is: `app/api/auth.py` `require_control_key` — extender con `require_admin_key`
- Extend: `ChangeTradingModeUseCase` (Issue 004) — añadir validación desde route
- Build new: `SecretManager`, `SettingValidator`, `UpdateControlSettingUseCase`, `control_routes.py`, 4 query objects

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-401-409, tabla de permisos por endpoint |
| Interface design | `docs/dev/artifacts/refactor/06-interface-design.md` | API endpoints completos, Workflow 3 (API keys) |
| Why Decisions | `docs/dev/artifacts/refactor/05-why-decisions.md` | DEC-008 (auth levels), DEC-010 (Fernet) |

---

## Acceptance Criteria

- [ ] `PUT /control/settings/max_risk_pct` con valor válido → 200 OK, persiste, audit_log actualizado
- [ ] `PUT /control/settings/max_risk_pct` con valor `-0.5` → 422 con mensaje de error claro
- [ ] `PUT /control/settings/max_risk_pct` sin `X-Control-Key` → 403
- [ ] `PUT /control/settings/telegram_bot_token` sin `X-Admin-Key` → 403
- [ ] `GET /control/settings` → `telegram_bot_token` value es `"••••••••"`, nunca el valor real
- [ ] `PUT /control/settings/telegram_bot_token` → valor cifrado en DB (verificable con SQL directo)
- [ ] `GET /control/settings/telegram_bot_token` → `{ "value": "••••••••", "is_secret": true }`
- [ ] Secret con `SECRET_ENCRYPTION_KEY` incorrecto → `{ "decryption_failed": true }` en response, no 500
- [ ] `GET /control/jobs` → lista con `last_run`, `next_run`, `status` para cada job
- [ ] `POST /control/jobs/signal_processor/trigger` → job ejecuta + `last_run` actualiza
- [ ] `GET /control/audit` → entrada por cada `PUT /control/settings/*`
- [ ] Hot-reload: cambiar `max_risk_pct` → el próximo `validate_order()` usa el nuevo valor sin restart

## Definition of Done

- [ ] Todos los acceptance criteria verificados
- [ ] Tests de `UpdateControlSettingUseCase`: validación, cifrado, evento, hot-reload
- [ ] Test: `GET /control/settings` no revela secrets
- [ ] Test: auth levels correctos por endpoint
- [ ] Mypy sin errores nuevos
- [ ] Issue movido a `done/`
