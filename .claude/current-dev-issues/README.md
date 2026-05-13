# live-dashboard — Development Issues

**Module**: live-dashboard
**Started**: 2026-05-13
**Status**: Phase 5 — Execution ready
**Spec**: docs/superpowers/specs/2026-05-13-live-dashboard-design.md

## Objetivo

Dashboard con datos reales de IBKR: balance vivo, P&L flotante por posición,
equity curve 30 días, e interactividad futura (Fase 2).

## Issue List

| Issue | Título | Effort | Bloqueado por | Estado |
|-------|--------|--------|---------------|--------|
| LD-001 | DB Foundation — 4 tablas + SymbolParameter fields | S | — | pending |
| LD-002 | Data Collection Jobs — position/account/news/scanner | M | LD-001 | pending |
| LD-003 | Enrich /dashboard/data endpoint | S | LD-001 | pending |
| LD-004 | Dashboard Frontend A — header, stats, positions, charts | M | LD-003 | pending |
| LD-005 | Dashboard Frontend B — symbol, news, trends, universo, controls | M | LD-004 | pending |

## Dependency Graph

```
LD-001 (DB Foundation)
  ├── LD-002 (Data Jobs)    — escribe a las tablas
  └── LD-003 (API endpoint) — lee de las tablas
        └── LD-004 (Frontend A) — consume endpoint
              └── LD-005 (Frontend B) — extiende Frontend A
```

## Parallelizable Groups

- **Grupo A**: LD-001 solo (sin deps)
- **Grupo B**: LD-002 + LD-003 en paralelo (después de LD-001)
- **Grupo C**: LD-004 → LD-005 secuencial

## Orden recomendado

```
1. LD-001  DB Foundation  (S, ~1h)
2. LD-002  Data Jobs       (M, ~3h)  ← en paralelo con LD-003
3. LD-003  API endpoint    (S, ~1.5h) ← en paralelo con LD-002
4. LD-004  Frontend A      (M, ~3h)
5. LD-005  Frontend B      (M, ~3h)
```
