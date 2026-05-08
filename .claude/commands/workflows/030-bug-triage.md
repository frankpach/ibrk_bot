---
name: 030-bug-triage
description: Lightweight bug workflow for reproduce, isolate, root-cause, minimal fix, and validation.
model: sonnet
allowed-tools: Read Grep Glob Bash Edit Write
argument-hint: <symptom-or-command>
---

# Bug Triage

Use this when the goal is to find and repair a defect.

## Context Budget

Load at most:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. failing test/log/command output
5. the smallest relevant source/test files

Use `.claude/project-memory/known-risks.md` only when the failure resembles a
known risk. Avoid full module artifacts unless the bug depends on design intent.

## Process

1. Reproduce or inspect the failure.
2. Identify the smallest failing behavior.
3. Search for nearby patterns and previous failures.
4. State root cause before editing.
5. Add or update the narrowest regression check that is practical.
6. Apply the minimal fix.
7. Run targeted validation first, then broader validation if the touched area is shared.
8. Record the failure in:
   - `.claude/current-dev-issues/.state/failed-attempts.md` for active issue work;
   - `.claude/project-memory/known-risks.md` if it is reusable project knowledge;
   - `docs/` if it affects developer-facing behavior.

## Escalation

Escalate to the full pipeline if the bug reveals missing requirements, architecture
change, cross-module contract drift, or unclear product behavior.

## Output

Return:

- reproduced symptom or evidence;
- root cause;
- fix summary;
- validation evidence;
- memory/docs updates.
