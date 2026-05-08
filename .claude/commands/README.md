# Claude Development System

Start here for the local `.claude` development system.

The authoritative contract is `SYSTEM_CONTRACT.md`. The machine-readable inventory is
`registry.yaml`. If this README disagrees with either file, treat this README as stale.

## Purpose

This system keeps agent sessions useful with a compact context:

- use short workflows for small tasks, bug triage, and code search;
- use the full lifecycle pipeline for module-sized work;
- keep active work in runtime memory;
- promote durable lessons to project memory and `docs/`;
- validate the system for drift before relying on it.

## First Read Order

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. The workflow you are about to run
4. Only the state, docs, and source files required by that workflow

## Workflow Groups

Standalone workflows (`000-099`):

- `/000-system-health` - validate `.claude` registry, paths, stale references, and memory layout.
- `/010-search-assess` - code archaeology and impact analysis without implementation.
- `/020-quick-task` - small scoped edits, documentation updates, narrow cleanup.
- `/030-bug-triage` - reproduce, isolate, root-cause, and plan or apply a minimal fix.
- `/040-pytest-repair` - run backend pytest, group failures by error and file, repair, and rerun.

Full module lifecycle:

- `/100-state-init`
- `/110-discovery`
- `/120-architecture`
- `/130-design`
- `/140-requirements`
- `/150-planning`
- `/200-execution`
- `/210-quality`
- `/220-review`
- `/230-architecture-improvements`
- `/300-documentation`
- `/310-retrospective`
- `/320-state-close`

Operations:

- `/900-commit-push-github`
- `/910-rotate-docker-tags`

## Memory Layers

- Runtime memory: `.claude/current-dev-issues/.state/`
- Automation runtime: `.claude/scripts/.state/`
- Project memory: `.claude/project-memory/`
- Future backlog: `.claude/dev-future/<module-or-system>/`
- Archived packages and legacy material: `.claude/archive/`
- Durable docs: `docs/`

Runtime memory can be cleared after extraction. Project memory is a compact index for
future agents. Durable docs are the human-facing source of truth.

Detailed future development notes discovered during workflows `100-150` stay in a
module/system folder under `.claude/dev-future/`. Stable roadmap summaries are
promoted to `docs/06-roadmap/`.

## Validation

Run this after changing `.claude`:

```powershell
python .claude/scripts/validate-claude-system.py
```

Use the same command with `--check` for read-only health checks.
