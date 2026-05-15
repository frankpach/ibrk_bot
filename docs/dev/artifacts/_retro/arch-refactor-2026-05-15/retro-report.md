# Retrospective: arch-refactor Sprint

**Date**: 2026-05-15
**Duration**: ~1 day (all 10 issues + Sprint 1 DI fixes + docs + CI/CD)
**Commits**: 16 on `main` since sprint start
**Tests**: 934 passed, 55 pre-existing failures (scanner/legacy), 0 regressions introduced

---

## Sprint Summary

Transformed the IBKR AI Trader from a fragile monolith into a clean Hexagonal Architecture. All 10 planned issues (001–010) completed, plus an unplanned Sprint 1 that eliminated 4 residual DI anti-patterns discovered during the architecture review phase.

| Phase | Issues | Outcome |
|-------|--------|---------|
| Phase 0 — Quick Wins | 001 | OpenCodeAdapter consolidated, WAL mode, X-Control-Key |
| Phase 1 — Eliminate HTTP | 002 | httpx self-calls removed from llm/loop, positions/manager |
| Phase 2 — DI + Services | 003 | Container, use cases, 6 route files, run.py → 60 LOC |
| Phase 3 — Event Bus | 004 | EventBus, 7 domain events, AuditLogHandler |
| Phase 4a — Control Backend | 005 | control_settings DB, two-tier auth |
| Phase 4b — Control Frontend | 006 | React SPA at /control |
| Phase 5 — Background Jobs | 007 | ThreadPoolExecutor(3), job polling API |
| Phase 6 — SQLAlchemy | 008 | 23 ORM models, Alembic migrations, database.py deleted |
| Phase 7 — PostgreSQL | 009 | Dual-backend, parametrized tests |
| Phase 8 — Hardening | 010 | Security headers, subprocess hardening, systemd unit |
| Sprint 1 — DI Fixes | post | AlertManager, LLMSignalProcessor, dedup, pipeline broker |

---

## What Went Well

### 1. Architecture review caught 4 real bugs before deploy

The `/230-architecture-improvements` phase (before `/200-execution`) surfaced issues that would have caused silent failures in production:
- `pipeline._score()` httpx self-call → would fail silently if API server was under load
- `AlertManager.get_price_and_prev_close()` returning `(price, price)` → **alerts never fired** (pct_change = 0 always)
- `_dedup_instance` non-thread-safe → rare race on concurrent orders
- `LLMSignalProcessor` module-level globals → wrong broker used under concurrent scheduler threads

**Lesson**: Architecture review after execution is not optional polish — it catches correctness bugs masked by tests that patch the wrong symbols.

### 2. Subagent-driven development caught the prev_close regression that tests missed

The `test_alert_manager_with_mock_broker` test was patching `get_price_and_prev_close` entirely, which made the regression invisible. The code quality reviewer caught it by reading the actual logic path, not the test. Two-stage review (spec compliance → code quality) is worth the extra subagent cost.

**Lesson**: Tests that mock the method under test provide false confidence. Prefer end-to-end tests that mock at the infrastructure boundary (broker port) not the method being tested.

### 3. `test_container()` as the testing backbone

Having `test_container()` in `app/container.py` from Phase 2 enabled all subsequent sprint phases and Sprint 1 to write fast, isolated tests without IB Gateway or Telegram. The 34-minute test run (934 tests) ran entirely in-process with no external dependencies.

**Lesson**: Invest in the test factory early. The DI container's test variant pays for itself across every subsequent test.

### 4. Incremental issues (001→010) with rollback points

Each issue was small enough to commit independently. No issue required reverting any other. The ordering (quick wins → ports → services → events → control → DB) meant each phase had a clean integration point.

---

## What Cost Tokens / Time

### 1. Stale test patch targets (highest friction point)

The `tests/db/test_symbol_config_migration.py` had `from app.db import database` — a stale import from the deleted monolith. This blocked pytest collection and caused repeated confusion across the sprint. Similar pattern: tests patching `app.llm.loop._get_broker` (module-level global) that became `LLMSignalProcessor._broker` (instance attribute) after refactor — caused 5 test failures in Sprint 1 that needed per-test migration.

**Root cause**: Tests that patch internal implementation symbols (module globals, private methods) are coupled to the implementation, not the behavior.

**Token cost**: ~3 subagent round-trips to diagnose and fix patch targets across `test_signal_loop.py`, `test_migrations_005.py`, `test_issue002_eliminate_internal_http.py`.

### 2. `EventBus` subscription leak discovered late

The first Sprint 1 implementation subscribed `_on_system_paused` inside `AnalysisPipeline.run()`. This was a correctness bug (handler never unsubscribes, accumulates per pipeline run). It was caught by the code quality reviewer, not the spec reviewer. The fix (remove the subscription entirely) was the right call — but it added a review loop.

**Root cause**: The plan said "subscribe to SystemPaused for graceful abort" without flagging that EventBus has no unsubscribe. The plan was incomplete about the lifecycle constraint.

**Lesson for plan writing**: When a plan step uses a stateful resource (event bus, thread pool, connection pool), always specify the cleanup/lifecycle. "Subscribe X" → "Subscribe X in constructor, unsubscribe in teardown."

### 3. The `prev_close` regression

`AlertManager.get_price_and_prev_close()` was rewritten without checking what the old implementation actually returned for `prev_close`. The old code hit `/price/free/{symbol}` which returned a genuine `close` field from IBKR. The new code returned `(price, price)`. This required adding `IBrokerPort.get_prev_close()`, implementing it in `IBKRBrokerAdapter` via `reqHistoricalData`, and updating `MockBrokerAdapter` with a `prev_closes` dict.

**Token cost**: One full subagent round-trip (fix + re-review).

**Lesson**: When rewriting a function that fetches data, always trace WHERE the old data came from before discarding it. "Replace `_get_broker()` calls with `self._broker`" is safe. "Replace the entire fetching logic" requires reading the old implementation first.

### 4. Container import placement (minor)

`from app.alerts.manager import AlertManager` was placed as a local import inside `Container.__init__` to avoid a circular import — but the circular dependency actually lives only inside the shim function, not at `app.alerts.manager` module level. The local import was unnecessary and inconsistent with other top-level imports in `container.py`. Caught by quality reviewer as a Minor.

**Lesson**: Check whether circular import fear is real before adding a local import. Run `python -c "from app.alerts.manager import AlertManager"` first.

---

## Token Efficiency Findings

| What | Effect |
|------|--------|
| Providing exact "before/after" code blocks in plan | Reduced implementer hallucination, faster task completion |
| Spec reviewer first, quality reviewer second | Caught scope creep early (spec); prevented shipping correctness bugs (quality) |
| Subagent per task (not one per sprint) | Each agent had ~35K context budget; no context overload observed |
| Architecture review artifact before Sprint 1 | Identified all 4 DI issues in one read-pass; no discovery during implementation |
| `test_container()` shared pattern | Zero per-test infrastructure setup; fast collection and execution |
| Stale tests NOT fixed during refactor issues | Added debt that cost 3 extra subagent invocations in Sprint 1 |

**Biggest token waste**: Fixing stale test patch targets. If `test_symbol_config_migration.py` had been deleted at Issue 008 (when `database.py` was deleted), ~500K tokens of Sprint 1 context would have been avoided.

**Rule for future sprints**: When deleting a module, immediately delete or update all tests that import from it. Don't defer.

---

## Process Improvements

### P1 — Add to plan template: lifecycle for stateful resources

When a plan step creates a subscription, connection, or thread, require the plan to also specify teardown/cleanup. The check: "Does this object have a destructor or cleanup path? Where does it run?"

### P2 — Track "test patch target" debt explicitly

When a test patches an internal symbol (not a port/interface), flag it in `known-risks.md` as coupling debt. During refactor, fix these tests in the same commit as the code change, not in a later sprint.

### P3 — "Trace the data source" check in plan review

When a plan step rewrites a data-fetching method, require the plan to state: "Old source: X. New source: Y. Are these equivalent?" If the plan doesn't answer this, it's incomplete.

### P4 — Architecture review timing

The `/230-architecture-improvements` phase (post-execution) was the right time to catch Sprint 1 items. Keep this phase — it reliably catches issues that are architecturally correct but implementation-incomplete.

---

## Next Sprint Recommended Actions

In order of value:

1. **Wire `ILLMPort` into Container** (S2-01) — completes the port triad; makes LLM analysis testable
2. **Add `EventBus.unsubscribe()`** (S2-05) — prerequisite for analysis lifecycle events
3. **Replace top-5 direct `notify()` imports** (S2-02) — highest coupling density, easy wins
4. **Tests for EventBus + use cases** (S2-04) — fills the test gap left in this sprint
5. **`datetime.utcnow()` → `datetime.now(timezone.utc)` in `compat.py`** (Q1 cleanup) — eliminates 8 warnings/run

---

## Metrics

| Metric | Value |
|--------|-------|
| Issues completed | 10 + Sprint 1 (4 DI fixes) |
| Commits | 16 |
| Files changed | 200+ |
| Tests at sprint end | 934 passing |
| Pre-existing failures | 55 (scanner/reports legacy) |
| New regressions introduced | 0 |
| P0 bugs caught in review | 2 (OpenCodeAdapter construction, prev_close regression) |
| P1 bugs caught in review | 3 (RuntimeError catch, hardcoded path, handler leak) |
| Architecture health score | 7.7/10 |
