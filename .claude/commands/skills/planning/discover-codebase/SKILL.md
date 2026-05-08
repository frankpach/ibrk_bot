---
name: discover-codebase
description: Phase 1 archaeology skill - map existing models, services, events, components, and gaps.
model: haiku
allowed-tools: Read Grep Glob Bash Write
argument-hint: <module-name>
---

# Discover Codebase

Use this skill during Phase 1 of the full pipeline.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. `.claude/current-dev-issues/.state/project-map.yaml`
4. `.claude/current-dev-issues/.state/current-objective.md`
5. Phase 0 artifacts
6. targeted docs from `docs/`
7. targeted source files found by search

Do not load full source or docs trees.

## Process

1. Confirm Phase 0 is complete.
2. Read the design concept and persona journey.
3. Search for related models, services, events, components, and tests.
4. Identify gaps and reusable patterns.
5. Detect model blindness, island components, pub/sub bypass, and UX amnesia.
6. Write:
   - `docs/dev/artifacts/<module>/03-architecture-map.md`
   - `docs/dev/artifacts/<module>/04-constraints.md`
   - `docs/dev/artifacts/<module>/05-why-decisions.md`
7. Update:
   - `.claude/current-dev-issues/.state/code-index.yaml`
   - `.claude/current-dev-issues/.state/constraints.md`
   - `.claude/current-dev-issues/.state/module-registry.md`
   - `.claude/current-dev-issues/.state/decisions.md`
   - `.claude/project-memory/code-patterns.md` for reusable discoveries

## Output

- architecture artifacts;
- compact state updates;
- reusable project-memory entries when appropriate.
