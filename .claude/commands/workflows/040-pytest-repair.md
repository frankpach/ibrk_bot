---
name: 040-pytest-repair
description: Standalone backend pytest repair loop: group failures, fix by file, rerun targeted tests, then rerun the full suite.
model: sonnet
allowed-tools: Read Grep Glob Bash Edit Write
argument-hint: [optional-test-path-or-filter]
---

# Pytest Repair

Use this standalone workflow when the backend test suite has failures, errors,
or warnings and the task is to converge the suite back to green.

## Context Budget

Read only:

1. `SYSTEM_CONTRACT.md`
2. `registry.yaml`
3. this workflow
4. failing test files and directly related source files
5. `.claude/current-dev-issues/.state/failed-attempts.md` only if the same
   failure repeats

Do not load the full lifecycle pipeline, full docs tree, frontend files, archives,
or unrelated modules unless the failure points there.

## Scope

Default working directory is `backend/`.

Default command:

```powershell
cd backend
uv run pytest
```

If the user provides a path, marker, or keyword filter, start with the narrowest
valid pytest command. Example:

```powershell
cd backend
uv run pytest tests/path/to/test_file.py
```

## Process

### Step 1: Run Pytest Once

Run the selected pytest command and capture the output. Do not start editing until
the output is grouped.

### Step 2: Group Findings

Create a compact failure map:

```text
By error:
- <exception or assertion family>
  - <test file>::<test name>
  - suspected source: <file>

By file:
- <test file>
  - failures: <count>
  - errors: <count>
  - warnings: <count>
  - first root-cause hypothesis: <one sentence>
```

Treat warnings as work items when they indicate deprecated APIs, resource leaks,
unawaited coroutines, transaction leakage, fixture misuse, or future-breaking
behavior. Do not chase cosmetic warnings unless the suite policy treats warnings
as failures.

### Step 3: Fix One File Cluster At A Time

For each failing file cluster:

1. Inspect the failing test file.
2. Inspect only the source files needed to explain the failure.
3. Identify whether the test, fixture, or implementation is wrong.
4. Apply the smallest correct fix.
5. Run the targeted file:

```powershell
cd backend
uv run pytest <file-with-problems>
```

If the file still fails, repeat the file-level loop. If a second attempt fails for
the same reason, record the failed approach in
`.claude/current-dev-issues/.state/failed-attempts.md` when runtime state exists.

### Step 4: Run Full Suite

After all known file clusters pass, run:

```powershell
cd backend
uv run pytest
```

If the full suite reveals new failures, regroup by error and by file, then restart
from Step 2. Stop after three full-suite cycles unless the remaining failure is
clearly understood and locally bounded.

## Stop And Ask

Stop before editing if:

- the failure requires a product decision or changed acceptance criteria;
- the fix touches authentication, RBAC, tenant filtering, migrations, module
  registry, or cross-layer frontend code;
- tests require external services that are not available;
- the same root cause survives two different repair strategies;
- the required context would exceed this standalone workflow budget.

## Output

Return a compact repair report:

```text
Initial command: uv run pytest ...
Grouped by error: <summary>
Grouped by file: <summary>
Files changed: <paths>
Targeted reruns: <commands and PASS/FAIL>
Full-suite reruns: <commands and PASS/FAIL>
Remaining risks: <none or list>
```
