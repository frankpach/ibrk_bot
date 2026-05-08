---
name: design-interface
description: Phase 2 design skill - propose interface alternatives and document the selected direction.
model: sonnet
allowed-tools: Read Grep Glob Write
argument-hint: <module-name>
---

# Design Interface

Use this skill during Phase 2 of the full pipeline.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. Phase 0 design concept
4. Phase 1 architecture map and constraints

Do not read source code unless the architecture map is missing a required fact.

## Process

1. Propose three structurally different interface alternatives:
   - depth-first;
   - user-first;
   - reusability-first.
2. Compare trade-offs clearly.
3. Recommend one alternative with rationale.
4. Ask the user to choose or approve a hybrid.
5. Check for model blindness, island components, pub/sub bypass, and UX amnesia.
6. Save the selected design to `docs/dev/artifacts/<module>/06-interface-design.md`.
7. Update runtime state for Phase 3.

## Output

- selected interface design artifact;
- state update;
- open questions, if any.
