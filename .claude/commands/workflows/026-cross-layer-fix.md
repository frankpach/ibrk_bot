---
name: 026-cross-layer-fix
description: small cross-layer corrections — add fields to existing responses, sync form+api, adjust pydantic schemas. requires user confirmation before first write.
model: sonnet
allowed-tools: Read Grep Glob Bash Edit Write
argument-hint: <feature> <what-needs-to-change>
---

# Cross-Layer Fix

Use this when a frontend correction requires a matching change in an existing backend
endpoint or schema. Does not create new modules, endpoints, or migrations.

## Context Budget

Load at most:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `CLAUDE.backend.md` — API Contract and StandardResponse sections only
5. `CLAUDE.frontend.md` — apiClient and types sections only
6. target BE files: router + schema + service for the affected endpoint
7. target FE files: hook/query + component/form
8. `frontend/src/locales/` only if the change touches i18n keys

## Fit Criteria

Use this workflow when all are true:

- the endpoint already exists; only a field or schema is changing;
- no migration is required;
- no `core/auth/` or RBAC logic is touched;
- no new module is introduced.

Escalate to the full pipeline if a new endpoint is needed, a migration is required,
or the change touches more than one module.

## Process

1. Map the current contract: endpoint path, Pydantic schema, FE types, apiClient call.
2. Identify the minimum delta in BE and FE.
3. **Present the delta to the user and wait for explicit confirmation before any write.**
   List: BE files that will change, FE files that will change, and whether a migration
   could be needed (if yes — stop and escalate).
4. Update BE first: Pydantic schema → service → router (in that order).
5. Update FE: types → apiClient → hook/query → component/form → i18n if needed.
6. Run validation gates:
   - `cd backend && uv run pytest tests/ -v -k <relevant-test>`
   - `cd frontend && npx tsc --noEmit`
   - `npx tsx scripts/verify-i18n.ts --module <module>` (only if i18n was touched)

## Output

Return:

- BE files changed;
- FE files changed;
- i18n keys added, if any;
- validation gate results;
- whether escalation was avoided or required.
