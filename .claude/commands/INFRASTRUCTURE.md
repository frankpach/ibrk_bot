# Claude System Infrastructure

This document describes the real `.claude` command system in this repository.
For the compact operating contract, read `SYSTEM_CONTRACT.md` first.

## Layout

```text
.claude/
  commands/
    SYSTEM_CONTRACT.md
    registry.yaml
    workflows/
    skills/
    artifacts-template/
  current-dev-issues/
    .state/
    done/
  current-dev-temp/
  dev-future/
  archive/
    packages/
  project-memory/
  scripts/
    validate-claude-system.py
    .state/
docs/
  dev/
  06-roadmap/
  04-modules/
```

## Operating Model

The system has two execution paths:

- Standalone path (`000-099`): system health, search and assessment, small task, bug triage.
- Full lifecycle path (`100-399`): definition, delivery, validation, documentation, retrospective, and state close.
- Operations path (`900-999`): release, push, and deployment maintenance workflows.

The lightweight path exists to minimize tokens and avoid forcing small work through
module discovery, design, and planning.

## Memory Model

Runtime memory:

- `.claude/current-dev-issues/.state/`
- active module state, current objective, issue status, recent tests
- safe to clear only after extraction

Project memory:

- `.claude/project-memory/`
- compact agent-facing indexes of reusable patterns, decisions, risks, and module map
- read before broad work, not before every tiny edit

Durable documentation:

- `docs/dev/artifacts/<module>/`
- `docs/04-modules/<module>/`
- `docs/dev/project-memory.md`
- human-facing source of truth

## Context Budget

Default loading order:

1. `SYSTEM_CONTRACT.md`
2. `registry.yaml`
3. current workflow
4. relevant runtime/project memory files
5. relevant docs
6. source files

Avoid loading:

- `.claude/dev-archive/`
- `.claude/dev-future/`
- `.claude/archive/`
- `.claude/current-dev-temp/` unless referenced by active state
- full `docs/` trees
- generated logs and checkpoints unless debugging automation

## Validation

Run:

```powershell
python .claude/scripts/validate-claude-system.py
```

The validator checks registry paths, active skill/workflow existence, stale references,
memory layout, and docs promotion paths.

## Extension Rules

When adding a workflow or skill:

- add it to `registry.yaml`;
- document whether it is lightweight, full-pipeline, automation, or deprecated;
- declare expected inputs and outputs;
- state what context files it may load;
- define when it must escalate to a larger workflow.
