---
name: 230-architecture-improvements
description: Architecture phase - look at the module holistically and identify improvement backlog for future sprints.
model: opus
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Phase 8: Architecture — Find Improvements for Next Sprint

## Purpose

Look at the completed module **holistically** and identify:
- Technical debt incurred during execution
- Architectural improvements for maintainability
- Opportunities to reuse patterns elsewhere
- Scaling concerns before they become problems

**Output**: A prioritized backlog of improvements (not bugs, not features — architectural work).

## Prerequisites

- Phase 0-7 complete
- Module is in production (or ready to merge)
- Fresh context

## Process

### Step 1: Analyze the Module

```
/230-architecture-improvements <module-name>
```

The skill will:
1. Read all code in the module
2. Analyze it against the original Phase 0 design intent
3. Look for:
   - Duplicated patterns that could be extracted
   - Tight coupling that could be loosened
   - Missing abstractions that would help scale
   - Places where the module deviates from the planned architecture
   - Opportunities to make this module reusable by other modules
4. Compare against anti-patterns from Phase 1
5. Produce an improvement backlog

### Step 2: Review the Architecture Report

The skill produces a report organized by:

**Category 1: Extraction Opportunities**
> "The work order assignment logic and the property assignment logic are 80% identical. Extract to a shared AssignmentService."

**Category 2: Architecture Alignment**
> "Phase 2 design said 'minimal interface' but the API has 23 endpoints. The top 3 workflows use 8 endpoints, the rest are rarely used. Move to v2 API."

**Category 3: Scaling Concerns**
> "The sync logic queries all work orders every 5 seconds. As the fleet grows, this will become a bottleneck. Recommend: pub/sub-driven sync."

**Category 4: Module Reuse**
> "The work order lifecycle (created→assigned→started→completed) is generic enough that the property inspection module could reuse it."

**Category 5: Debt Incurred**
> "Phase 3 PRD called for offline-first sync, but we implemented online-first with local caching. This works for now, but will cause issues at scale."

### Step 3: Prioritize & Backlog

The skill categorizes each improvement:

**Priority 1 — Do Next Sprint**:
- Blocking a new feature planned for next sprint
- Will significantly improve performance
- Reduces ongoing maintenance burden

**Priority 2 — Do in Next Quarter**:
- Nice to have, but not blocking anything
- Improves code clarity and maintainability
- Enables future features

**Priority 3 — Monitor**:
- Keep an eye on this, don't act yet
- May become important as product scales
- Revisit in 6 months

## Output Artifact

Skill automatically saves to:

```
/docs/dev/artifacts/<module-name>/08-architecture-backlog.md
```

**Format**:
```markdown
# Architecture Backlog: <Module Name>

## Summary
- Module complexity: MEDIUM
- Maintainability score: 7/10
- Scaling risk: LOW
- Reuse potential: HIGH
- Recommended next step: [specific improvement]

## Priority 1 — Do Next Sprint (2 improvements)

### Improvement 1: Extract AssignmentService
**Why**: Work order assignment and property assignment have 80% duplicate logic
**Impact**: Reduces code duplication by ~300 lines, improves maintainability
**Effort**: M (3-4 hours)
**Risk**: LOW (new service, no change to existing APIs)
**How**: Create shared service, use from both modules

### Improvement 2: Replace polling with pub/sub for sync
**Why**: Current 5-second polling will bottleneck with 100+ technicians
**Impact**: Improves real-time responsiveness, reduces server load
**Effort**: L (8-10 hours)
**Risk**: MEDIUM (changes sync mechanism, must verify offline scenarios)
**How**: Subscribe to events instead of polling, maintain local cache for offline

## Priority 2 — Do in Next Quarter (3 improvements)

### Improvement 1: Simplify API surface
**Why**: 23 endpoints, but 80% of workflows use 8
**Impact**: Improves documentation, reduces cognitive load
**Effort**: M (4-6 hours)
**Risk**: LOW (breaking change only if clients depend on v1)
**How**: Move rarely-used endpoints to v2 API, deprecate v1

### Improvement 2: Add real-time filters to work order list
**Why**: Current list doesn't support real-time sorting/filtering
**Impact**: Improves UX, enables custom views per technician
**Effort**: M (4-6 hours)
**Risk**: LOW (new feature, doesn't break existing API)
**How**: Add query parameters to GET /work-orders/assigned

### Improvement 3: Refactor UI components for reuse
**Why**: WorkOrderDetail component is 60% specific, 40% generic
**Impact**: Other modules could reuse generic parts
**Effort**: M (4-6 hours)
**Risk**: LOW (internal refactor, no API changes)
**How**: Extract generic FormWithMedia component, use from WorkOrderDetail

## Priority 3 — Monitor (2 improvements)

### Improvement 1: Consider sharding by geography
**Why**: As we add more technicians, sync queries will grow linearly
**Impact**: Would improve performance at scale (1000+ technicians)
**Effort**: XL (20+ hours) — not worth doing yet
**Risk**: HIGH (architecture change)
**When to act**: When we have 500+ technicians or see sync latency > 2s

### Improvement 2: Implement conflict resolution for offline edits
**Why**: Current approach: last-write-wins. Could lose data if two technicians edit same order offline
**Impact**: Better data consistency, fewer support tickets
**Effort**: L (8-10 hours)
**Risk**: HIGH (changes sync semantics, could break existing workflow)
**When to act**: When we see actual conflicts in production, or if offline rate > 50%

## Deferred From Phase 7 Review (2 findings moved here)

### P1: Direct import of tenant filtering logic
**Status**: Deferred to Phase 8
**Why**: Works for now, but if we scale to 10+ modules, we should extract to core
**Action**: Add to Priority 2, revisit if we build 3+ more modules

### P1: WorkOrderList component lacks virtualization
**Status**: Deferred to Phase 8
**Why**: Performance is fine for current data volume (~500 orders), will degrade at 10k orders
**Action**: Add to Priority 3, monitor performance in production

## Opportunities for Other Modules

### Can this module be reused?
**Yes** — The assignment lifecycle and offline sync are generic enough that:
- Inspection module could use this
- Maintenance visits module could use this
- Service call scheduling could use this

**How to enable reuse**:
- Extract AssignmentService (see Priority 1)
- Document the offline sync pattern
- Consider publishing as a shared library

## Anti-Pattern Assessment (Revisited)

### Model Blindness: ✓ CLEAN
No redundant models. WorkOrderModel, TechnicianAssignment, and SyncLog are distinct.

### Island Components: ⚠️ MINOR DEBT (P2)
40% of WorkOrderDetail component could be generic. Extract as Priority 2 improvement.

### Pub/Sub Bypass: ⚠️ MODERATE DEBT (P1)
Assignment logic uses direct imports instead of events. Extract to service and consume events.

### UX Amnesia: ✓ CLEAN
Design clearly reflects field technician use case. Offline-first sync validates this.

## Recommendations for Next Sprint

1. **Do this first**: Extract AssignmentService (Priority 1) — unblocks other improvements
2. **Then do**: Replace polling with pub/sub (Priority 1) — improves performance before it becomes a problem
3. **Backlog**: Priority 2 improvements for next quarter
4. **Monitor**: Priority 3 improvements, revisit every sprint

## Architecture Health Score

| Dimension | Score | Notes |
|-----------|-------|-------|
| Cohesion | 8/10 | Module has single responsibility, well-defined boundaries |
| Coupling | 7/10 | Some direct imports should be events (P1 debt) |
| Testability | 9/10 | Good unit/integration/E2E test coverage |
| Maintainability | 7/10 | Clear code, but could reduce duplication (P2) |
| Scalability | 7/10 | Works for current load, polling will bottleneck at scale (P1 concern) |
| Reusability | 6/10 | Components and services are somewhat generic, could extract more (P2) |

**Overall: 7.3/10 — Solid foundation, improve before scaling**

## Sign-Off
- Reviewed: [timestamp]
- Recommended path: [Priority 1 improvements first, then Priority 2 and 3]
- Next review: [after next sprint or when module grows 50%]
```

## What This Is NOT

This phase is **not**:
- Bug fixing (bugs are issues for Phase 5)
- Feature planning (features are Phase 0-4 work)
- Refactoring for personal preference (refactoring only if it reduces debt or improves maintainability)
- Scope creep (don't add things Phase 0 didn't plan)

This phase **is**:
- Understanding what debt you incurred
- Identifying what to improve before scaling
- Planning the next sprint's architecture work

## Common Improvements Found

| Type | Example | Why It Matters |
|------|---------|----------------|
| Extraction | "Sync logic duplicated in 2 modules" | Reduces maintenance burden |
| Abstraction | "Direct imports should use events" | Loosens coupling, enables reuse |
| Scaling | "Polling will bottleneck at 1000 users" | Prevents future firefighting |
| API Design | "23 endpoints when 8 would do" | Improves discoverability, reduces cognitive load |
| Testing | "Missing edge case tests in sync logic" | Prevents production incidents |
| Reuse | "Assignment lifecycle is generic" | Enables other modules to ship faster |

## Time Budget

- **Min**: 15 minutes (simple module, few improvements)
- **Typical**: 30-45 minutes (comprehensive analysis)
- **Max**: 1 hour (complex module, many opportunities)

This is a thorough, but quick analysis. Don't spend more than 1 hour here.

## After Phase 8

1. **Copy the backlog path**: `/docs/dev/artifacts/<module-name>/08-architecture-backlog.md`
2. **Add Priority 1 improvements** to your next sprint backlog
3. **Share Priority 2 improvements** with the team for future planning
4. **Monitor Priority 3 concerns** and revisit if conditions change
5. **Clear context**: `/clear` (manually)
6. **Move to Phase 9**: Update `/docs` with module documentation

## Next Phase

```
/300-documentation <module-name>
```

Update the module documentation in `/docs/04-modules/<module-name>/` with:
- Overview
- Architecture (models, services, events)
- API endpoints
- Component library
- How to extend or reuse this module
