# Decisions: arch-refactor

**Module**: arch-refactor
**Documented**: 2026-05-14
**Status**: Planning complete — execution pending (Fase 0 next)

## D-01: SQL plano + repositorios (no ORM)

**Decision**: No SQLAlchemy, no SQLModel. SQL plano con repositorios por entidad.
**Why**: Codebase ya usa SQL plano eficazmente. ORM añade complejidad sin ganancia clara para trading. SQL plano es más legible, revisable y debuggeable. Repositorios proveen la indirección necesaria para cambiar backend.
**How to apply**: Todo SQL en `infrastructure/db/repositories/`. Ningún módulo de domain/application importa sqlite3 o psycopg.

---

## D-02: InProcessJobRunner con asyncio (no Celery/ARQ todavía)

**Decision**: Background jobs usando asyncio.Semaphore + asyncio.create_task. Estado de jobs en tabla `background_jobs` en DB.
**Why**: Proceso único hoy. Interfaz swappable: reemplazar InProcessJobRunner por CeleryJobRunner implementando la misma interfaz cuando la carga lo requiera.
**How to apply**: Fase 6 si se necesita escalar; Fase 9 para separación completa en workers.

---

## D-03: X-Control-Key auth (no JWT/OAuth) para control plane inicial

**Decision**: API key en header X-Control-Key leído de .env. Tres niveles: READ_ONLY, OPERATOR, ADMIN.
**Why**: Tailscale reduce radio de exposición. JWT agrega complejidad (rotación, expiración, storage) sin ganancia proporcional para un sistema de 1 usuario.
**How to apply**: Middleware en control_plane_routes.py. JWT diferido a Fase 8 si se requiere.

---

## D-04: No DDD puro — use cases + ports + adapters

**Decision**: No Aggregates, no Domain Services formales, no Repositories como parte del domain.
**Why**: El dominio de trading de este sistema no tiene invariantes complejos que requieran Aggregates. Use cases + ports proveen suficiente separación para testabilidad y evolución.
**How to apply**: application/ports/ define interfaces. infrastructure/ implementa. domain/ solo entidades y eventos.

---

## D-05: No CQRS full — read models separados para dashboard

**Decision**: Un read model separado para dashboard/reportes. No event sourcing.
**Why**: El dashboard agrega datos de 15+ fuentes. Separar en DashboardQueryService evita que el dominio operativo quede acoplado a presentación. Event sourcing es overkill para este sistema.
**How to apply**: infrastructure/db/read_models/ con queries optimizadas para presentación.

---

## D-06: Feature flags temporales para rollback en Fases 1–2

**Decision**: USE_DIRECT_CALLS=true/false en .env para Fase 1. Se elimina después de 1 semana de operación estable.
**Why**: Fase 1 toca la ruta crítica de trading (loop.py → orders/place). Feature flag permite rollback sin revert de código.
**How to apply**: Verificar en execute_order.py qué path tomar. Eliminar al cerrar Fase 1.
