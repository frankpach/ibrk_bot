---
name: 140-requirements
description: Requirements phase - write the PRD directly from prior artifacts.
model: sonnet
allowed-tools: Read Grep Glob Bash Write
argument-hint: <module-name>
---

# Phase 3: Requirements

Write a PRD from the approved design and architecture artifacts.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `.claude/current-dev-issues/.state/current-objective.md`
5. `.claude/current-dev-issues/.state/constraints.md`
6. Phase 0-2 artifacts for the module

Do not read issue files or source code unless a requirement cannot be resolved from
the artifacts.

## Future Development Capture

If PRD writing identifies non-current requirements, optional capabilities, or future
release behavior, write the detailed notes to
`.claude/dev-future/<module-or-system>/`. Keep the PRD limited to the active scope
and promote only stable roadmap summaries to `docs/06-roadmap/`.

## Inputs

- `docs/dev/artifacts/<module>/01-design-concept.md`
- `docs/dev/artifacts/<module>/02-persona-journey.md`
- `docs/dev/artifacts/<module>/03-architecture-map.md`
- `docs/dev/artifacts/<module>/06-interface-design.md` or the active interface artifact

## Process

1. Confirm Phase 0-2 are complete in runtime state.
2. Read the minimum artifacts listed above.
3. Write `docs/dev/artifacts/<module>/08-prd.md`.
4. Include acceptance criteria, edge cases, event/API needs, security constraints,
   performance expectations, and open questions.
5. Update runtime state:
   - `project-map.yaml`: mark Phase 3 complete.
   - `current-objective.md`: move to Phase 4.
   - `next-actions.md`: next action is `/150-planning <module>`.

## Escalation

Stop and ask if the approved interface, acceptance criteria, or product behavior is
ambiguous. Escalate back to Phase 2 if the design is not decision complete.

## Output

- PRD: `docs/dev/artifacts/<module>/08-prd.md`
- updated runtime state
