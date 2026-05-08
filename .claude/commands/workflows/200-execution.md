---
name: 200-execution
description: Execution phase - implement a single issue using TDD. Code, tests, and validation.
model: sonnet
allowed-tools: Read Grep Glob Bash Edit Write
argument-hint: [module-name] [issue-number]
---

# Phase 5: Execution — Implement One Issue

## Purpose

Take **one vertical-slice issue** from Phase 4 and execute it end-to-end using **Test-Driven Development (TDD)**: write tests first, then code, then validate.

**Output**: Passing tests, working code, no console errors, and merged to `main`.

## Prerequisites

- Phase 0-4 complete
- Issue list from Phase 4
- Each issue has clear acceptance criteria
- Fresh context (user has cleared it, or starting a new issue)

## Process

### Step 1: Run Module Preflight (once per module)

```
/200-execution <module-name> <issue-1> --preflight
```

Before executing any issue in a module, run preflight once to:
1. Verify the module scaffold is correct (models, services, components exist)
2. Verify the module is registered in the system
3. Verify dependencies are installed
4. Set up any one-time infrastructure (database schema, event registration)

**You only run this once per module**. Subsequent issues skip this step.

### Step 2: Execute the Issue with TDD

```
/200-execution <module-name> <issue-number>
```

The skill will:
1. Read the issue acceptance criteria
2. Write tests first (unit + integration + E2E)
3. Run tests (they fail — red)
4. Implement code to pass tests
5. Run tests again (they pass — green)
6. Refactor if needed (keep tests passing)
7. Validate no console errors, no regressions

**Your role**: Approve at each gate (after tests, after implementation, before merge).

### Step 3: Validate the Implementation

The skill will:
- ✓ Run all tests (unit, integration, E2E)
- ✓ Check for console errors
- ✓ Verify acceptance criteria
- ✓ Check TypeScript/ESLint
- ✓ Spot-check code review standards

**If anything fails**:
- Tests fail → skill fixes code and re-runs
- Console errors → skill fixes and re-runs
- Code review issues → skill refactors
- Acceptance criteria not met → skill adds implementation

**You approve or request changes** before merge.

### Step 4: Merge & Move to Next Issue

Once the issue passes all gates:
1. Commit code with message referencing the issue
2. Push to feature branch (or main if no PR workflow)
3. Mark issue as done in tracker
4. Clear context manually
5. Start next issue with `/200-execution <module-name> <issue-2>`

## Issue Execution Order

**Run issues in dependency order**:
1. Core workflows (usually issues 1-2)
2. Features that depend on core (usually issues 3-5)
3. Quality-of-life features (usually issues 6+)

**Example sequence** for a work order system:
1. ✓ Technician can view assigned work orders
2. ✓ Technician can update work order status
3. ✓ Dispatcher can assign work order to technician
4. ✓ Send notification when assigned
5. ✓ Sync offline changes

## What TDD Means in This Phase

**Red Phase**: Write tests that fail
- Unit test: does the service method work?
- Integration test: does the API endpoint return the right data?
- E2E test: can the user perform the workflow in the UI?

**Green Phase**: Write code to pass tests
- Implement the model/service
- Implement the API endpoint
- Implement the UI component

**Refactor Phase**: Keep tests passing, improve code
- Extract duplicates
- Improve variable names
- Optimize performance

## Acceptance Criteria for the Issue

The issue from Phase 4 lists acceptance criteria. By end of this phase:
- ✓ All criteria checked off
- ✓ All tests passing
- ✓ No console errors
- ✓ Code follows project standards
- ✓ Documentation updated (if needed)

## Context Management

**Before starting**: Fresh context + one issue number

**During Phase 5**:
- Skill implements the issue (you review gates)
- One issue per session (to stay in smart zone)
- Typical: 40-60k tokens per issue

**After Phase 5**:
- Commit and push to repo
- Manual context clear (user runs `/clear`)
- Next issue starts with fresh context

## Time Budget (per issue)

- **Small (S)**: 1-2 hours (simple endpoint or component)
- **Medium (M)**: 4-6 hours (cross-layer feature)
- **Large (L)**: 8-12 hours (complex feature with many edge cases)
- **XL**: 16+ hours (major feature, break into 2 issues)

## Gates Before Merge

Each issue has these gates:

### Gate 1: Tests Pass ✓
- All unit tests pass
- All integration tests pass
- No failing E2E tests

### Gate 2: Acceptance Criteria Met ✓
- Every checkbox from Phase 4 issue is verified
- No partial implementations
- All workflows work end-to-end

### Gate 3: No Console Errors ✓
- Browser console: no errors or warnings
- Server logs: no errors
- E2E test console: clean

### Gate 4: Code Quality ✓
- TypeScript: no type errors
- ESLint: no violations
- No duplicated code
- Variable names are clear

### Gate 5: No Regressions ✓
- Previous issues still work
- No breaking changes to shared code
- All existing tests still pass

## Handling Blockers

If you hit a blocker (missing dependency, unclear requirement, architecture issue):
1. **Document the blocker** in the issue comments
2. **Ask for clarification** or raise it to Phase 2-3
3. **Don't work around it** — don't add flags, don't hack
4. **Escalate if needed**: if a design issue, circle back to Phase 2

## Handling Test Failures

If a test fails:
1. **Read the error message** — usually it tells you exactly what failed
2. **Decide**: Is the test wrong (requirement misunderstood) or code wrong?
3. **If code is wrong**: Skill will fix it
4. **If test is wrong**: Verify with Phase 4 issue, update test if requirement changed
5. **Re-run tests**

## After Each Issue

1. **Commit with message**: `[Module] Issue #N: Brief description`
2. **Mark done in tracker**
3. **Clear context**: `/clear`
4. **Next issue**: `/200-execution <module-name> <issue-N+1>`

**Don't skip phases** — each issue goes through preflight/TDD/gates in order.

## Rules

- **Tests first**: Never code before writing tests
- **Complete the issue**: Don't leave it "half-working"
- **No technical debt**: If you see something wrong, don't leave it for later — fix it now
- **Ask before guessing**: If acceptance criteria are unclear, ask Phase 4 or Phase 3 for clarification
- **Language**: All new code text must be in English (DB columns, variables, comments, notes). Apply only to new/modified code. Rename existing elements only if it does not break functionality.

## Next Phase

Once **all issues from Phase 4 are done**:
```
/210-quality <module-name>
```

Run quality gates and validate the complete module.
