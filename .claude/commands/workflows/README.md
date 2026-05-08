# Workflows

`../registry.yaml` is the source of truth for workflow status and paths.

## Standalone Workflows (`000-099`)

- `000-system-health.md`: validate `.claude` health.
- `010-search-assess.md`: read-only code archaeology and impact assessment.
- `020-quick-task.md`: small scoped task.
- `025-frontend-corrections.md`: targeted FE corrections — forms, i18n, component reuse, layout.
- `026-cross-layer-fix.md`: small cross-layer corrections — existing endpoint field additions, schema sync.
- `030-bug-triage.md`: reproduce, isolate, and fix or plan a bug.
- `040-pytest-repair.md`: run backend pytest, group failures, fix by file, rerun targeted tests, then rerun all tests.
- `050-progress-report.md`: cross-cutting progress snapshot comparing docs, code, and git history to surface drift, blockers, and next actions.

Use these when full module discovery and planning would waste tokens.

## Full Module Pipeline

- `100-state-init.md`
- `110-discovery.md`
- `120-architecture.md`
- `130-design.md`
- `140-requirements.md`
- `150-planning.md`
- `200-execution.md`
- `210-quality.md`
- `220-review.md`
- `230-architecture-improvements.md`
- `300-documentation.md`
- `310-retrospective.md`
- `320-state-close.md`

Use the full pipeline for module-sized work, new features that need product
decisions, cross-layer changes, and architectural changes.

## Operations (`900-999`)

- `900-commit-push-github.md`
- `910-rotate-docker-tags.md`

## Deprecated Workflows

- `6-phase-x-execution.md`
- `8-quality-tests.md`

They are retained for reference only and must not be used as active contracts.

## Token Rule

Every workflow starts with the same loading order:

1. `SYSTEM_CONTRACT.md`
2. `registry.yaml`
3. current workflow
4. minimal relevant runtime/project memory
5. targeted docs and source files

## Closure Rule

Module work is not complete until durable knowledge is promoted to `docs/` and
compact reusable knowledge is promoted to `.claude/project-memory/`.
