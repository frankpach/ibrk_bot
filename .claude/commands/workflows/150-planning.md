---
name: 150-planning
description: Planning phase - write WBS issue files directly from the PRD and state.
model: sonnet
allowed-tools: Read Grep Glob Bash Write
argument-hint: <module-name>
---

# Phase 4: Planning

Convert the PRD into self-contained WBS issue files.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `.claude/current-dev-issues/.state/constraints.md`
5. `.claude/current-dev-issues/.state/module-registry.md`
6. `.claude/current-dev-issues/.state/code-index.yaml`
7. the module PRD and interface artifact

Use `/010-search-assess` or `code-search` only for gaps that the current
`code-index.yaml` does not cover.

## Future Development Capture

If planning creates deferred slices, rejected issue groups, later-phase modules, or
implementation variants, store the detailed backlog in
`.claude/dev-future/<module-or-system>/`. Only selected active WBS issues belong in
`.claude/current-dev-issues/`. Promote a summary to `docs/06-roadmap/` only when it
affects roadmap sequencing.

## Process

1. Run `/state-validator 150-planning`.
2. Confirm the PRD path and interface artifact path.
3. Create WBS issues in `.claude/current-dev-issues/`.
4. Each issue must include WHY, WHO, WHAT, HOW, Code Search, Reference Documents,
   Acceptance Criteria, and Definition of Done.
5. Prefer 3-8 vertical slices. Split larger work instead of creating XL issues.
6. Update:
   - `.claude/current-dev-issues/README.md`
   - `.claude/current-dev-issues/.state/project-map.yaml`
   - `.claude/current-dev-issues/.state/current-objective.md`
   - `.claude/current-dev-issues/.state/next-actions.md`

## Escalation

Stop if issues are horizontal, acceptance criteria are vague, dependencies are
unclear, or the PRD requires architecture changes.

## Output

- WBS issues in `.claude/current-dev-issues/`
- dependency graph in `.claude/current-dev-issues/README.md`
- runtime state updated for Phase 5
