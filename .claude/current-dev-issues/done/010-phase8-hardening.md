# Issue 010: Phase 8 — Hardening Final

**Module**: refactor
**Type**: AFK
**Effort**: M
**Blocked by**: 009
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema corre como servicio systemd sin hardening — cualquier proceso en la Pi puede leer las variables de entorno. Los secretos están en `.env` con permisos por defecto. Los security headers de FastAPI no están configurados, exponiendo el dashboard a clickjacking en la red Tailscale.

**Business impact**: Aunque el acceso es privado via Tailscale, el hardening es necesario para proteger los secrets del sistema (API keys, tokens), limitar el blast radius si el proceso se compromete, y garantizar que el codebase no tiene code paths muertos de SQLite que puedan confundir al developer en el futuro.

**Success signal**: `systemctl show ibkr-trader | grep NoNewPrivileges` devuelve `yes`. `grep -r "sqlite3\|PRAGMA\|AUTOINCREMENT" app/` devuelve 0 resultados. Security headers presentes en todas las responses.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Developer | Terminal Pi | Producción | Sistem hardened sin cambios de comportamiento | No puede introducir regresiones funcionales |

**Primary user**: Frank — Developer.

---

## WHAT — Constraints

**Architecture**:
- [ ] `systemd` service usa `EnvironmentFile` para secretos — no `Environment=` en el unit file
- [ ] `.env.secret` tiene `chmod 600` y está en `.gitignore`
- [ ] No hay `shell=True` en ningún subprocess del codebase
- [ ] No hay raw SQL `f-strings` con interpolación de variables de usuario
- [ ] Los security headers se añaden via middleware en FastAPI, no en nginx (no hay nginx)

**Module-specific rules**:
- [ ] El CORS middleware solo permite el host de Tailscale (no `*`)
- [ ] Eliminar `SQLiteXxxRepository` clases si quedaron como code paths paralelos
- [ ] El `OPENCODE_BIN` se valida con `Path.resolve().exists()` y `os.access(path, os.X_OK)`
- [ ] El output de OpenCode se parsea solo con `json.loads()` — sin `eval()` en ningún lado

**Module context**:
- Archivos a modificar: `/etc/systemd/system/ibkr-trader.service` (fuera del repo), `app/interfaces/api/app.py` (middleware), `app/infrastructure/llm/opencode_adapter.py` (subprocess hardening)
- Archivos a eliminar: SQLite-specific code paths si quedan

---

## HOW — Implementation Approach

**systemd hardening** (RF-801):
```ini
[Service]
User=frankpach
Group=frankpach
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/home/frankpach/ibkr-bot
ReadWritePaths=/home/frankpach/ibkr-bot/db
EnvironmentFile=/home/frankpach/ibkr-bot/.env.secret

# Eliminar: Environment=TELEGRAM_BOT_TOKEN=... (no inline en unit file)
```

Mover de `.env` a `.env.secret` (chmod 600, gitignored):
- `TELEGRAM_BOT_TOKEN`
- `API_CONTROL_KEY`
- `API_ADMIN_KEY`
- `SECRET_ENCRYPTION_KEY`
- `LLM_API_KEY` (si aplica)

**Security headers** (RF-802):
```python
# app/interfaces/api/app.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://100.x.x.x"],  # solo IP Tailscale de la Pi
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-Control-Key", "X-Admin-Key", "Content-Type"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
```

**Subprocess hardening completo** (RF-803):
1. `OpenCodeLLMAdapter`: añadir `os.access(bin_path, os.X_OK)` además de `exists()`
2. Verificar que no hay `shell=True` en ningún subprocess del codebase: `grep -r "shell=True" app/`
3. El output de OpenCode: asegurar que solo `json.loads()` — `grep -r "eval(" app/`
4. Añadir `env={}` al subprocess para no pasar el environment completo a OpenCode

**Eliminar SQLite code paths** (RF-804):
1. `grep -r "sqlite3\|PRAGMA\|AUTOINCREMENT" app/` — eliminar todos
2. Si quedaron repositorios SQLite-specific: eliminar
3. `check_same_thread` en connection args: solo para SQLite — ya manejado en `container.py` con branching por URL

**Cleanup final**:
- Eliminar endpoints deprecados que ya no se usan: `/orders/preview` (si fue reemplazado internamente)
- Verificar que `app/system/controller.py` fue reemplazado completamente
- Verificar que las lambdas en scheduler fueron reemplazadas por funciones nombradas

**Events**:
- Publishes: none
- Consumes: none

---

## Code Search (MANDATORY)

- [x] `shell=True` en subprocess: `grep -r "shell=True" app/` — debe ser 0
- [x] `eval(` en codebase: `grep -r "eval(" app/` — debe ser 0 (para output de LLM)
- [x] `sqlite3` direct import: `grep -r "import sqlite3" app/` — debe ser 0 post-Fase 6
- [x] `PRAGMA` en SQL strings: `grep -r "PRAGMA" app/` — debe ser 0
- [x] Inline secrets en systemd unit file: verificar si existen

**Reuse decision**:
- Reuse as-is: `OpenCodeLLMAdapter` (solo añadir `X_OK` check y `env={}`)
- Extend: `app/interfaces/api/app.py` (añadir middleware)
- Build new: `.env.secret` setup, systemd unit file actualizado

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-801 a RF-804 con ACs |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | Security constraints, subprocess rules |
| Why Decisions | `docs/dev/artifacts/refactor/05-why-decisions.md` | DEC-008 (auth), DEC-010 (secrets) |

---

## Acceptance Criteria

- [ ] `systemctl show ibkr-trader | grep NoNewPrivileges` → `NoNewPrivileges=yes`
- [ ] `grep -r "sqlite3\|PRAGMA\|AUTOINCREMENT" app/` → 0 resultados
- [ ] `grep -r "shell=True" app/` → 0 resultados
- [ ] `grep -r "eval(" app/` → 0 resultados (excepto comentarios)
- [ ] `curl -I http://pi:8088/health | grep X-Frame-Options` → `X-Frame-Options: DENY`
- [ ] `curl -I http://pi:8088/health | grep X-Content-Type-Options` → `nosniff`
- [ ] `.env.secret` existe en Pi con `chmod 600` y no está en git
- [ ] `OpenCodeLLMAdapter` verifica `os.access(bin_path, os.X_OK)` al instanciar
- [ ] Symbol con caracteres de injection (`;`, `\n`, `$(cmd)`) → `ValueError` antes de subprocess
- [ ] Todos los tests pasan (no regressions)
- [ ] El sistema funciona correctamente en producción tras los cambios

## Definition of Done

- [ ] Todos los acceptance criteria verificados
- [ ] Security audit rápido: revisar todos los endpoints en `control_routes.py` con tabla de permisos del PRD
- [ ] `.gitignore` incluye `.env.secret`
- [ ] `SECURITY.md` o sección en README describe cómo gestionar secretos en producción
- [ ] Mypy sin errores nuevos
- [ ] Issue movido a `done/`
