# Skills Inventory

`registry.yaml` is the source of truth for active and deprecated skills.

## Active Skills

- `grill-me`: discovery interview for full pipeline Phase 0.
- `discover-codebase`: archaeology and architecture mapping for Phase 1.
- `design-interface`: interface alternatives and user choice for Phase 2.
- `code-search`: targeted reuse search before implementation or planning.
- `context-promoter`: promote useful context into runtime, project memory, or docs.
- `module-preflight`: scaffold and dependency validation before execution.
- `phase-run`: execute one WBS issue with TDD.
- `generate-afk-prompt`: build a compact issue prompt for autonomous execution.
- `quality-gates`: run module quality checks.
- `code-review`: review correctness, architecture, and risks.
- `improve-codebase`: identify architecture improvements after review.
- `state-validator`: check runtime state consistency before phase changes.

## Deprecated Missing Skills

Some older docs described separate PRD-writing and issue-writing skills. Those
entries are now represented only in `registry.yaml` as deprecated records. Active
workflows write the PRD and WBS issue files directly.

## Token Rule

Read the skill file only when the current workflow requires it. Prefer
`SYSTEM_CONTRACT.md`, `registry.yaml`, and project-memory indexes before loading
large references.
