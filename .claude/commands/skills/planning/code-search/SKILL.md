---
name: code_search
description: Mandatory code search before coding — find existing models, components, services
model: haiku
allowed-tools: Read Grep Glob Bash
argument-hint: [feature-name] [domain]
---

# Code Search — Mandatory Before Coding

**Purpose**: Find existing code before writing new code (reuse-before-build).

**Invocation**:
```
/code-search work_order maintenance
/code-search assignment technician
/code-search --full customer
```

**When**: ALWAYS before Phase 5 execution, after Phase 1 architecture.

---

## Process

### Step 1: Define Search Terms

Extract keywords from the feature:
- Feature: "work order assignment"
- Keywords: `work_order`, `assignment`, `technician`, `dispatch`

### Step 2: Search for Models

```bash
# Search for model definitions
grep -r "class.*Model" app/modules/ --include="*.py" | grep -i <keyword>

# Search for model usage
grep -r "work.order\|assignment\|dispatch" app/modules/ --include="*.py"

# Search for specific model names
grep -r "WorkOrder\|Technician\|Assignment" app/ --include="*.py"
```

**What to record**:
- Model name
- File path
- Key fields
- Reusability (yes/no/pattern only)

### Step 3: Search for Components

```bash
# Search for React components
find src/components -name "*.tsx" -type f | xargs grep -l -i <keyword>

# Search for component exports
grep -r "export.*function\|export.*class" src/components/ | grep -i <keyword>

# Search design system
find src/components/core/ui -name "*.tsx" -type f
```

**What to record**:
- Component name
- File path
- Purpose
- Reusability (yes/no/pattern only)

### Step 4: Search for Services

```bash
# Search for service classes
grep -r "class.*Service" app/services/ --include="*.py"

# Search for service methods
grep -r "def.*assign\|def.*dispatch" app/ --include="*.py"

# Search for core services
grep -r "notification\|files\|audit\|scheduler" app/core/services/ --include="*.py"
```

**What to record**:
- Service name
- File path
- Methods
- Reusability (yes/no)

### Step 5: Search for Events

```bash
# Search for event definitions
grep -r "events.listen\|@events.on" app/ --include="*.py"

# Search for event publishing
grep -r "events.publish\|events.emit" app/ --include="*.py"

# Search for specific events
grep -r "technician.online\|work_order.assigned" app/ --include="*.py"
```

**What to record**:
- Event name
- Publisher
- Listeners
- Payload structure

### Step 6: Update Code Index

Append active-module findings to `.claude/current-dev-issues/.state/code-index.yaml`.
Append reusable project-wide findings to `.claude/project-memory/code-patterns.md`:

```yaml
## New Entries (2026-04-30)

### Models
- path: app/modules/leases/models.py:LeaseAmendment
  purpose: Track changes to leases
  reusable: true
  fields: lease_id, change_type, effective_date, assigned_to
  notes: Pattern for work order assignment tracking

### Components
- path: src/components/core/ui/MediaUpload.tsx
  purpose: Image/file upload
  reusable: true
  props: onUpload, maxFiles, accept
  notes: Use for technician photos

### Services
- path: app/core/services/assignment_service.py
  purpose: Generic assignment logic
  reusable: true
  methods: assign(entity_id, user_id), unassign(entity_id)
  notes: Use for work order → technician assignment

### Events
- event: technician.online
  publisher: app.modules.technician
  payload: {technician_id, timestamp}
  listeners: maintenance (sync pending work orders)
```

### Step 7: Make Reuse Decision

For each finding, decide:

| Overlap | Fit | Decision |
|---------|-----|----------|
| ≥80% | ≥80% | **REUSE** — Use as-is |
| ≥50% | ≥50% | **EXTEND** — Add missing features |
| <50% | Pattern good | **REFACTOR** — Extract common logic |
| <30% | Nothing exists | **NEW** — Build from scratch |

**Record decision** in session log:
```markdown
## Reuse Decisions

1. **LeaseAmendment Model** → EXTEND
   - Overlap: 70% (tracks assignment, urgency, due dates)
   - Fit: 90% (same domain, same patterns)
   - Action: Add `maintenance_type`, `photo_urls` fields

2. **AssignmentService** → REUSE
   - Overlap: 85% (generic assign X to Y logic)
   - Fit: 100% (core service, designed for reuse)
   - Action: Call with WorkOrder entity

3. **Custom assignment logic** → AVOID
   - Reason: AssignmentService already exists
   - Rule: Don't reinvent assignment logic
```

---

## Output Format

Save search results to session log:

```markdown
# Code Search Results

**Feature**: Work order assignment  
**Domain**: maintenance  
**Date**: 2026-04-30

## Models Found

| Path | Name | Reusable | Notes |
|------|------|----------|-------|
| app/modules/leases/models.py | LeaseAmendment | ✅ Yes | Pattern for tracking changes |
| app/modules/leases/models.py | LeaseModel | ⚠️ Partial | Has assignment field |

## Components Found

| Path | Name | Reusable | Notes |
|------|------|----------|-------|
| src/components/core/ui/MediaUpload.tsx | MediaUpload | ✅ Yes | For technician photos |
| src/components/core/ui/FormBuilder.tsx | FormBuilder | ✅ Yes | For work order form |

## Services Found

| Path | Name | Reusable | Notes |
|------|------|----------|-------|
| app/core/services/assignment_service.py | AssignmentService | ✅ Yes | Generic assignment logic |
| app/core/services/notification_service.py | NotificationService | ✅ Yes | Send assignment alerts |

## Events Found

| Event | Publisher | Listeners | Notes |
|-------|-----------|-----------|-------|
| technician.online | technician module | maintenance | Sync pending work orders |

## Reuse Decisions

1. **LeaseAmendment Model** → EXTEND (70% overlap)
2. **AssignmentService** → REUSE (85% overlap)
3. **MediaUpload** → REUSE (design system component)
4. **Custom logic** → AVOID (service exists)

## Code Index Updated

`.claude/current-dev-issues/.state/code-index.yaml` updated with active-module entries.
`.claude/project-memory/code-patterns.md` updated only for reusable project patterns.

## Next Step

Proceed to Phase 5 execution with reuse strategy:
1. Extend LeaseAmendment model
2. Reuse AssignmentService
3. Compose MediaUpload + FormBuilder
```

---

## Rules

### Rule 1: Search Before Coding

**Never** write code without searching first.

**Why**: Prevents Model Blindness, Island Components, duplicate logic.

### Rule 2: Record All Findings

**Always** update `code-index.yaml` with search results.

**Why**: Future searches benefit from past work.

### Rule 3: Make Explicit Decision

**Always** decide: REUSE / EXTEND / REFACTOR / NEW.

**Why**: Forces conscious choice, not accidental duplication.

### Rule 4: Check Failed Attempts

**Before** searching during active module work, check
`.claude/current-dev-issues/.state/failed-attempts.md`.

For reusable project risks, check `.claude/project-memory/known-risks.md`.

**Why**: Avoid approaches that failed before.

---

## Anti-Patterns

### Anti-Pattern 1: Shallow Search

**Wrong**:
```bash
grep -r "WorkOrder" app/  # One search, done
```

**Right**:
```bash
# Multiple searches for comprehensive coverage
grep -r "class.*Model" app/modules/ --include="*.py" | grep -i work
grep -r "work.order" app/ --include="*.py"
grep -r "workorder\|work-order" app/ --include="*.py"
```

### Anti-Pattern 2: Ignoring Findings

**Wrong**: Find AssignmentService, build custom logic anyway

**Right**: Find AssignmentService → REUSE → save 4 hours

### Anti-Pattern 3: Not Recording

**Wrong**: Search, find great pattern, don't record it

**Right**: Search → find → record in code-index → future reuse

---

## Integration with Workflows

### Phase 1 (Architecture)

`discover-codebase` skill uses `code_search` internally.

### Phase 5 (Execution)

Before any coding:
```
/code-search <feature> <domain>
```

Then proceed with reuse strategy.

### Phase 8 (Architecture)

Periodic audit:
```
/code-search --full <module>
```

Check for duplication, anti-patterns.

---

## Time Budget

- Small feature (one domain): 5-10 minutes
- Medium feature (cross-module): 15-20 minutes
- Large feature (new domain): 30-45 minutes

---

## References

- `.claude/current-dev-issues/.state/code-index.yaml` - active module code index
- `.claude/current-dev-issues/.state/failed-attempts.md` - active failed approaches
- `.claude/project-memory/code-patterns.md` - reusable project patterns
- `.claude/project-memory/known-risks.md` - recurring risks
