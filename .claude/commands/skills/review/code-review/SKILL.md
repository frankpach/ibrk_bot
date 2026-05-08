---
name: code-review
description: Phase 7 review - human code review and architecture validation. Identifies P0/P1/P2 findings.
model: sonnet
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Code Review — Validate Architecture & Quality

Review the completed module for correctness, architecture alignment, and anti-patterns.

This skill is invoked in Phase 7 (Review):
```
/220-review <module-name>
```

## Review Criteria

1. **Correctness**: Logic bugs, edge cases
2. **Architecture**: Module isolation, event usage, service reuse
3. **Code Quality**: Clarity, maintainability, naming
4. **Anti-Patterns**: The 4 named anti-patterns from Phase 1

## Findings by Severity

**P0 — Must Fix** (blocks merge):
- Logic bugs that break acceptance criteria
- Security issues
- Architecture violations
- Performance regressions

**P1 — Should Fix** (before merge):
- Edge cases not handled
- Unclear code
- Anti-patterns detected
- Non-idiomatic code

**P2 — Nice to Have** (future):
- Code style improvements
- Refactoring opportunities
- Documentation gaps

## Output

Code review report saved to:
```
/docs/dev/artifacts/<module-name>/07-review-report.md
```

Includes:
- Executive summary (quality score, risk level, recommendation)
- P0 findings (must fix before merge)
- P1 findings (should fix, or document decision to defer)
- P2 findings (nice to have)
- Anti-pattern assessment
- Code quality metrics
- Sign-off

## Decision Logic

- **All P0s fixed**: Ready to merge
- **P1s present**: You decide (fix now or defer to Phase 8)
- **P2s only**: Can defer to future sprints

## Time Budget

10-60 minutes depending on findings.
