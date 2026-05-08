# Claude System Contract

Read this file before using `.claude` workflows or skills.

## Goal

Minimize token use while preserving enough context for reliable development. Use
compact indexes first, load source files only when needed, and promote durable
knowledge into `docs/`.

## Canonical Paths

- Commands: `.claude/commands/`
- Workflows: `.claude/commands/workflows/`
- Skills: `.claude/commands/skills/`
- Registry: `.claude/commands/registry.yaml`
- Runtime state: `.claude/current-dev-issues/.state/`
- Automation state: `.claude/scripts/.state/`
- Project memory: `.claude/project-memory/`
- Temporary active docs: `.claude/current-dev-temp/`
- Future development backlog: `.claude/dev-future/<module-or-system>/`
- Archived agent material: `.claude/archive/`
- Durable artifacts: `docs/dev/artifacts/`
- Module docs: `docs/04-modules/`
- Roadmap docs: `docs/06-roadmap/`
- Project memory docs: `docs/dev/project-memory.md`

## Workflow Selection

Use standalone workflows (`000-099`) for narrow work:

- `/000-system-health`: validate `.claude` consistency.
- `/010-search-assess`: search, reuse analysis, impact assessment.
- `/020-quick-task`: small scoped change or documentation cleanup.
- `/030-bug-triage`: reproduce, isolate, and fix or plan a defect.
- `/040-pytest-repair`: run pytest, group failures, fix by file, rerun targeted tests, then rerun all tests.

Use the full pipeline when work is module-sized, cross-layer, architectural, or
requires product discovery:

`/100-state-init` through `/320-state-close`, with `100-199` for definition,
`200-299` for delivery and validation, and `300-399` for closure and memory.

Use operations workflows (`900-999`) only after validation passes.

## Memory Layers

Runtime memory stores active work and can be cleared after extraction:

- `project-map.yaml`
- `current-objective.md`
- `next-actions.md`
- `decisions.md`
- `constraints.md`
- `module-registry.md`
- `code-index.yaml`
- `failed-attempts.md`
- `test-status.md`

Project memory stores compact reusable knowledge:

- `code-patterns.md`
- `decisions-index.md`
- `known-risks.md`
- `module-map.md`

Docs store durable human-facing knowledge. Anything important enough to survive
module closure must be promoted to `docs/`.

## Token Budget Rules

- Read this file and `registry.yaml` before large work.
- Read one workflow file at a time.
- Read only the state files named by the workflow.
- Prefer project-memory indexes over full docs trees.
- Do not load archives, future plans, temp files, logs, or screenshots unless they are
  directly relevant.
- Stop and ask if the required context would exceed the current workflow budget.

## Future Development Rule

During workflows `/100-state-init` through `/150-planning`, detailed future
development ideas, deferred slices, non-current module variants, and exploratory
execution notes belong in `.claude/dev-future/<module-or-system>/`.

Use `_platform` for cross-cutting architecture and infrastructure. Use `_intake`
for raw input that has not been triaged into a module yet. Each module/system folder
keeps a compact `README.md` so agents can load the summary before detailed files.

Promote only stable, human-facing summaries to `docs/06-roadmap/` or
`docs/dev/project-memory.md`.

## Promotion Rule

Before closing module work, promote durable knowledge from runtime state to:

- `docs/dev/artifacts/<module>/`
- `docs/04-modules/<module>/`
- `docs/dev/project-memory.md`
- `.claude/project-memory/`

Do not clear runtime state until promotion is complete.
