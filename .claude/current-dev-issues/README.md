# dev-plan — Development Issues

**Module**: dev-plan
**Started**: 2026-05-07
**Status**: planning complete → ready for execution

---

## Issue List

| # | Title | Priority | Effort | Blocked by | Status |
|---|---|---|---|---|---|
| 001 | Settings centralization + MockIBClient | P0 | S | — | pending |
| 002 | IBDataLayer + IndicatorEngine | P0 | L | 001 | pending |
| 003 | PostMortem v2 — Fix BUG-001 | P0 | S | 001 | pending |
| 004 | QuantScorer + HardRules + DB + AnalysisPipeline | P1 | XL | 002 | pending |
| 005 | Migrations — agent + loop + telegram /analizar | P1 | M | 004 | pending |
| 006 | DailyDiscovery + ReturnEvaluator + Endpoints + MCP | P2 | L | 004, 005 | pending |

---

## Dependency Graph

```
001 (settings + mock)
    ├── 002 (IBDataLayer + IndicatorEngine)
    │       └── 004 (Scorer + HardRules + DB + Pipeline)
    │               ├── 005 (migrations agent + bot)
    │               │       └── 006 (discovery + evaluator + endpoints)
    │               └── 006 (discovery + evaluator + endpoints)
    └── 003 (postmortem fix) [independiente de 002]
```

---

## Parallelizable Groups

**Grupo A — Ejecutar en paralelo:**
- 001 primero (unblocks everything)
- Luego: 002 y 003 en paralelo (002 no bloquea 003)

**Grupo B — Secuencial:**
- 004 después de 002
- 005 después de 004
- 006 después de 004 y 005

**Orden recomendado de ejecución:**
1. 001 (S — rápido, desbloquea todo)
2. 002 + 003 en paralelo (002 es L, 003 es S)
3. 004 (XL — el core del sistema nuevo)
4. 005 (M — migraciones)
5. 006 (L — discovery + endpoints)

---

## PRD Coverage

| PRD REQ | Issue |
|---|---|
| REQ-01 (settings) | 001 |
| REQ-02 (MockIBClient) | 001 |
| REQ-03 (IBDataLayer) | 002 |
| REQ-04 (IndicatorEngine) | 002 |
| REQ-05 (QuantScorer) | 004 |
| REQ-06 (HardRules) | 004 |
| REQ-07 (AnalysisPipeline) | 004 |
| REQ-08 (PostMortem v2) | 003 |
| REQ-09 (DB tables) | 004 |
| REQ-10 (preprocessor migration) | 002 |
| REQ-11 (backtest migration) | 002 |
| REQ-12 (agent migration) | 005 |
| REQ-13 (DailyDiscovery) | 006 |
| REQ-14 (ReturnEvaluator) | 006 |
| REQ-15 (new endpoints) | 006 |
| REQ-16 (MCP tools) | 006 |

---

## Done

(vacío — issues completados se mueven aquí)
