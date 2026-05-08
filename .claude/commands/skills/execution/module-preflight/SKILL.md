---
name: module-preflight
description: Phase 5 preflight - validate module scaffold, dependencies, and infrastructure before execution starts.
model: haiku
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Module Preflight — Validate Setup

Run once per module before execution starts. Verify:
- Module scaffold is correct (models, services, components exist)
- Module is registered in the system
- Dependencies are installed
- Database schema is initialized
- Event registration is complete

This skill is invoked in Phase 5 (Execution) with the `--preflight` flag:
```
/200-execution <module-name> <issue-1> --preflight
```

## Checks

- [ ] Module directory structure exists
- [ ] `__init__.py` files in place
- [ ] Models defined in `models.py`
- [ ] Services defined in `services.py`
- [ ] API routes defined in `api.py`
- [ ] React components in `components/`
- [ ] Module registered in `app/modules/__init__.py`
- [ ] Dependencies listed in `pyproject.toml` (backend) and `package.json` (frontend)
- [ ] Database migrations created
- [ ] Event definitions registered
- [ ] Tests directory structure ready

## Output

- [ ] All checks pass → ready to execute
- [ ] Any checks fail → blocks execution, must fix first

## Time Budget

5-10 minutes per module.
