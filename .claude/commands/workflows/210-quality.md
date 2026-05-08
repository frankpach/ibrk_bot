---
name: 210-quality
description: Quality phase - comprehensive validation of all code. Linting, type-checking, tests, E2E, performance.
model: haiku
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Phase 6: Quality — Validate Everything

## Purpose

Run **comprehensive quality checks** on the complete module. Verify linting, type safety, test coverage, E2E, and performance.

**Output**: A quality report. If all checks pass, proceed to Phase 7. If any fail, circle back to Phase 5.

## Prerequisites

- Phase 0-5 complete
- All issues from Phase 4 are merged
- Fresh context (or quick check mode)

## Process

### Step 1: Run Quality Checks

```
/210-quality <module-name>
```

The skill will:
1. **Linting**: ESLint on all module code
2. **Type Safety**: TypeScript `tsc --noEmit` on module
3. **Unit Tests**: Jest on all unit tests
4. **Integration Tests**: API tests against test database
5. **E2E Tests**: Playwright on all user workflows
6. **Coverage**: Verify test coverage > 80%
7. **Performance**: Check for console warnings, slow operations
8. **Accessibility**: Basic a11y checks (if applicable)

### Step 2: Review the Quality Report

The skill produces a report:

```
✓ ESLint: 0 errors, 0 warnings
✗ TypeScript: 3 type errors
✓ Unit tests: 45/45 passing
✗ E2E tests: 2 failures
✓ Coverage: 87%
✓ Accessibility: OK
```

**For each failure**, the report includes:
- What failed
- Why it failed
- Suggested fix

### Step 3: Decide: Pass or Rework

**If everything passes** ✓:
- Proceed to Phase 7 (Code Review)

**If anything fails** ✗:
1. **Review the failure**: Is it a real issue or a false positive?
2. **Decide**: Can you fix it now, or does it need architectural change?
3. **Fix it**: Either:
   - **Simple fix** (typo, missing test): Skill fixes and re-runs
   - **Needs rework**: Circle back to Phase 5 for specific issue
   - **Needs design change**: Circle back to Phase 2-3
4. **Re-run quality checks** until everything passes

**Common fixes**:
- ESLint: Skill auto-fixes or you explain the violation
- TypeScript: Skill adds type annotations or you clarify type
- Test failure: Skill debugs or you verify acceptance criteria
- E2E failure: Skill debugs UI automation or you verify workflow
- Coverage: Skill adds missing test or you decide it's not critical

## Quality Standards

The module is **quality-ready** only when:

| Check | Standard |
|-------|----------|
| ESLint | 0 errors, 0 warnings (auto-fix applied) |
| TypeScript | 0 type errors, strict mode |
| Unit tests | > 80% coverage, all passing |
| Integration tests | All passing, mocked external deps |
| E2E tests | All 3 critical workflows passing |
| Performance | No console errors/warnings in E2E |
| Accessibility | No automated a11y violations |

## Output Artifact

Skill automatically saves to:

```
/docs/dev/artifacts/<module-name>/06-quality-report.md
```

**Format**:
```markdown
# Quality Report: <Module Name>

## Summary
- Started: [timestamp]
- Completed: [timestamp]
- Overall: PASS or FAIL

## Checks

### ESLint
✓ PASS — 0 errors, 0 warnings

### TypeScript
✓ PASS — 0 type errors (strict mode)

### Unit Tests
✓ PASS — 45/45 passing, 87% coverage

### Integration Tests
✓ PASS — 12/12 passing

### E2E Tests
✓ PASS — 3/3 critical workflows passing

### Performance
✓ PASS — No console errors

### Accessibility
✓ PASS — No automated a11y violations

## Rework History (if applicable)
- Attempt 1: ESLint failed → fixed
- Attempt 2: E2E test failed → fixed
- Attempt 3: All checks pass ✓

## Sign-Off
- By: [LLM/User]
- Date: [timestamp]
- Ready for Phase 7: [YES/NO]
```

## Failure Scenarios

### Scenario 1: ESLint Violations
**Issue**: Code doesn't follow style guide
**Fix**: Auto-fix violations, or update `.eslintrc` if rule is wrong
**Escalate if**: Rule conflicts with project standard

### Scenario 2: TypeScript Errors
**Issue**: Types are missing or wrong
**Fix**: Skill adds type annotations, or you clarify types from Phase 3 PRD
**Escalate if**: Type system doesn't match architecture

### Scenario 3: Test Failures
**Issue**: Test expects different behavior
**Fix**: Skill debugs test vs code, or you verify acceptance criteria from Phase 4
**Escalate if**: Acceptance criteria unclear

### Scenario 4: E2E Test Failures
**Issue**: User workflow doesn't work as expected
**Fix**: Skill debugs UI automation, or you verify workflow from Phase 3 PRD
**Escalate if**: Workflow requirement misunderstood in Phase 2-3

### Scenario 5: Low Test Coverage
**Issue**: Some code paths not tested
**Fix**: Skill identifies gap and adds test, or you decide coverage standard is wrong
**Escalate if**: Coverage requirement conflicts with code complexity

## Time Budget

- **Min**: 5 minutes (all checks pass immediately)
- **Typical**: 15-30 minutes (1-2 failures, quick fixes)
- **Max**: 1 hour (multiple failures requiring rework)

If it's taking longer than 1 hour, you probably need to circle back to Phase 5 for deeper fixes.

## Rules

- **No skipping checks**: All 7 checks must pass
- **Coverage > 80%**: Non-negotiable. If you disagree, that's a Phase 2-3 decision
- **Zero type errors**: TypeScript strict mode. No `any`
- **All E2E workflows**: The 3 critical workflows from Phase 3 PRD must all pass

## Context Management

**Before starting**: Fresh context, module name

**During Phase 6**:
- Skill runs checks (mostly mechanical, haiku model)
- You review failures and approve fixes
- Typical: 10-20k tokens per attempt

**After Phase 6**:
- If PASS: proceed to Phase 7
- If FAIL: fix and re-run (or circle back to Phase 5)

## Next Phase

If quality report is **PASS**:
```
/220-review <module-name>
```

If quality report is **FAIL**:
- Fix specific issues with `/200-execution <module-name> <issue-N>`
- Re-run `/210-quality <module-name>`
