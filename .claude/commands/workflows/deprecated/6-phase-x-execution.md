---
auto_execution_mode: 3
description: This is a workflow to execute a specific phase from the plan.
---
*THE FIRST STEP IS TO ASK THE USER FOR THE PLAN {PLAN} AND PHASE {PHASE} TO EXECUTE.*


SCOPE:

- Execute ONLY Phase {PHASE}.
- Follow the plan checklist tasks in order (Task IDs).
- Do NOT invent tasks or expand scope.
- Do NOT refactor unless the plan explicitly requires it.

────────────────────────────────────────
0) PRE-EXECUTION GATES (MUST PASS)
────────────────────────────────────────

1) Read and comply with:

- .windsurf/rules/ (all applicable)
- @docs
- .windsurf/workflows/00-promp-backend-footer.md
- .windsurf/workflows/00-promp-frontend-footer.md

2) Verify current code state:

- Git status clean OR explicitly document existing changes.
- On correct branch.
- Baseline tests (if required by the plan) pass.

2.1) Run module preflight check (MANDATORY for module work):

- Execute `.windsurf/workflows/0-module-preflight-check.md`
- Confirm module scaffold is valid (backend/frontend)
- Confirm `contracts.yaml` exists for business modules
- Confirm `get_dependencies()` matches `modules.json.depends_on`
- Confirm no direct imports between business modules

If preflight fails → STOP and report.

3) Contract Validation (MANDATORY, before coding):

- Identify frontend expectations for the scope:
  * request/response DTOs
  * routes/endpoints
  * error format
- Verify backend compatibility.
- Confirm response wrapper: { data, error }
- Confirm error handling uses APIException (NOT HTTPException)
- Confirm multi-tenancy: tenant_id filtering enforced in all relevant queries
- Confirm Type Safety:
  * backend: full type hints
  * frontend: TypeScript strict types where touched
- Confirm i18n: useTranslation() for any new/modified UI text
- Confirm module contracts:
  * `contracts.yaml` present and updated
  * `module.meta.json` aligned with `contracts.yaml`
  * `modules.json` aligned with hard dependencies

IF any gate fails → STOP and report:

- What failed
- Evidence (files/paths)
- Minimal fix options (no code unless explicitly requested)

────────────────────────────────────────

1) EXECUTION STRATEGY (BRIEF)
   ────────────────────────────────────────
   Write a 5-bullet execution strategy for Phase {PHASE} aligned to the plan:

- order of tasks
- risk points
- validation approach
- tests to run per task
- documentation updates

────────────────────────────────────────
2) EXECUTE TASKS (ONE BY ONE)
────────────────────────────────────────
For each checklist task in Phase {PHASE}:

A) Restate the task:

- Task ID + Title
- Target files
- Expected output artifact
- Test command(s)

B) Implement ONLY what the task requires.

C) Run the task's test/validation command(s).
Use the official commands when applicable:

- **Run tests**: Execute `.windsurf/workflows/8-quality-tests.md`
- Or individual: `aiutox test backend` / `aiutox test frontend` / `aiutox test`
- Migrations: alembic revision / alembic upgrade head

D) Update documentation and the plan:

- Check off the task in the plan file
- Update any specified docs/rules/workflow notes

E) Record a mini execution log per task:

- Files changed (paths)
- What changed (1–3 bullets)
- Tests run + result
- Docs updated

If a test fails:

- Perform root-cause analysis (short)
- Apply the minimal fix
- Re-run ONLY the relevant tests
- Do not proceed to the next task until passing

────────────────────────────────────────
3) PHASE GATE (MUST PASS BEFORE NEXT PHASE)
────────────────────────────────────────
Before declaring Phase {PHASE} complete, verify:

- All Phase {PHASE} tasks checked off in the plan
- **Run quality tests**: Execute `.windsurf/workflows/8-quality-tests.md`
- **Run quality gate**: Execute `.windsurf/workflows/9-quality-gate.md`
- Contract validation still holds (DTOs/routes/error format)
- Module preflight check passes
- contracts.yaml/module.meta.json/modules.json consistency preserved
- Multi-tenancy enforced (tenant_id)
- APIException used where relevant
- Response wrapper { data, error } preserved
- i18n useTranslation() used for UI text touched
- Docs updated as required

If anything is missing → Phase {PHASE} is NOT complete. STOP and report.

────────────────────────────────────────
4.5) POST-PHASE (OPTIONAL - RUN IF APPLICABLE)
────────────────────────────────────────

After Phase Gate passes, optionally execute:

A) **Commit & Push** (if there are changes to commit):
- Execute `.windsurf/workflows/900-commit-push-github.md`
- Includes pre-commit scripts, commit, push, and verify GitHub Actions

B) **Docker Deploy** (if changes are deployable):
- Execute `.windsurf/workflows/910-rotate-docker-tags.md`
- Build + push new image + rotate tags (keep max 3)

C) **Sprint Retrospective** (if sprint is closing):
- Execute `.windsurf/workflows/10-sprint-retrospective.md`
- Capture lessons learned for next sprint

────────────────────────────────────────
4) OUTPUT (STRICT)
────────────────────────────────────────
Return:

- Phase {PHASE} completion status: Complete / Blocked
- Completed tasks (Task IDs)
- Remaining tasks (Task IDs)
- Failures encountered + fixes applied
- Tests executed (commands)
- Docs updated (paths)
- Next immediate action (one)
- Proactive recommendations (code, tech, infrastructure, UI/UX improvements)

────────────────────────────────────────
5) NEXT STEP & RECOMMENDATIONS
────────────────────────────────────────

At the end of each execution, ALWAYS provide:

A) NEXT STEP (clear and concise):
- If Phase {PHASE} is COMPLETE → What is the next phase to execute?
- If Phase {PHASE} is BLOCKED → What is needed to unblock?
- If there are remaining tasks → Which task is next?

B) PROACTIVE RECOMMENDATIONS (optional but encouraged):
Suggest improvements in these areas when relevant:

- **Code Quality**: Refactoring opportunities, technical debt, SOLID violations
- **Performance**: Query optimizations, caching opportunities, lazy loading
- **UX/UI**: Better component patterns, accessibility improvements, loading states
- **Infrastructure**: Docker improvements, CI/CD optimizations, monitoring
- **Developer Experience**: Better error messages, logging, debugging tools
- **Security**: Input validation, authorization checks, data protection

Format recommendations as:
```
### Next Step
[Clear statement of what comes next]

### Recommendations
- **[Area]**: [Specific suggestion] → [Expected benefit]
```
