---
description: Run quality tests (unit + integration/e2e) for AiutoX ERP backend + frontend
auto_execution_mode: 2
---

Run quality tests for AiutoX ERP and produce a concise failure report.

## Scope

- Run tests only. Do NOT implement fixes unless explicitly requested.
- If a test fails, diagnose the root cause briefly and propose minimal fix plan (no code).
- Covers both backend and frontend in single execution.

## Pre-Run Gates

1) Read and comply with `.windsurf/rules/` and `@docs` (relevant sections).
2) Verify current code state:
   - correct branch
   - git status (report if dirty)
3) Ensure environment ready:
   - Backend: deps installed, DB/redis if integration requires
   - Frontend: npm/pnpm deps installed, backend running if e2e requires

## Execution Order

### Phase 1: Backend Tests

#### 1.1 Lint & Format
Run
´´´powershell
cd backend
uv run ruff check
uv run black --check
´´´
Then correct any formatting issues found and re-run the checks until they pass.

#### 1.2 Type checks
Run
´´´powershell
uv run mypy .
´´´
Then correct any type errors found and re-run the checks until they pass.

#### 1.3 Security checks
Run
´´´powershell
uv run bandit -r 
´´´
Then correct any security issues found and re-run the checks until they pass.

Run
´´´powershell
uv run pip-audit .
´´´
Then correct any security issues found and re-run the checks until they pass.

Run
´´´powershell
uv run radon mi app -s
´´´
Show any maintainability issues found and re-run the checks until they pass.

Run
´´´powershell
echo "=== Vulture 80%+ probable dead code ==="
uv run vulture app tests --min-confidence 80
´´´
Show any dead code issues found and re-run the checks until they pass.

#### 1.4 Unit tests (parallel)
Run
´´´powershell
uv run pytest -q -n 12 tests/unit
´´´
Then correct any unit test failures and re-run the tests until they pass.

#### 1.5 Integration tests (if unit passes)
Run
´´´powershell
uv run pytest -q -n 12 --maxfail=12 tests/integration
´´´
Then correct any integration test failures and re-run the tests until they pass.

### Phase 2: Frontend Tests

#### Lint
Run
```powershell
cd frontend
npm run lint
´´´
Then correct any linting issues found and re-run the checks until they pass.

#### Type check

```powershell
cd frontend
npm run typecheck
´´´
Then correct any type errors found and re-run the checks until they pass.


#### Security audit
Run
´´´powershell
npm audit --audit-level=high
´´´
Then correct any security issues found and re-run the checks until they pass.

#### Unit tests
```powershell
cd frontend
npm test -- --watchAll=false --passWithNoTests
´´´
Then correct any unit test failures and re-run the tests until they pass.

#### E2E tests (if unit passes, requires backend running)
Run
´´´powershell
npx playwright test --project=chromium --headless --reporter=line --workers=50%
´´´
Then correct any e2e test failures and re-run the tests until they pass.

## Output (Strict)

Return only:

### 1) Summary

| Layer | Status | Passed | Failed |
|-------|--------|--------|--------|
| Backend Unit | PASS/FAIL | N | N |
| Backend Integration | PASS/FAIL | N | N |
| Frontend Unit | PASS/FAIL | N | N |
| Frontend E2E | PASS/FAIL | N | N |

### 2) Failures (group by layer/file)

For each failing layer:

- **Layer**: `<backend-unit/backend-integration/frontend-unit/frontend-e2e>`
- **File**: `<path>`
- **Failing tests**: `<test names>`
- **Error type**: `<assertion/import/db/render/network/timeout/etc>`
- **Most likely root cause**: 1–2 lines

### 3) Minimal Fix Plan (no code)

- P0 actions (max 6 bullets total)
- Dependencies / Preconditions (if any)
- Validation command(s) to confirm the fix

### 4) Stop/Go

- Ready for fixes: Yes/No
- Blocking items (if any)

## Notes

- Run unit tests first for both layers
- If unit fails, skip integration/e2e for that layer
- Do not rerun full suite repeatedly; rerun only failing tests if re-check needed
- Use official commands: `aiutox test backend`, `aiutox test frontend`, `aiutox test`
