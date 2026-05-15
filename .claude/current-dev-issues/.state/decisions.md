# Decisions Log: refactor

**Module**: refactor
**Last Updated**: 2026-05-14

## Module: refactor — 2026-05-14

### DEC-001: SQLAlchemy como ORM — committed
Decidido por el usuario. Reemplaza raw SQL en database.py (1,277 LOC). Facilita portabilidad SQLite→PostgreSQL.

### DEC-002: Alembic para migraciones — committed
Reemplaza ALTER TABLE en try/except. Revisiones numeradas con upgrade() y downgrade() siempre. alembic upgrade head al startup.

### DEC-003: Ports/Adapters con capas explícitas — committed
domain/ → application/ports/ + use_cases/ → infrastructure/ → interfaces/. Tests de use cases sin infra real (mocks).

### DEC-004: Eliminar HTTP interno — committed
llm/loop.py y positions/manager.py dejan de llamar httpx a localhost. Llaman use cases Python directamente.

### DEC-005: Event bus in-process síncrono — committed
Handlers registrados en container.py. Publishers emiten eventos. No Redis/RabbitMQ. Handlers sync.

### DEC-006: Persistir estado en DB (control_settings) — committed
is_paused, trading_mode, ib_port y todos los parámetros de riesgo en tabla control_settings SQLAlchemy. Restart preserva estado.

### DEC-007: Control plane /control — committed
React SPA accesible desde header del dashboard. Gestiona API keys (cifradas), puertos IB, DB URL, parámetros de riesgo, jobs/scheduler.

### DEC-008: Control Key + Admin Key — committed
X-Control-Key para operaciones estándar. X-Admin-Key para alto impacto (modo live, API keys, puertos IB, DB URL, aprobar símbolos).

### DEC-009: ThreadPoolExecutor para jobs lentos — committed
max_workers=3. Estado en background_jobs (SQLAlchemy). API de polling: POST /jobs/{type} → {job_id}, GET /jobs/{id} → {status, result}.

### DEC-010: Fernet (cryptography) para secrets — pending-confirmation
cryptography.Fernet con SECRET_ENCRYPTION_KEY env var. Campos is_secret=True cifrados. Nunca en plain text en API responses.
