# Next Actions

**Module**: refactor — CLOSED 2026-05-15

No pending actions for this module. All issues complete, state closed.

## Next Sprint Options (from BACKLOG.md)

Priority order:

1. Wire `ILLMPort` into Container (`docs/04-modules/refactor/BACKLOG.md` → S2-01)
2. Add `EventBus.unsubscribe()` (S2-05)
3. Replace top-5 direct `notify()` imports (S2-02)
4. Tests for EventBus + use cases (S2-04)
5. `datetime.utcnow()` → `datetime.now(timezone.utc)` in compat.py (Q1)

## To Start Next Module

```
/clear
/workflows:100-state-init <module-name>
```
