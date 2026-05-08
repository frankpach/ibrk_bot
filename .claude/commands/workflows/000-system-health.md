---
name: 000-system-health
description: Validate the local .claude workflow, skill, memory, and documentation contract.
model: haiku
allowed-tools: Read Glob Bash
argument-hint: [--check]
---

# System Health

Use this before and after changing `.claude`.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. validator output

Do not load workflow bodies unless the validator points to a specific failure.

## Process

Run:

```powershell
python .claude/scripts/validate-claude-system.py --check
```

Use without `--check` after edits:

```powershell
python .claude/scripts/validate-claude-system.py
```

## Output

Report:

- PASS or FAIL
- failed file/path checks
- stale reference findings
- missing memory/docs paths
- next minimal repair

## Escalation

Stop if validation fails in active workflows or skills. Repair the contract before
running module work.
