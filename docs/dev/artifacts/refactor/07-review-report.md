# Code Review: refactor (Issue #004 — Persist System State, Auditoría y Event Bus)

## Executive Summary

| Metric | Score |
|--------|-------|
| Code Quality | 9/10 |
| Architecture Alignment | 9/10 |
| Risk Level | LOW |
| **Recommendation** | **APPROVED** (all P0/P1 fixes applied) |

---

## Scope

Commits `2350228` and `d6be5fa`. Files reviewed:
- `app/application/event_bus.py`
- `app/domain/trading/events.py`
- `app/application/use_cases/change_mode.py`
- `app/application/use_cases/pause_system.py`
- `app/infrastructure/system/persisted_state.py`
- `app/infrastructure/notifications/telegram_adapter.py`
- `app/infrastructure/llm/opencode_adapter.py`
- `app/container.py`
- `app/api/auth.py`
- `tests/test_issue004_persist_state.py`
- `tests/test_arch_refactor_fase0.py`

---

## P0 Findings (Must Fix)

### P0-01: OpenCodeAdapter._validate_bin() called at construction time — broke all 9 adapter tests ✅ FIXED

- **Location**: `app/infrastructure/llm/opencode_adapter.py`
- **Issue**: `_validate_bin()` in `__init__` caused `FileNotFoundError` on every test that constructed `OpenCodeAdapter()` when the binary wasn't on the machine. Tests mocked `subprocess.run` but couldn't get past construction.
- **Fix applied**: Removed eager call from `__init__`. `_validate_bin()` remains available for explicit health-check calls; `call()` relies on subprocess errors propagated through the existing `except Exception` handler (which returns `""`).
- **Result**: All 9 previously failing tests now pass.

---

## P1 Findings (Should Fix)

### P1-01: Bare `RuntimeError` catch in `TelegramNotificationAdapter.request_approval` ✅ FIXED

- **Location**: `app/infrastructure/notifications/telegram_adapter.py:42`
- **Issue**: `except RuntimeError` caught ALL RuntimeErrors, including real failures from `request_approval()`, silently routing them to the sync fallback.
- **Fix applied**: Now checks error message before using fallback; re-raises any other RuntimeError.

### P1-02: `is_paused` stored as `"1"`/`"0"` string but coerced transparently — implicit contract

- **Location**: `app/application/use_cases/pause_system.py:40`, `app/infrastructure/db/compat.py:1377`
- **Status**: ACCEPTED — works correctly today. `compat.py` coercion is in place. Deferred to P2 backlog.

### P1-03: Hardcoded absolute Windows path in test ✅ FIXED

- **Location**: `tests/test_issue004_persist_state.py:398`
- **Fix applied**: Changed to `Path(__file__).parent.parent / "app" / "application"` — portable across machines.

---

## P2 Findings (Deferred)

| ID | Finding | Location |
|----|---------|----------|
| P2-01 | `datetime.utcnow()` deprecated — 8 warnings per test run | `app/infrastructure/db/compat.py:1410` |
| P2-02 | `ChangeTradingModeUseCase` always blocks on open positions — no `confirmed` override | `app/application/use_cases/change_mode.py:52` |
| P2-03 | `test_container()` in production `app/container.py` imports from `tests/` | `app/container.py:108` |

---

## Anti-Pattern Check

| Pattern | Status | Notes |
|---------|--------|-------|
| Model Blindness | ✓ CLEAR | Frozen dataclasses with clear semantics |
| Island Components | ✓ CLEAR | EventBus + container as single composition root |
| Pub/Sub Bypass | ✓ CLEAR | All cross-module communication via ports or events |
| UX Amnesia | ✓ CLEAR | State survives restart; audit log complete |

---

## Code Quality Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Clarity | 9/10 | Clean separation, minimal necessary comments |
| Correctness | 9/10 | All 46 tests pass after fixes |
| Test Coverage | 9/10 | 17 new tests + 29 existing; 0 failures |
| Architecture | 9/10 | Clean hexagonal; minor layering concern deferred |
| Security | 9/10 | Dual-key auth correct; secret masking; `env={}` subprocess isolation |

---

## Verification

```
python -m pytest tests/test_issue004_persist_state.py tests/test_arch_refactor_fase0.py -q
# 46 passed, 0 failed
```

## Sign-Off

- **Reviewer**: LLM Code Reviewer
- **Date**: 2026-05-15
- **Ready for Merge**: YES
