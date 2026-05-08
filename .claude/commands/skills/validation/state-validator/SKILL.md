---
name: state-validator
description: Consistency gate — verify state before any phase starts. Detects stale state, missing prerequisites, open blockers.
model: haiku
allowed-tools: Read Grep
argument-hint: [phase-name]
---

# State Validator — Consistency Gate

Run this before starting any phase. It reads `.state/` and reports PASS or FAIL with specific blockers.

## When to Run

- Before Phase 1 (architecture): verify Phase 0 artifacts exist
- Before Phase 5 (execution): verify Phases 0-4 complete, no open blockers
- Before any retry: verify previous failure is documented in `failed-attempts.md`
- Manually: `/state-validator [phase-name]`

## Input

Argument: phase name to validate prerequisites for.
Example: `/state-validator 200-execution`

## Process

### Step 1 — Read State

Read these files (in order, stop if missing):

1. `.claude/current-dev-issues/.state/project-map.yaml`
2. `.claude/current-dev-issues/.state/current-objective.md`
3. `.claude/current-dev-issues/.state/constraints.md`

If any file is missing: **FAIL** — run `/100-state-init [module-name]` first.

### Step 2 — Check Prerequisites

For the requested phase, verify all prior phases are marked `complete` in `project-map.yaml`:

| Requesting phase | Required prior phases |
|---|---|
| 120-architecture | phase_0: complete |
| 130-design | phase_0, phase_1: complete |
| 140-requirements | phase_0, phase_1, phase_2: complete |
| 150-planning | phase_0, phase_1, phase_2, phase_3: complete |
| 200-execution | phase_0 through phase_4: complete |
| 210-quality | phase_5 issues_completed == issues_total |
| 220-review | phase_6: complete |
| 230-architecture-improvements | phase_7: complete |

If prerequisite not met: **FAIL** — list which phases are incomplete.

### Step 3 — Check Open Blockers

Read `project-map.yaml` → `open_questions`.

If any question is marked `blocking: true`: **FAIL** — list the blocking questions.

### Step 4 — Check Failed Attempts (anti-loop)

Read `.claude/current-dev-issues/.state/failed-attempts.md`.

If the requested phase appears with `resolved: false`: **FAIL** — show the unresolved failure and its root cause.

### Step 5 — Check Objective Alignment

Read `current-objective.md`.

If `phase` does not match the requested phase: **WARN** — objective is set to a different phase. Confirm before proceeding.

### Step 6 — Output

**If PASS**:
```
STATE VALIDATOR: PASS
Phase: [phase-name]
Prerequisites: all complete
Blockers: none
Failed attempts: none unresolved
Ready to proceed.
```

**If FAIL**:
```
STATE VALIDATOR: FAIL
Phase: [phase-name]
Blockers:
  - [Specific blocker 1]
  - [Specific blocker 2]
Action required: [what to do before retrying]
```

## Rules

- Never skip this check before Phase 5 (execution)
- FAIL is a hard stop — do NOT proceed until blockers are resolved
- WARN is advisory — user can override with explicit confirmation
- Update `project-map.yaml.issues` when a new blocker is discovered

## Time Budget

~2 minutes per check