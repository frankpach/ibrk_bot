---
name: phase-run
description: Phase 5 execution - implement a single issue using TDD. Write tests first, code second, validate third.
model: sonnet
allowed-tools: Read Grep Glob Bash Edit Write
argument-hint: [module-name] [issue-number]
---

# Phase Run — Execute One Issue with TDD

Implement a single vertical-slice issue from Phase 4 (Planning) using Test-Driven Development.

This skill is invoked in Phase 5 (Execution):
```
/200-execution <module-name> <issue-number>
```

## Process

1. **Read the issue** acceptance criteria from Phase 4 output
2. **Write tests first** (red phase)
   - Unit tests
   - Integration tests
   - E2E tests
3. **Implement code** to pass tests (green phase)
4. **Refactor** while keeping tests passing
5. **Validate** no console errors, no regressions
6. **Commit & merge** when all gates pass

## Gates Before Merge

- [ ] All tests pass
- [ ] All acceptance criteria verified
- [ ] No console errors
- [ ] TypeScript: no type errors
- [ ] ESLint: no violations
- [ ] No regressions

## Output

- Code merged to main branch
- Issue marked done in tracker
- Ready for Phase 6 (Quality)

## Time Budget

Per issue, varies by size (S: 1-2h, M: 4-6h, L: 8-12h, XL: break into 2 issues)

## Methodology

This skill uses **Test-Driven Development (TDD)**:
1. Write failing test (red)
2. Write minimal code to pass (green)
3. Refactor while passing (refactor)
4. Repeat for each feature
