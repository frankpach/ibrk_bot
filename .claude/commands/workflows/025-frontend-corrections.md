---
name: 025-frontend-corrections
description: targeted frontend corrections — forms, i18n, component reuse, layout. no backend changes.
model: sonnet
allowed-tools: Read Grep Glob Bash Edit Write
argument-hint: <feature-path> <correction: form|i18n|component|style>
---

# Frontend Corrections

Use this for focused frontend changes with a clear boundary and no backend contract changes.

## Context Budget

Load at most:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `CLAUDE.frontend.md` — i18n, apiClient, component conventions
5. target feature files only
6. `frontend/src/locales/` only if the change touches i18n keys

Do not load backend addenda, runtime state, or unrelated feature files.

## Fit Criteria

Use this workflow when all are true:

- change is confined to one feature or component area;
- no new endpoint and no schema response change is required;
- no migration is needed;
- validation commands can be named before editing.

Escalate to `026-cross-layer-fix` if any backend file must change.
Escalate to the full pipeline if the change is feature-sized or introduces new product behavior.

## Process

1. Identify the correction type (form / i18n / component / style) and target files.
2. Search `frontend/src/components/` for reusable components before writing new ones;
   classify each candidate as REUSE, EXTEND, or NEW.
3. Make the smallest change that satisfies the correction; add i18n keys if missing.
4. Run validation gates:
   - `cd frontend && npx tsc --noEmit`
   - `npx tsx scripts/verify-i18n.ts --module <module>` (only if i18n was touched)
5. Report: files changed, components reused vs new, i18n keys added, gate results.

## Output

Return:

- files changed;
- components reused / extended / created;
- i18n keys added, if any;
- validation gate results;
- whether escalation was avoided or required.
