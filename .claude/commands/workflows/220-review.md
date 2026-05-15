---
name: 220-review
description: Review phase - human code review and architecture validation. Identifies issues and recommends fixes.
model: sonnet
allowed-tools: Read, Grep, Glob, Bash
argument-hint: [module-name]
---

# Phase 7: Review — Code & Architecture Review

## Purpose

Have the code and architecture **reviewed by an LLM code reviewer** for:
- **Correctness** — logic bugs, edge cases
- **Architecture** — module isolation, event usage, service reuse
- **Code Quality** — clarity, maintainability, naming
- **Anti-patterns** — the 4 from Phase 1

**Output**: A review report with P0/P1/P2 findings and recommendations.

## Prerequisites

- [ ] Phase 6 (Quality) passed with all checks green
- [ ] All issues from Phase 4 merged
- [ ] Fresh context loaded

## Severity Definitions

| Level | Name | Action |
|-------|------|--------|
| **P0** | Critical | **Must fix** — blocks merge |
| **P1** | Important | **Should fix** — your decision |
| **P2** | Nice to Have | **Can defer** — log in Phase 8 |

**P0 — Critical (Blocks Merge)**
- Violates principles from Phase 0-3 (architecture, design, requirements)
- Logic bug that breaks acceptance criteria
- Security issue
- Violates pub/sub or service contracts
- Will cause performance problems in production

**P1 — Important (Should Fix)**
- Works but is unclear or fragile
- Handles an edge case incorrectly (but doesn't crash)
- Duplicates existing patterns or components
- Will be confusing to maintain
- Violates anti-patterns from Phase 1

**P2 — Nice to Have (Can Defer)**
- Could be refactored for clarity (but is understandable)
- Could be optimized (but is performant enough)
- Could use better variable naming (but is functional)
- Could have better documentation (but is usable)

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

The report categorizes findings by severity. See [Severity Definitions](#severity-definitions) above for criteria.

**P0 — Must Fix**: Logic bugs, security issues, architecture violations, performance regressions.

**P1 — Should Fix**: Edge cases, unclear code, anti-patterns, non-idiomatic code.

**P2 — Nice to Have**: Style improvements, refactoring opportunities, optimizations, documentation gaps.

### Step 3: Decide & Fix

For each finding:

**P0** — This blocks merge. Skill will:
- Explain the issue
- Suggest the fix
- Implement the fix
- You review the fix
- Commit with a reference to the review finding

**P1** — You decide. Either:
- **"Fix it now"** → Skill fixes and you review
- **"Accept the risk and merge"** → Document the decision
- **"Circle back later"** → Add to Phase 8 (architecture backlog)

**P2** — Usually deferred to Phase 8 or future sprints.

### Step 4: Re-Review (if needed)

If skill made fixes:
1. Review the changes
2. Run Phase 6 (Quality) again to ensure fixes didn't break tests
3. Approve or request changes
4. Merge once you approve

## Output Artifact

Skill automatically saves to:

```
/docs/dev/artifacts/<module-name>/07-review-report.md
```

**Report Structure**:

```markdown
# Code Review: <Module Name>

## Executive Summary
| Metric | Score |
|--------|-------|
| Code Quality | 8/10 |
| Architecture Alignment | 9/10 |
| Risk Level | LOW |
| **Recommendation** | **APPROVE** (with minor fixes) |

## P0 Findings (Must Fix)
### [ID]: [Title]
- **Location**: `file/path.py:15`
- **Issue**: [description]
- **Fix**: [recommended change]
- **Impact**: [why it matters]

## P1 Findings (Should Fix)
### [ID]: [Title]
- **Location**: `file/path.py:42`
- **Issue**: [description]
- **Fix**: [recommended change]
- **Impact**: [why it matters]

## P2 Findings (Nice to Have)
### [ID]: [Title]
- **Location**: `file/path.py:88`
- **Issue**: [description]
- **Fix**: [recommended change]
- **Impact**: [why it matters]

## Anti-Pattern Check
| Pattern | Status | Notes |
|---------|--------|-------|
| Model Blindness | ✓ / ✗ | |
| Island Components | ✓ / ✗ | |
| Pub/Sub Bypass | ✓ / ✗ | |
| UX Amnesia | ✓ / ✗ | |

## Code Quality Assessment
| Aspect | Rating | Notes |
|--------|--------|-------|
| Clarity | 8/10 | |
| Correctness | 9/10 | |
| Test Coverage | 9/10 | |
| Architecture | 8/10 | |
| Security | 10/10 | |

## Recommendation
[APPROVE / APPROVE WITH FIXES / NEEDS WORK]

## Sign-Off
- **Reviewer**: [LLM Code Reviewer]
- **Date**: [timestamp]
- **Ready for Merge**: [YES / NO]
```

## Conflict Scenarios

### Scenario 1: You Disagree with a P0 Finding
**Situation**: Reviewer says "direct import violates pub/sub" but you think it's fine for this case.

**Options**:
1. **Accept the finding** → Circle back to Phase 2-3 to revise the architecture decision
2. **Challenge the finding** → Request a second opinion (escalate to yourself as architect)
3. **Document the exception** → Add a comment explaining why you're breaking the rule, and log it in Phase 8

### Scenario 2: Review Reveals a Bigger Problem
**Situation**: Reviewer finds an issue that requires architectural change from Phase 2-3.

**Action**: Don't patch it. Circle back to Phase 2-3, revise the design, and re-execute affected issues.

### Scenario 3: Too Many P1 Findings
**Situation**: Review finds 10 P1 findings and the timeline is tight.

**Decision**: You decide. Either:
- **"Fix all P1s now"** → More time, better quality
- **"Fix P1s now, defer minor P1s to Phase 8"** → Faster to production, tech debt noted
- **Circle back to Phase 5** for deeper fixes

## Time Budget

| Scenario | Duration |
|----------|----------|
| **Min** | 10 min (clean code, few findings) |
| **Typical** | 20 min (a few P1s, maybe one P0) |
| **Max** | 1 hour (many findings, needs discussion) |

If review takes > 1 hour, you might need to:
- Circle back to Phase 5 for deeper fixes
- Revisit Phase 2-3 for architectural changes
- Defer some findings to Phase 8

## Rules

1. **All P0s must be fixed** before merge
2. **P1s are your choice** — you decide which to fix now vs. defer
3. **Document your decisions** — if you defer a P1, explain why
4. **No "I'll fix it later"** — if you defer work, it goes to Phase 8 (explicit backlog), not "maybe someday"

## Context Management

**Before starting**: Fresh context, module name

**During Phase 7**:
- Skill reviews code (comprehensive, uses sonnet model)
- You decide on each P1 finding
- If fixes needed: skill fixes and you approve
- Typical: 30-50k tokens per review

**After Phase 7**:
- **APPROVE** → proceed to Phase 8
- **NEEDS FIXES** → fix and re-run Phase 6 (quality) then Phase 7 again
- **Architecture issue** → circle back to Phase 2-3

## Next Phase

```
If APPROVED:         /230-architecture-improvements <module-name>
If P0 findings:      /200-execution <module-name> <issue-N> → Phase 6 → Phase 7
If architecture gap: Phase 2 or 3 → revise design → re-execute
```
