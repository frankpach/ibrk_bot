---
name: improve-codebase
description: Phase 8 architecture - analyze module holistically and identify improvement backlog for future sprints.
model: opus
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Improve Codebase — Find Architectural Improvements

Look at the completed module holistically to identify improvements for future sprints.

This skill is invoked in Phase 8 (Architecture):
```
/230-architecture-improvements <module-name>
```

## Analysis

1. **Extraction Opportunities**: Code duplication across modules
2. **Architecture Alignment**: Does the module match Phase 2 design intent?
3. **Scaling Concerns**: What will break at 10x the current load?
4. **Module Reuse**: Can other modules reuse these patterns?
5. **Debt Incurred**: What compromises were made during execution?

## Backlog Priorities

**Priority 1 — Do Next Sprint**:
- Blocking a new feature
- Significantly improves performance
- Reduces maintenance burden

**Priority 2 — Do in Next Quarter**:
- Nice to have
- Improves maintainability
- Enables future features

**Priority 3 — Monitor**:
- Keep an eye on
- Revisit when circumstances change

## Output

Architecture backlog saved to:
```
/docs/dev/artifacts/<module-name>/08-architecture-backlog.md
```

Includes:
- Summary (complexity, maintainability, scaling risk, reuse potential)
- Priority 1 improvements (2-3 items)
- Priority 2 improvements (2-3 items)
- Priority 3 concerns (monitoring items)
- Deferred findings from Phase 7
- Opportunities for other modules to reuse
- Anti-pattern assessment (revisited)
- Recommendations for next sprint

## This Is NOT

- Bug fixing (Phase 5)
- Feature planning (Phases 0-4)
- Refactoring for personal preference (only for debt/maintainability)

## Time Budget

15-45 minutes per module.
