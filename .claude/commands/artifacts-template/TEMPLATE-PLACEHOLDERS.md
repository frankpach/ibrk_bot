# Artifact Templates — Placeholders for Remaining Phases

This file documents what templates are needed and where they should go.

## Created Templates ✓

- [x] `01-design-concept-TEMPLATE.md` — Phase 0 output
- [x] `02-architecture-map-TEMPLATE.md` — Phase 1 output

## Needed Templates (To Create)

### 03-interface-design-TEMPLATE.md (Phase 2)
**What it should contain**:
- Chosen alternative (A, B, or C)
- Problem this solves (from design concept)
- Primary workflows (3+ key user journeys)
- Core interface (main entry points, methods/endpoints)
- Models involved (what gets created/extended)
- Events published/consumed
- Components to build
- Components to reuse/extend
- Trade-offs made
- Why not other alternatives

### 04-prd-TEMPLATE.md (Phase 3)
**What it should contain**:
- Problem statement (from design concept)
- Solution overview (from interface design)
- User personas & workflows
- Acceptance criteria (per workflow)
- Edge cases
- Technical requirements (models, services, events, APIs, components)
- Performance constraints
- Security/compliance requirements
- Success metrics

### 05-issues-TEMPLATE.md (Phase 4)
**What it should contain**:
- Phase grouping (Phase 1: core workflow, Phase 2: features, etc.)
- Per-issue template:
  - Title + classification (HITL/AFK)
  - What to build (user-facing outcome)
  - Acceptance criteria (checklist)
  - Definition of done (tests, code review, no errors)
  - Effort estimate (S/M/L/XL)
- Dependencies between issues
- Effort summary per phase

### 06-quality-report-TEMPLATE.md (Phase 6)
**What it should contain**:
- Summary (PASS/FAIL, timestamp)
- Per-check results:
  - ESLint
  - TypeScript
  - Unit tests
  - Integration tests
  - E2E tests
  - Coverage
  - Performance
  - Accessibility
- Rework history (if applicable)
- Sign-off for next phase

### 07-review-report-TEMPLATE.md (Phase 7)
**What it should contain**:
- Executive summary (code quality score, risk level, recommendation)
- P0 findings (must fix)
- P1 findings (should fix or defer)
- P2 findings (nice to have)
- Anti-pattern assessment (revisited)
- Code quality metrics
- Recommendation (APPROVE / NEEDS FIXES / NEEDS REDESIGN)
- Sign-off

### 08-architecture-backlog-TEMPLATE.md (Phase 8)
**What it should contain**:
- Summary (complexity, maintainability, scaling risk, reuse potential)
- Priority 1 improvements (do next sprint)
- Priority 2 improvements (do next quarter)
- Priority 3 concerns (monitor)
- Deferred findings from Phase 7
- Reuse opportunities for other modules
- Anti-pattern assessment (revisited)
- Recommendations for next sprint

## How to Create

Each template should follow the pattern:

1. **Purpose statement** (what is this artifact for?)
2. **Key sections** (major headings)
3. **Examples** (show what good looks like)
4. **Sign-off** (who approves, when)

Use the existing templates as examples.

## Time to Create

- Each template: 20-30 minutes
- Total: ~2-3 hours for all 6
- Can be done by copying from corresponding workflow file and adding examples

