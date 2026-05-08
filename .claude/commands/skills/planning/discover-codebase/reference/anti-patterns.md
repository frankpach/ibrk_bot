# Anti-Patterns in Code Archaeology

When exploring the codebase in Phase 1, watch for these four anti-patterns. They're the most common architectural failures in this project.

## Anti-Pattern 1: Model Blindness

**What it is**: Designing a new model without checking if one already exists that covers 80% of your needs.

**Why it happens**: 
- Easy to miss existing models (they might be in a different module)
- Exciting to build new things
- "Our model is slightly different, so we need our own"

**The cost**:
- Duplicate data in the database (sync problems)
- Inconsistent business logic (two models of the same concept)
- Maintenance burden (updating the concept in 2 places)

### WRONG: Model Blindness

```
You're building a maintenance module. You create:
  - WorkOrderModel (your new model)

But the leases module already has:
  - LeaseAmendmentModel (tracks changes to leases)
  - Which includes: type (repair/inspection), property_id, urgency, due_date, assignee

Result: You've recreated 80% of the concept in a new model.
You now have duplicate logic for "assigning work to people" in two places.
```

### RIGHT: Model Extension

```
You're building a maintenance module. You find:
  - LeaseAmendmentModel (tracks changes to leases)
  - Can be extended with maintenance-specific fields

You decide:
  - Extend LeaseAmendmentModel for work orders
  - OR create WorkOrderModel that reuses LeaseAmendment's assignment logic
  - Use a single table/schema pattern

Result: One source of truth. One place to update business logic.
```

### Diagnostic Question

> "Does this model cover 80% of what I need? Can I extend it instead?"

If yes → extend it. If no → create a new one.

---

## Anti-Pattern 2: Island Components

**What it is**: Building custom UI components instead of extending or reusing design system components.

**Why it happens**:
- Design system components are in a different folder (out of sight)
- Easier to build something quick than learn an existing pattern
- "Our component is slightly different, so we need our own"

**The cost**:
- Inconsistent UX across the app (different design systems)
- Maintenance burden (updating a pattern in 10 places)
- Development slowdown (reimplementing the same thing)

### WRONG: Island Components

```
You're building a work order form. You create:
  - WorkOrderForm component (custom)
  - Which includes: text input, date picker, checkbox for "urgent"

But core/ui already has:
  - FormBuilder (generic form components)
  - DatePicker (reusable, handles locales)
  - Checkbox (reusable, handles accessibility)

You built an island. Other modules can't use your form. 
You can't update the design system pattern here.
```

### RIGHT: Component Reuse

```
You're building a work order form. You discover:
  - FormBuilder in core/ui (handles form lifecycle)
  - DatePicker in core/ui (handles dates)
  - Checkbox in core/ui (handles accessibility)

You decide:
  - Compose these components into a WorkOrderForm
  - If FormBuilder doesn't support "urgent" toggle, extend it
  - WorkOrderForm is now a thin wrapper, easy to maintain

Result: Consistent UX. One place to update design patterns.
```

### Diagnostic Question

> "Does core/ui already have a component that does 80% of what I need?"

If yes → reuse/extend it. If no → build a new one.

---

## Anti-Pattern 3: Pub/Sub Bypass

**What it is**: Importing directly from another module instead of listening to events it publishes.

**Why it happens**:
- Tighter coupling means simpler logic (no events to subscribe to)
- Events might not exist yet
- "I just need one field from that table"

**The cost**:
- Tight coupling (changes in one module break another)
- Hidden dependencies (not visible in the interface)
- Scalability problems (modules can't evolve independently)

### WRONG: Pub/Sub Bypass

```
You're building the maintenance module. You write:

  from app.modules.technician.models import TechnicianModel
  
  @app.route('/work-orders/assigned')
  def list_assigned():
    technician = TechnicianModel.query.get(current_user.id)
    if not technician.is_online:
      return empty_list
    return work_orders...

Result: Tight coupling. Maintenance module imports from technician module.
If technician module refactors, maintenance breaks.
```

### RIGHT: Pub/Sub

```
You're building the maintenance module. You write:

  from app.events import events
  
  @events.listen('technician.online')
  def on_technician_online(technician_id):
    sync_pending_work_orders(technician_id)
  
  @app.route('/work-orders/assigned')
  def list_assigned():
    return work_orders...

Result: Loose coupling. Maintenance module listens to events.
Technician module can refactor without breaking maintenance.
Events are the contract.
```

### Diagnostic Question

> "Am I importing directly from another business module? Should I use events instead?"

If yes → use events. If no → you're good.

---

## Anti-Pattern 4: UX Amnesia

**What it is**: Designing the interface without thinking about the actual user, their device, and their constraints.

**Why it happens**:
- Easy to design for the "happy path" (connected, desktop, lots of time)
- Actually using the product is different than designing it
- "We can add mobile support later"

**The cost**:
- Interface doesn't match reality (users can't use it)
- Offline doesn't work (but field technicians need it)
- Takes 3x longer to ship (building for one user, realizing too late it's wrong)

### WRONG: UX Amnesia

```
You're building a maintenance module. You design:

  WorkOrderForm (desktop form, all fields visible)
  - Large form with 20 fields
  - Requires good internet connection
  - Requires precise mouse clicks
  - Requires wide screen

Who uses it: Field technicians on mobile devices with spotty connectivity.

Result: The form doesn't fit on a phone screen. 
Field technicians can't use it offline. 
You ship it and get support tickets.
```

### RIGHT: User-First Design

```
You're building a maintenance module. You think about the user first:

  Primary user: Field technician
  Device: Mobile phone (iPhone, Android)
  Environment: Outdoor, moving between properties
  Biggest constraint: Battery, connectivity

You design:

  WorkOrderDetail (mobile-first)
  - Large touch targets
  - Offline-first (works without internet)
  - Minimal fields on main screen (scroll for details)
  - One action per screen (start work, add photo, mark complete)
  
Result: Technician can complete work without internet.
Each action takes 2-3 taps. Fits in pocket. Ships with positive feedback.
```

### Diagnostic Question

> "Can I describe the user and their context? (device, environment, constraints)"

If yes → design for that context. If no → ask Phase 0 (discovery) to clarify.

---

## How to Detect Them During Archaeology

### Detecting Model Blindness
**Grep for**: Model definitions, field names similar to your domain
```bash
grep -r "class.*Model" app/models/
grep -r "work.order\|assignment\|dispatch" app/
```

**Ask**: "Is there already a model that covers 80% of this?"

### Detecting Island Components
**Grep for**: Components in different folders
```bash
find src/components/core/ui -name "*.tsx"
find src/features/*/components -name "*.tsx"
```

**Ask**: "Did core/ui already solve this problem?"

### Detecting Pub/Sub Bypass
**Grep for**: Direct module imports
```bash
grep -r "from app.modules\\..*import" app/modules/
grep -r "import.*Model.*from.*modules" app/
```

**Ask**: "Should this be an event subscription instead?"

### Detecting UX Amnesia
**Read**: The design concept from Phase 0

**Ask**: "Does the interface match the user's device and environment?"

---

## Documenting Anti-Patterns in Architecture Map

When you find an anti-pattern, document it in your output:

```markdown
## Anti-Patterns Detected

### Model Blindness: POTENTIAL ISSUE
I found LeaseAmendmentModel in the leases module. It's 80% of what 
WorkOrderModel needs (assignment, urgency, due date). 

Question: Should we extend LeaseAmendmentModel instead of creating 
WorkOrderModel?

### Island Components: CLEAR
MediaUpload and FormBuilder in core/ui solve 90% of the UI needs. 
Don't build custom components.

### Pub/Sub Bypass: POTENTIAL ISSUE
The technician module publishes technician.online. The sync logic 
should listen to this event, not poll the technician table.

### UX Amnesia: NOT APPLICABLE
Design concept clearly describes field technician as primary user 
(mobile, offline, field). This will shape interface design.
```

---

## Severity Scale

**CLEAR**: This anti-pattern is definitely happening. Flag it.

**POTENTIAL ISSUE**: This anti-pattern might be happening. Ask a clarifying question.

**NOT APPLICABLE**: This anti-pattern doesn't apply to this module.

**RESOLVED**: This anti-pattern was flagged in an earlier phase and has been addressed.
