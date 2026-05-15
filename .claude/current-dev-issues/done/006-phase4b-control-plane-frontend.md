# Issue 006: Phase 4b — Control Plane Frontend

**Module**: refactor
**Type**: HITL
**Effort**: M
**Blocked by**: 005
**Requires review**: true

---

## WHY — The Human Problem

**User pain**: El operador no tiene forma de ver el estado actual del sistema (modo, pausa, P&L) sin navegar activamente al dashboard. No hay una UI para cambiar parámetros, gestionar API keys ni ver el historial de cambios. Todo requiere SSH.

**Business impact**: Sin UI de configuración, el operador no puede ajustar parámetros durante mercado activo desde su browser o móvil. La barra de estado persistente elimina la ansiedad de "¿en qué modo quedó el sistema tras el restart?"

**Success signal**: El operador cambia `max_risk_pct` desde el browser en < 30 segundos. La barra de estado muestra `● PAPER | Puerto: 4002 | Activo` en todas las páginas sin recargar.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Trader | Desktop browser | Mercado activo | Ver estado del sistema sin buscar, ajustar parámetros en segundos | Tiempo limitado durante mercado |
| Frank | Trader | Móvil | Fuera de oficina | Ver si el sistema está activo y en qué modo | Pantalla pequeña, táctil |

**Primary user**: Frank — Trader en desktop.

---

## WHAT — Constraints

**Architecture**:
- [ ] Los componentes React están embebidos en `dashboard.py` (mismo patrón que el dashboard existente)
- [ ] `SystemStatusBar` hace polling a `GET /control/status` cada 30s — sin auth
- [ ] Los campos de tipo secret (`is_secret=True`) usan `<input type="password">` y nunca muestran el valor en plain text
- [ ] El botón "Cambiar a LIVE" abre un modal con campo `X-Admin-Key` explícito
- [ ] Settings con `requires_restart=True` muestran banner `⚠ Requiere restart` antes y después de guardar

**Module-specific rules**:
- [ ] La URL refleja la sección activa: `/control?section=risk`
- [ ] Los errores de validación del backend (422) se muestran inline junto al campo
- [ ] El audit log se muestra paginado, sin descargar toda la tabla
- [ ] Los botones de acciones destructivas (cambiar a live, pausar) tienen estado de loading mientras esperan respuesta

**Module context**:
- Archivos a modificar: `app/api/dashboard.py` (añadir ruta `/control` y el componente)
- Nuevos componentes React: `SystemStatusBar`, `ControlPlaneApp`, 7 paneles, `ConfirmModeModal`

---

## HOW — Implementation Approach

**SystemStatusBar** (RF-401):
- Componente React: `{ mode, ib_port, is_paused, daily_pnl, ib_connected }`
- Polling: `setInterval(() => fetch('/control/status'), 30000)` con retry en error
- Renderiza: `● PAPER | Puerto: 4002 | ● Activo | P&L: +$23.40 | IB: ✓  [→ /control]`
- Color coding: PAPER = verde, LIVE = naranja, Pausado = amarillo, IB desconectado = rojo
- Añadir al layout HTML del dashboard existente (header)

**ControlPlaneApp** (RF-402):
- Página React en `/control` (nueva ruta en FastAPI, servida desde `control_routes.py`)
- Sidebar con 7 items: Operativo, Riesgo, Símbolos, Infraestructura, Jobs, API Keys, Audit Log
- URL param `?section=operational` (default), cambia al hacer click en sidebar
- Cada sección es un componente independiente

**Panel: Operativo** (RF-403):
- Modo paper/live: radio buttons. Click en LIVE → `ConfirmModeModal`
- Pausa/Reanuda: botones grandes con estado de loading. Solo Control Key
- Circuit Breaker: estado (activo/activado), threshold, botón reset (Control Key)
- `ConfirmModeModal`: campo `X-Admin-Key` tipo password, advertencia si hay posiciones abiertas, botón confirmar

**Panel: Riesgo** (RF-404):
- Campos editables inline: `max_positions`, `max_risk_pct`, `min_risk_usd`, `max_position_usd`, `capital_cap`
- Editar campo → botón `[Guardar]` aparece → click → `PUT /control/settings/{key}` con `X-Control-Key`
- Validación inline: error del backend (422) mostrado bajo el campo
- Toast de éxito: `✓ max_risk_pct actualizado a 1.5%`
- Sin banner de restart (todos son hot-reload)

**Panel: Infraestructura** (RF-405):
- Campos: `ib_host`, `opencode_bin`, `opencode_model`, `database_url`
- Requiere `X-Admin-Key` para guardar
- `database_url` y `opencode_bin` muestran banner `⚠ Requiere restart` al guardar
- Banner persistente en la página si hay settings pendientes de restart

**Panel: API Keys** (RF-406):
- Lista: `LLM_API_KEY: ••••••••  [Actualizar]`
- Click [Actualizar] → campo `<input type="password">` + botón guardar con `X-Admin-Key`
- Si `decryption_failed: true` en response → `⚠ No se puede leer — re-ingresa`
- Banner especial si algún secret tiene `decryption_failed: true`: "N secrets no pueden descifrarse — re-ingrésalos"

**Panel: Jobs** (RF-407):
- Tabla: `signal_processor | last: 2min | next: 13min | ● OK  [▶]`
- `[▶]` → `POST /control/jobs/{job_id}/trigger` con `X-Control-Key` → feedback en tabla
- Error del último run mostrado en tooltip

**Panel: Audit Log** (RF-408):
- Tabla paginada (50 por página): `occurred_at | event_type | changed_by | old_value | new_value`
- Load more button (no infinite scroll)
- Requiere Control Key para acceder a la sección

**Panel: Símbolos** (RF-403 adicional):
- Lista de símbolos aprobados con metadata
- Proposals pendientes con botón `[Aprobar]` (Admin Key) y `[Rechazar]` (Admin Key)

**Events**:
- Publishes: none (solo llama API)
- Consumes: none (polling REST, no WebSockets)

---

## Code Search (MANDATORY)

- [x] `app/api/dashboard.py`: patrón de React embebido en Python — replicar para `/control`
- [x] `app/api/auth.py`: `require_control_key` ya existe — los endpoints de control lo usan
- [x] Control routes: `control_routes.py` (Issue 005) — el frontend consume estos endpoints

**Reuse decision**:
- Reuse as-is: patrón de React embebido en dashboard.py — mismo enfoque para control plane
- Extend: el layout HTML del dashboard para añadir `SystemStatusBar` en el header
- Build new: `ControlPlaneApp` y todos sus paneles, `ConfirmModeModal`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-401 a RF-408 (frontend ACs) |
| Interface design | `docs/dev/artifacts/refactor/06-interface-design.md` | Mockups ASCII, Workflow 1, 2, 3 |
| Persona journey | `docs/dev/artifacts/refactor/02-persona-journey.md` | Journey steps del Trader con el control plane |

---

## Acceptance Criteria

- [ ] `SystemStatusBar` visible en el dashboard principal, actualiza cada 30s
- [ ] `SystemStatusBar` muestra modo correcto tras cambiar paper↔live (sin recargar)
- [ ] `/control?section=risk` carga directamente el panel de riesgo
- [ ] Editar `max_risk_pct` con valor válido → toast de éxito → audit log actualizado
- [ ] Editar `max_risk_pct` con `-0.5` → error inline bajo el campo
- [ ] Click "LIVE" → modal aparece con campo de Admin Key
- [ ] Modal con posiciones abiertas → advertencia visible antes de confirmar
- [ ] API Key panel: valor nunca visible, siempre `••••••••`
- [ ] Secret con `decryption_failed` → banner de advertencia visible en API Keys panel
- [ ] Settings con `requires_restart=True` → banner `⚠ Requiere restart` en UI tras guardar
- [ ] Jobs panel: trigger manual → estado de loading → tabla actualiza `last_run`
- [ ] Audit log paginado funciona, muestra 50 entradas por página

## Definition of Done

- [ ] Todos los acceptance criteria verificados manualmente en browser
- [ ] Probado en Chrome desktop (principal) y Chrome móvil (verificación básica)
- [ ] Sin errores de JavaScript en consola del browser
- [ ] La barra de estado no interrumpe el resto del dashboard cuando `/control/status` falla
- [ ] Code review aprobado (HITL)
- [ ] Issue movido a `done/`
