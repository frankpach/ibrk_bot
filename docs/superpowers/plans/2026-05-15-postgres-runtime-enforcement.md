# PostgreSQL Runtime Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PostgreSQL mandatory in runtime while keeping SQLite available only for tests and temporary compatibility paths.

**Architecture:** Centralize runtime DB resolution in the SQLAlchemy engine layer, then route the legacy compat API through that shared backend instead of direct `sqlite3` connections. Keep SQLite support only when tests explicitly pass SQLite URLs or run in-memory/file-backed fixtures.

**Tech Stack:** Python, SQLAlchemy, psycopg2, FastAPI, pytest

---

### Task 1: Harden database URL resolution

**Files:**
- Modify: `app/infrastructure/db/engine.py`
- Modify: `app/config/settings.py`
- Test: `tests/test_issue009_postgresql.py`

- [ ] **Step 1: Write the failing test**

Add a test asserting runtime resolution prefers `DATABASE_URL` and that explicit SQLite remains allowed only when passed directly in tests.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_issue009_postgresql.py -k database_url -q`

- [ ] **Step 3: Write minimal implementation**

Keep `get_database_url()` environment-first, add a helper that can enforce runtime PostgreSQL, and keep explicit SQLite URLs valid for tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_issue009_postgresql.py -k database_url -q`

- [ ] **Step 5: Commit**

`git add app/infrastructure/db/engine.py app/config/settings.py tests/test_issue009_postgresql.py`

### Task 2: Route compat DB access through SQLAlchemy backend

**Files:**
- Modify: `app/infrastructure/db/compat.py`
- Modify: `app/infrastructure/db/session.py`
- Test: `tests/test_issue009_postgresql.py`

- [ ] **Step 1: Write the failing test**

Add a test asserting compat connections use SQLite only for explicit SQLite URLs and do not ignore `DATABASE_URL`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_issue009_postgresql.py -k compat -q`

- [ ] **Step 3: Write minimal implementation**

Replace direct `sqlite3.connect(DB_PATH)` runtime behavior with SQLAlchemy-backed connections obtained from the shared engine, while preserving SQLite behavior in test URLs.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_issue009_postgresql.py -k compat -q`

- [ ] **Step 5: Commit**

`git add app/infrastructure/db/compat.py app/infrastructure/db/session.py tests/test_issue009_postgresql.py`

### Task 3: Verify runtime behavior against deployed Pi

**Files:**
- Modify: `app/infrastructure/db/engine.py`
- Modify: `app/infrastructure/db/compat.py`
- Test: `tests/test_issue009_postgresql.py`

- [ ] **Step 1: Write the failing test**

Add a test for runtime enforcement that rejects startup assumptions when `DATABASE_URL` is absent under PostgreSQL-required mode.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_issue009_postgresql.py -k runtime -q`

- [ ] **Step 3: Write minimal implementation**

Add a runtime enforcement switch/helper and verify the deployed service resolves PostgreSQL on `aiutox-pi`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_issue009_postgresql.py -q`

- [ ] **Step 5: Commit**

`git add docs/superpowers/plans/2026-05-15-postgres-runtime-enforcement.md app/infrastructure/db/engine.py app/infrastructure/db/compat.py tests/test_issue009_postgresql.py`
