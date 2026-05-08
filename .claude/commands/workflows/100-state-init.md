---
name: 100-state-init
description: Initialize structured state for a new module. Run before Phase 0. Creates .state/ in current-dev-issues/ and copies artifact templates.
model: haiku
allowed-tools: Read Write Glob Bash
argument-hint: <module-name>
---

# State Init — Prepare Module State

Run this **before Phase 0** when starting work on a new module.

## Input

```
/100-state-init <module-name>
```

Example: `/100-state-init material-requests`

## Prerequisites

- `current-dev-issues/` must be empty (or cleared from previous module)
- `current-dev-temp/` must be empty (or cleared from previous module)
- Module name confirmed with user

## Future Development Capture

If startup reveals ideas that are not part of the active module, store detailed
notes in `.claude/dev-future/<module-or-system>/`. Keep a compact folder README
for summaries. Promote only stable roadmap summaries to `docs/06-roadmap/`.

## Process

### Step 1 — Verify Clean State

Check that `.claude/current-dev-issues/` contains no `.md` files (other than README).
Check that `.claude/current-dev-issues/.state/` does not exist.

If files exist: **STOP** — ask user to run `/320-state-close` first or confirm clearing.

### Step 2 — Create .state/ Directory and Files

Create `.claude/current-dev-issues/.state/` with these files:

**project-map.yaml** (initialize with module name, all phases pending):
```yaml
version: "1.0"
module: <module-name>
updated_at: <ISO8601_NOW>

objectives:
  current: <module-name>
  status: phase_0_pending
  phases:
    phase_0: {status: pending, completed_at: null, artifacts: []}
    phase_1: {status: pending, completed_at: null, artifacts: []}
    phase_2: {status: pending, completed_at: null, artifacts: []}
    phase_3: {status: pending, completed_at: null, artifacts: []}
    phase_4: {status: pending, completed_at: null, artifacts: []}
    phase_5: {status: pending, completed_at: null, issues_completed: 0, issues_total: 0}
    phase_6: {status: pending, completed_at: null, artifact: null}
    phase_7: {status: pending, completed_at: null, artifact: null}
    phase_8: {status: pending, completed_at: null, artifact: null}

personas: []
constraints: {timeline: null, technical: [], business: []}
decisions: []
open_questions: []
assumptions: []
issues: []
actions: []
code_index: {models: [], components: [], events: [], services: []}
failed_attempts_summary: []
next_action: {phase: 0, goal: "Run Phase 0 discovery", deadline: null, blockers: []}
```

**current-objective.md**:
```markdown
# Current Objective

**Phase**: Phase 0 — Discovery
**Module**: <module-name>
**Started**: <YYYY-MM-DD>

## Goal
Run /110-discovery to reach shared understanding of what we are building.

## Next Action
Invoke /grill-me and answer questions about the module.

## Blockers
None
```

**constraints.md**:
```markdown
# Constraints: <module-name>

**Module**: <module-name>
**Last Updated**: <YYYY-MM-DD>

## Global Rules

See CLAUDE.backend.md and CLAUDE.frontend.md for the complete global ruleset.

Summary:
- StandardResponse / StandardListResponse on all API responses
- tenant_id filter on all queries — no bypass
- APIException only — never HTTPException
- No direct imports between business modules
- apiClient only — no direct fetch/axios
- useTranslation() only — no hardcoded text

## Module-Specific Constraints

[To be filled during Phase 1 — /discover-codebase]

## Module Dependencies

[To be filled during Phase 1 — /discover-codebase]
```

**module-registry.md**:
```markdown
# Module Registry: <module-name>

**Module**: <module-name>
**Last Updated**: <YYYY-MM-DD>

## This Module

**Name**: <module-name>
**Path**: backend/app/modules/<module-name>/
**Status**: in_development

## Related Modules

[To be filled during Phase 1 — read from backend/config/modules.json]

| Module | Enabled | depends_on | produces_for | Relationship to this module |
|--------|---------|------------|--------------|----------------------------|
| | | | | |
```

**decisions.md**:
```markdown
# Decisions Log: <module-name>

**Module**: <module-name>
**Last Updated**: <YYYY-MM-DD>

[Decisions will be appended here during discovery and architecture phases]
```

**code-index.yaml**:
```yaml
# Code Index: <module-name>
module: <module-name>
updated_at: <ISO8601_NOW>

# Populated during Phase 1 (discover-codebase)
models: []
components: []
events: []
services: []
utilities: []
```

**failed-attempts.md**:
```markdown
# Failed Attempts Registry: <module-name>

**Module**: <module-name>
**Last Updated**: <YYYY-MM-DD>

[Failures will be logged here during execution]

## Loop Detection Log

| Attempt # | Action | Timestamp | Similar To | Blocked? | Alternative Taken |
|-----------|--------|-----------|------------|----------|-------------------|
```

**next-actions.md**:
```markdown
# Next Actions: <module-name>

**Module**: <module-name>
**Last Updated**: <YYYY-MM-DD>

## Current Focus

**Phase**: Phase 0 — Discovery
**Goal**: Reach shared understanding of what we are building

## Next Action (Do This Now)

1. Run `/110-discovery <module-name>`

## Backlog

- [ ] Phase 1 — Architecture (after Phase 0 complete)
- [ ] Phase 2 — Design (after Phase 1 complete)
- [ ] Phase 3 — Requirements (after Phase 2 complete)
- [ ] Phase 4 — Planning (after Phase 3 complete)
- [ ] Phase 5 — Execution (after Phase 4 complete)
```

**test-status.md**:
```markdown
# Test Status: <module-name>

**Module**: <module-name>
**Last Updated**: <YYYY-MM-DD>

## Latest Run

No tests run yet. Module in planning phase.

## Status

Unit: not run
Integration: not run
E2E: not run
TypeScript/Mypy: not run
Linting: not run
```

### Step 3 — Create README in current-dev-issues/

Create `.claude/current-dev-issues/README.md`:
```markdown
# <Module Name> — Development Issues

**Module**: <module-name>
**Started**: <YYYY-MM-DD>
**Status**: planning

## Issue List

[To be populated in Phase 4 — /150-planning]

## Dependency Graph

[To be populated in Phase 4]

## Parallelizable Groups

[To be populated in Phase 4]
```

### Step 4 — Create done/ directory

Create `.claude/current-dev-issues/done/.gitkeep`

### Step 5 — Output

```
STATE INIT: COMPLETE
Module: <module-name>
State files created: 8
Next step: /110-discovery <module-name>
```

## Rules

- Never run if `.state/` already exists with data — must explicitly clear first
- All 8 state files are mandatory — do not skip any
- Timestamps must be real ISO8601 — not placeholders
