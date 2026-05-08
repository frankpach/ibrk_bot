# Quickstart

Use this file only as a short launch guide. The canonical rules live in
`SYSTEM_CONTRACT.md`; the inventory lives in `registry.yaml`.

## Choose the Smallest Correct Workflow

Use a lightweight workflow when the task is narrow:

```text
/000-system-health --check
/010-search-assess <domain or feature>
/020-quick-task <short description>
/030-bug-triage <symptom or failing command>
/040-pytest-repair [optional-test-path-or-filter]
```

Use the full module pipeline when the work needs discovery, design, planning,
implementation, quality, review, documentation, and closure:

```text
/100-state-init <module>
/110-discovery <module>
/120-architecture <module>
/130-design <module>
/140-requirements <module>
/150-planning <module>
/200-execution <module> <issue>
/210-quality <module>
/220-review <module>
/230-architecture-improvements <module>
/300-documentation <module>
/310-retrospective <sprint>
/320-state-close <module>
```

Use operations only after validation passes:

```text
/900-commit-push-github <commit message>
/910-rotate-docker-tags
```

## Token Discipline

Every workflow starts with:

1. Read `SYSTEM_CONTRACT.md`.
2. Read `registry.yaml`.
3. Read the current workflow.
4. Read only the smallest relevant state/docs/source set.

Do not load archived docs, temporary docs, or full directories unless the workflow
explicitly requires them.

## Before and After Changes

Validate the system:

```powershell
python .claude/scripts/validate-claude-system.py --check
```

After editing `.claude`, run:

```powershell
python .claude/scripts/validate-claude-system.py
```

## Memory Rule

Active state belongs in `.claude/current-dev-issues/.state/`. Reusable project
knowledge belongs in `.claude/project-memory/`. Durable documentation belongs in
`docs/`.
