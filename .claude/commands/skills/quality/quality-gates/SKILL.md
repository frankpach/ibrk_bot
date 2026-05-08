---
name: quality-gates
description: Phase 6 quality - run comprehensive checks on the module. Linting, type safety, tests, E2E, performance.
model: haiku
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Quality Gates — Validate All Checks

Run comprehensive quality checks on the completed module after all issues are merged.

This skill is invoked in Phase 6 (Quality):
```
/210-quality <module-name>
```

## Checks

1. **ESLint**: 0 errors, 0 warnings (auto-fix applied)
2. **TypeScript**: 0 type errors (strict mode)
3. **Unit Tests**: > 80% coverage, all passing
4. **Integration Tests**: All passing, mocked external deps
5. **E2E Tests**: All critical workflows passing
6. **Performance**: No console errors/warnings
7. **Accessibility**: No automated a11y violations

## Output

Quality report saved to:
```
/docs/dev/artifacts/<module-name>/06-quality-report.md
```

Includes:
- Summary (PASS/FAIL)
- Results for each check
- Rework history (if applicable)
- Sign-off for Phase 7

## Decision Logic

- **All checks pass**: Proceed to Phase 7 (Review)
- **Any check fails**: Circle back to Phase 5 (Execution) to fix
- **Coverage < 80%**: Add missing tests

## Time Budget

5-30 minutes per attempt.
