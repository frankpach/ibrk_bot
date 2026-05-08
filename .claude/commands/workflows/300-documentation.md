---
name: 300-documentation
description: Documentation phase - promote completed module knowledge into docs and project memory.
model: haiku
allowed-tools: Read Grep Glob Edit Write
argument-hint: <module-name>
---

# Phase 9: Documentation

Promote completed module knowledge from runtime artifacts into durable docs.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `.claude/current-dev-issues/.state/project-map.yaml`
5. `.claude/current-dev-issues/.state/decisions.md`
6. `.claude/current-dev-issues/.state/code-index.yaml`
7. Phase 0-8 artifacts for the module

Do not load active issue bodies unless documentation requires a missing detail.

## Required Outputs

Create or update:

- `docs/dev/artifacts/<module>/`
- `docs/04-modules/<module>/README.md`
- `docs/04-modules/<module>/ARCHITECTURE.md`
- `docs/04-modules/<module>/API.md` when API exists
- `docs/04-modules/<module>/COMPONENTS.md` when UI exists
- `docs/04-modules/<module>/EXTENDING.md`
- `docs/04-modules/<module>/DECISIONS.md`
- `docs/04-modules/<module>/BACKLOG.md`
- `docs/dev/project-memory.md`
- `.claude/project-memory/code-patterns.md`
- `.claude/project-memory/decisions-index.md`
- `.claude/project-memory/known-risks.md`
- `.claude/project-memory/module-map.md`

## Promotion Requirements

Capture:

- architecture decisions;
- reusable patterns;
- module contracts and events;
- known risks;
- lessons learned;
- extension guidance;
- deferred work from Phase 8.

## Gate

Do not mark Phase 9 complete if durable knowledge exists only in
`.claude/current-dev-issues/.state/`.

## Output

Return docs paths updated, project-memory entries updated, and any missing durable
documentation that blocks `/320-state-close`.
