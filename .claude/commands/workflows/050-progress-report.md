---
name: 050-progress-report
description: Cross-cutting progress snapshot that compares documented plans against actual code and git history to surface drift, blockers, and recommended next actions.
model: sonnet
allowed-tools: Read Grep Glob Bash
argument-hint: [--plan <A|B|C|D>] [--module <name>]
---

# Progress Report — Cross-Cutting Project Status

## Purpose

Answer "where are we right now?" by cross-referencing what docs say is done/planned,
what the runtime state says is active, what the code actually contains, and what git
history shows recently happened.

**Output**: A structured progress report with phase status, roadmap plan status, active
development state, any doc/code drift found, blockers, and recommended next actions.

## Arguments

- No args — full project view (all plans, all phases)
- `--plan A|B|C|D` — focus report on a specific roadmap plan
- `--module <name>` — include deeper code spot-checks for that module

## Context Budget (load in this order, no more)

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. This workflow
4. `docs/05-status/progress.md`
5. `docs/05-status/pending.md`
6. `docs/06-roadmap/README.md`
7. `.claude/current-dev-issues/.state/project-map.yaml` (if exists)
8. `.claude/current-dev-issues/.state/next-actions.md` (if exists)
9. `git log --oneline -20` (Bash)
10. If `--plan` arg: load the referenced roadmap plan doc
11. If `--module` arg: load `docs/04-modules/<name>/README.md`

Do not load: full issue bodies, all module docs, test output, operational runbooks.

## Process

### Step 1 — Read Documentation State

Read `docs/05-status/progress.md` and `docs/05-status/pending.md`. Extract:
- Which phases are marked complete
- What is marked in-progress with its stated goal
- What is blocked, pending, or explicitly deferred

### Step 2 — Read Roadmap Plans

Read `docs/06-roadmap/README.md`. Identify:
- Status of Plans A/B/C/D (in-progress / planned / blocked)
- Timeline markers and their stated goals
- Any plan dependencies (B requires A to finish, etc.)

### Step 3 — Read Runtime State

If `.state/project-map.yaml` exists, read it. Extract:
- Current module under development and its phase
- Open questions, blockers, and pending decisions
- Number of issues done vs total

If `.state/` does not exist, note it and continue with docs and git only.

### Step 4 — Check Git History

Run `git log --oneline -20`. Identify:
- What was committed in the last ~2 weeks
- Whether commits align with what docs say is in-progress
- Any phases or modules whose completion appears in commits but not in docs

### Step 5 — Spot-Verify Code Claims

For the 3-5 modules/features most recently marked as "complete" in progress.md,
run targeted existence checks using Glob and Grep only (do not read full files):

- `Glob backend/app/modules/<name>/` — does the backend module directory exist?
- `Glob frontend/src/features/<name>/` — does the frontend feature directory exist?
- `Grep "APIRouter|router" backend/app/modules/<name>/routes.py` — is it wired?

If `--module <name>` is provided, run spot-checks for that module regardless of
completion status.

### Step 6 — Cross-Reference and Identify Drift

Compare what docs claim vs what code and git confirm. Flag any of the following:
- Docs say complete but the code directory is missing
- Docs say planned but code already exists
- Git commits mention a module not reflected in progress.md
- Runtime `.state/` shows active work on something docs mark as pending or blocked

### Step 7 — Produce Report

```
## Project Progress Report — YYYY-MM-DD

### Phase Status
| Phase | Status      | Notes                        |
|-------|-------------|------------------------------|
| 0     | Complete    |                              |
| 1     | Complete    |                              |
| 5     | In Progress | Plan A + Data Collection M6  |

### Roadmap Plans
| Plan | Status      | Key Remaining Items          |
|------|-------------|------------------------------|
| A    | In Progress | <items>                      |
| B    | Planned     | Awaiting Plan A completion   |
| C    | Planned     | —                            |
| D    | Planned     | —                            |

### Active Development
- Module: <name>
- Current phase: <N>
- Slices done: X / Y
- Current issue: <issue-filename>

### Documentation vs Code Drift
[List each divergence as: "docs/<file> says X — code/git shows Y"]
[Write "None detected" if clean.]

### Blockers
[List anything explicitly blocking progress with its source (docs/state/git).]
[Write "None identified" if clear.]

### Recommended Next Actions
1. <concrete action — link to workflow or skill if applicable>
2. <concrete action>
3. <concrete action>
```

## Rules

- Read-only — never write, never edit docs, never stage changes.
- Do not re-run tests or type-checkers — this is a snapshot, not a quality gate.
- Spot-check with Glob/Grep only — do not read full source files.
- If `.state/` is missing, note it explicitly and continue from docs and git.
- Report divergences as facts: state what the source says vs what was observed.
- Scope the report to `--plan` or `--module` when those args are provided.

## Time Budget

- Min: 2 minutes (clean state, docs and git agree)
- Typical: 5-8 minutes (active module + roadmap cross-check)
- Max: 15 minutes (deep investigation with `--module`)

## When to Use

- Before starting a new sprint or roadmap plan, to confirm current baseline
- When rejoining a project after a break, to rebuild shared context fast
- When preparing a status update for a stakeholder or code review
- When something feels "off" between what was discussed and what is in the code

## Next Workflows

After this report, the natural next step depends on what the report reveals:

- If drift found → `/010-search-assess <domain>` to investigate
- If blockers found → `/030-bug-triage` or raise with user
- If docs are stale → `/300-documentation <module>` to update
- If ready for next plan → `/100-state-init <module>` to begin
