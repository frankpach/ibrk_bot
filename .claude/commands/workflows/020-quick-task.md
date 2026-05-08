---
name: 020-quick-task
description: Lightweight path for small scoped edits, docs updates, and narrow cleanup without the full module pipeline.
model: sonnet
allowed-tools: Read Grep Glob Bash Edit Write
argument-hint: <task>
---

# Quick Task

Use this for small work with a clear boundary.

## Context Budget

Load at most:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. one relevant project-memory file, if needed
5. only the target files

Do not load runtime state unless the task touches active module execution.

## Fit Criteria

Use this workflow when all are true:

- scope is one narrow behavior, doc, script, or config area;
- no product discovery is needed;
- no module lifecycle state change is required;
- validation can be named before editing.

Escalate to the full pipeline if the task becomes module-sized, cross-layer,
architectural, or unclear.

## Process

1. State the task, scope, risk, and validation command.
2. Search target files for existing patterns.
3. Make the smallest change that satisfies the task.
4. Run targeted validation.
5. Write a compact note only if the result should persist:
   - runtime note for active issue work;
   - project-memory note for reusable knowledge;
   - docs update for durable human-facing knowledge.

## Output

Return:

- files changed;
- validation run and result;
- memory/docs updated, if any;
- whether escalation was avoided or required.
