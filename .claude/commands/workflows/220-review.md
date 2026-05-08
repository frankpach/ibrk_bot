---
name: 220-review
description: Review phase - human code review and architecture validation. Identifies issues and recommends fixes.
model: sonnet
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Phase 7: Review — Code & Architecture Review

## Purpose

Have the code and architecture **reviewed by an LLM code reviewer** for:
- Correctness (logic bugs, edge cases)
- Architecture (module isolation, event usage, service reuse)
- Code quality (clarity, maintainability, naming)
- Anti-patterns (the 4 from Phase 1)

**Output**: A review report with P0/P1/P2 findings and recommendations.

## Prerequisites

- Phase 6 (Quality) passed with all checks green
- All issues from Phase 4 merged
- Fresh context

## Process

### Step 1: Run Code Review

```
/220-review <module-name>
```

The skill will:
1. Read all code in the module
2. Review against the PRD from Phase 3
3. Check for the 4 anti-patterns from Phase 1 architecture
4. Look for logic bugs and edge cases
5. Assess code quality and clarity
6. Produce a review report with findings and recommendations

### Step 2: Read the Review Report

The report categorizes findings by severity:

**P0 — Must Fix (Blocks Merge)**:
- Logic bugs that break acceptance criteria
- Security issues
- Architecture violations (direct imports, event bypass)
- Performance regressions

**P1 — Should Fix (Before Merge)**:
- Edge cases not handled
- Unclear code that will confuse future devs
- Anti-patterns detected
- Non-idiomatic code

**P2 — Nice to Have (Future)**:
- Code style improvements
- Refactoring opportunities
- Performance optimizations
- Documentation gaps

### Step 3: Decide & Fix

For each finding:

**P0**: This blocks merge. Skill will:
- Explain the issue
- Suggest the fix
- Implement the fix
- You review the fix
- Commit with a reference to the review finding

**P1**: You decide. Either:
- "Fix it now" → Skill fixes and you review
- "I'll accept the risk and merge" → Document the decision
- "Circle back later" → Add to Phase 8 (architecture backlog)

**P2**: Usually deferred to Phase 8 or future sprints.

### Step 4: Re-Review (if needed)

If Skill made fixes:
1. Review the changes
2. Run Phase 6 (Quality) again to ensure fixes didn't break tests
3. Approve or request changes
4. Merge once you approve

## Output Artifact

Skill automatically saves to:

```
/docs/dev/artifacts/<module-name>/07-review-report.md
```

**Format**:
```markdown
# Code Review: <Module Name>

## Executive Summary
- Code Quality: 8/10
- Architecture Alignment: 9/10
- Risk Level: LOW
- Recommendation: APPROVE (with minor fixes)

## P0 Findings (Must Fix)
### Finding 1: Direct import from leases module
**Location**: `maintenance/services/work_order.py:15`
**Issue**: Importing directly instead of listening to events
**Fix**: Replace direct import with event subscription
**Impact**: Violates pub/sub contract, tight coupling

### Finding 2: Missing error handling on external API call
**Location**: `maintenance/api/dispatch.py:42`
**Issue**: No timeout or retry on notifications API call
**Fix**: Add timeout and retry logic
**Impact**: Could hang if notifications service is slow

## P1 Findings (Should Fix)
### Finding 1: Unclear variable naming
**Location**: `maintenance/components/WorkOrderDetail.tsx:88`
**Issue**: Variable `x` stores the work order status
**Fix**: Rename to `currentStatus` for clarity
**Impact**: Maintenance burden

### Finding 2: Missing null check
**Location**: `maintenance/services/list_assigned.py:23`
**Issue**: Assumes technician always has a team
**Fix**: Add guard clause or default behavior
**Impact**: Edge case, won't crash, but behavior undefined

## P2 Findings (Nice to Have)
### Finding 1: Extract duplicate code
**Location**: `maintenance/api/endpoints.py` lines 15-25, 40-50
**Issue**: Same validation logic duplicated
**Fix**: Extract to shared validator function
**Impact**: Maintenance, no functional impact

## Anti-Pattern Check

### Model Blindness: ✓ PASS
Architecture map shows LeaseModel and PropertyModel exist. WorkOrderModel is new and doesn't duplicate.

### Island Components: ✓ PASS
WorkOrderList extends core/ui components (FormBuilder, MediaUpload), doesn't duplicate.

### Pub/Sub Bypass: ⚠️ MINOR ISSUE (P1)
Found one direct import in work_order_service.py — should use events instead.

### UX Amnesia: ✓ PASS
Design clearly describes technician workflow (field, mobile, offline) and dispatcher workflow (office, desktop).

## Code Quality Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Clarity | 8/10 | Variable names clear, logic is easy to follow |
| Correctness | 9/10 | One edge case missing (technician without team) |
| Test Coverage | 9/10 | 87% coverage, good integration tests |
| Architecture | 8/10 | Mostly follows patterns, one pub/sub violation |
| Security | 10/10 | No obvious vulnerabilities |

## Recommendation
**APPROVE WITH FIXES** — Fix the 2 P0 findings, then merge. P1 findings can be deferred if timeline is tight.

## Sign-Off
- Reviewer: [LLM Code Reviewer]
- Date: [timestamp]
- Ready for Merge: [YES (after P0 fixes) / NO (needs more work)]
```

## Finding Severity Guide

**P0 — Critical (Blocks Merge)**
- The code violates a principle from Phase 0-3 (architecture, design, requirements)
- The code has a logic bug that breaks acceptance criteria
- The code introduces a security issue
- The code violates pub/sub or service contracts
- The code will cause performance problems in production

**P1 — Important (Should Fix)**
- The code works but is unclear or fragile
- The code handles an edge case incorrectly (but doesn't crash)
- The code duplicates existing patterns or components
- The code will be confusing to maintain
- The code violates anti-patterns from Phase 1

**P2 — Nice to Have (Can Defer)**
- The code could be refactored for clarity (but is understandable)
- The code could be optimized (but is performant enough)
- The code could use better variable naming (but is functional)
- The code could have better documentation (but is usable)

## Conflict Scenarios

### Scenario 1: You Disagree with a P0 Finding
**Situation**: Reviewer says "direct import violates pub/sub" but you think it's fine for this case.

**Options**:
1. **Accept the finding**: Circle back to Phase 2-3 to revise the architecture decision
2. **Challenge the finding**: You can request a second opinion (escalate to yourself as architect)
3. **Document the exception**: Add a comment explaining why you're breaking the rule, and log it in Phase 8

### Scenario 2: Review Reveals a Bigger Problem
**Situation**: Reviewer finds an issue that requires architectural change from Phase 2-3.

**Action**: Don't patch it. Circle back to Phase 2-3, revise the design, and re-execute affected issues.

### Scenario 3: Too Many P1 Findings
**Situation**: Review finds 10 P1 findings and the timeline is tight.

**Decision**: You decide. Either:
- "Fix all P1s now" → More time, better quality
- "Fix P1s now, defer minor P1s to Phase 8" → Faster to production, tech debt noted
- Circle back to Phase 5 for deeper fixes

## Time Budget

- **Min**: 10 minutes (clean code, few findings)
- **Typical**: 20 minutes (a few P1s, maybe one P0)
- **Max**: 1 hour (many findings, needs discussion)

If review takes > 1 hour, you might need to:
- Circle back to Phase 5 for deeper fixes
- Revisit Phase 2-3 for architectural changes
- Defer some findings to Phase 8

## Rules

- **All P0s must be fixed** before merge
- **P1s are your choice**: You decide which to fix now vs defer
- **Document your decisions**: If you defer a P1, explain why
- **No "I'll fix it later"**: If you defer work, it goes to Phase 8 (explicit backlog), not "maybe someday"

## Context Management

**Before starting**: Fresh context, module name

**During Phase 7**:
- Skill reviews code (comprehensive, uses sonnet model)
- You decide on each P1 finding
- If fixes needed: skill fixes and you approve
- Typical: 30-50k tokens per review

**After Phase 7**:
- If review is APPROVE: proceed to Phase 8
- If review is NEEDS FIXES: fix and re-run Phase 6 (quality) then Phase 7 again
- If review finds architecture issue: circle back to Phase 2-3

## Next Phase

If review is **APPROVED**:
```
/230-architecture-improvements <module-name>
```

If review has **P0 findings**:
- Fix the P0s with `/200-execution <module-name> <issue-N>`
- Re-run Phase 6 (Quality)
- Re-run Phase 7 (Review)

If review reveals **architectural problems**:
- Circle back to Phase 2 or 3
- Revise the design
- Re-execute affected issues
