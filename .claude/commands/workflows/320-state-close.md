---
name: 320-state-close
description: Close a module only after promoting runtime memory into project memory and docs.
model: sonnet
allowed-tools: Read Write Glob Bash
argument-hint: <module-name>
---

# State Close

Close completed module work and clear runtime state only after durable promotion.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `.claude/current-dev-issues/.state/project-map.yaml`
5. `.claude/current-dev-issues/.state/decisions.md`
6. `.claude/current-dev-issues/.state/code-index.yaml`
7. `.claude/current-dev-issues/.state/failed-attempts.md`
8. relevant `docs/dev/artifacts/<module>/` files
9. relevant `docs/04-modules/<module>/` files

## Required Gates

- All issues complete or explicitly deferred.
- Phase 6 quality result captured.
- Phase 7 review result captured.
- Phase 9 documentation completed.
- HITL issues reviewed.
- Durable knowledge promoted to `docs/`.
- Reusable compact knowledge promoted to `.claude/project-memory/`.

## Promotion Checklist

Before clearing runtime state, verify:

- decisions are in `docs/04-modules/<module>/DECISIONS.md`;
- reusable patterns are in `.claude/project-memory/code-patterns.md`;
- project-level decisions are indexed in `.claude/project-memory/decisions-index.md`;
- known risks are in `.claude/project-memory/known-risks.md`;
- module map entry is in `.claude/project-memory/module-map.md`;
- human-facing summary is linked from `docs/dev/project-memory.md`.

## Clear Rule

Never clear `.claude/current-dev-issues/` or `.claude/current-dev-temp/` until the
promotion checklist passes and the user confirms cleanup.

## Output

Return:

- promoted docs paths;
- promoted project-memory paths;
- HITL confirmation status;
- cleanup confirmation status;
- next module startup instruction.
