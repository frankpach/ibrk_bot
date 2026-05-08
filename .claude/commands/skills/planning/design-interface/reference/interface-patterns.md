# Interface Patterns — Good Designs to Emulate

When proposing the 3 alternatives in Phase 2, refer to these patterns. They're proven designs that work in practice.

## Pattern 1: State Machine Interface (Depth-First)

**When to use**: When the module manages a lifecycle with clear states.

**Example**: Work orders go assigned → started → completed

**How it works**:
```
WorkOrder state: "assigned" | "started" | "completed"

From "assigned" you can:
  - Call start_work() → transitions to "started"
  - Call cancel() → transitions to "cancelled"

From "started" you can:
  - Call complete() → transitions to "completed"
  - Call cancel() → transitions to "cancelled"

From "completed" you can:
  - Call reopen() → transitions to "assigned"
```

**Interface**:
```python
class WorkOrderController:
  def get(id): → WorkOrder (read-only)
  def update_status(id, new_status): → updates if transition is valid
  def get_available_actions(id): → list of valid transitions from current state
```

**Pros**:
- Encodes business logic (no invalid state transitions possible)
- Minimal interface (few methods)
- Easy to understand (state machine is explicit)

**Cons**:
- Hard to add new states (requires modifying the controller)
- Hard to reuse (state machine is built-in)
- Not flexible for edge cases

**Good for**: Simple, well-defined lifecycles with few states (3-5)

---

## Pattern 2: Workflow-Based Interface (User-First)

**When to use**: When different users have different workflows that converge on the same data.

**Example**: 
- Dispatcher assigns work → Technician completes it → Manager reviews it

**How it works**:
```
Three separate views/endpoints:

AssignmentController (for dispatcher):
  - list_pending() → unassigned work orders
  - assign(work_order_id, technician_id) → creates assignment
  - bulk_assign(work_order_ids, technician_ids) → batch operations

WorkOrderController (for technician):
  - list_assigned() → my work orders
  - get_detail(id) → full details
  - update_status(id, status) → changes status + notes + photos

ReviewController (for manager):
  - list_all() → all work orders with status
  - get_metrics() → completion rate, avg time, etc.
```

**Pros**:
- Each workflow optimized for its user (dispatcher gets bulk, technician gets detail)
- Clear separation of concerns
- Easy to evolve each independently

**Cons**:
- More code overall
- Risk of duplication (assignment logic in two places)
- More API surface to document

**Good for**: Modules with 2-3 distinct user workflows

---

## Pattern 3: Composable Components Interface (Reusability-First)

**When to use**: When you're building a platform where multiple modules need similar patterns.

**Example**: Assignment, lifecycle, and notification are used in:
- Maintenance (work orders assigned to technicians)
- Inspections (inspections assigned to inspectors)
- Service calls (calls assigned to technicians)

**How it works**:
```
Core abstractions:

LifecycleStateMachine:
  - generic state machine you can configure
  - maintenance: created → assigned → started → completed
  - inspection: created → assigned → scheduled → completed
  - Used by both modules, configured differently

AssignmentService:
  - generic "assign something to someone" logic
  - maintenance: assign work order to technician
  - inspection: assign inspection to inspector
  - Used by both, with different entity types

EventPublisher:
  - generic event publishing
  - maintenance publishes: work_order.assigned, work_order.completed
  - inspection publishes: inspection.assigned, inspection.completed
  - Used by both with different events

WorkOrderModule composes these:
  - Use LifecycleStateMachine for states
  - Use AssignmentService for dispatch
  - Use EventPublisher for events
  - Add maintenance-specific fields (urgency, photos, etc.)
```

**Pros**:
- Highly reusable (inspection module ships faster)
- Loosely coupled (modules don't depend on each other)
- Enables platform-level patterns

**Cons**:
- More abstraction upfront
- More code to maintain
- Overkill if modules don't actually reuse patterns

**Good for**: Platforms with 4+ modules that follow similar patterns

---

## Pattern 4: Hybrid: State Machine + Events

**When to use**: When you have a state machine and other modules need to react to state changes.

**How it works**:
```
WorkOrder has an internal state machine (Pattern 1):
  - assigned → started → completed (only valid transitions)

When state changes, publish events (Pattern 1 + events):
  - on_assigned() → publish work_order.assigned
  - on_started() → publish work_order.started
  - on_completed() → publish work_order.completed

Other modules (notifications, audit) listen to events:
  - notifications listens to work_order.assigned → sends push alert
  - audit listens to work_order.* → logs all changes
```

**Pros**:
- Strong encapsulation (state machine inside)
- Loose coupling (other modules use events, not imports)
- Extensible (new modules can listen without changing maintenance)

**Cons**:
- Slightly more code (events + state machine)
- Eventual consistency (events are async)

**Good for**: Most modules (it's the balanced choice)

---

## Anti-Pattern: Too Many Entry Points

**WRONG**:
```
Alternative D: REST Purist
  GET /work-orders
  GET /work-orders/:id
  POST /work-orders
  PATCH /work-orders/:id
  DELETE /work-orders/:id
  GET /work-orders/assigned
  GET /work-orders/assigned/:id
  POST /work-orders/:id/assign
  POST /work-orders/:id/unassign
  POST /work-orders/:id/start
  POST /work-orders/:id/complete
  POST /work-orders/:id/cancel
  POST /work-orders/:id/photos
  [... 15+ endpoints]
```

This LOOKS comprehensive but:
- Hard to discern the conceptual model from the API
- "What operation do I use for X?" requires documentation
- Adding a new concept (e.g., "unassign") requires adding endpoints

**Better**: Combine related operations
```
POST /work-orders/:id/status → single endpoint for state transitions
  body: { status: "completed", notes: "...", photos: [...] }

GET /work-orders/:id/available-actions → learn what's possible from current state

POST /work-orders/:id/assign
  body: { technician_id: "..." }

This is still REST but with fewer, richer endpoints.
```

**Rule**: If you're proposing more than 5-6 endpoints for one concept, you might be inflating the interface.

---

## Real Examples from This Project

### Example 1: Leases Module (User-First)
```
Interface: Lease lifecycle
  - GET /leases/:id (read lease)
  - PATCH /leases/:id (modify lease)
  - POST /leases/:id/renew (extend lease)
  - POST /leases/:id/terminate (end lease)
  - GET /leases/expiring (list expiring for renewal)

Why this design:
  - Primary user: property manager (desktop, office)
  - Workflows: renew or terminate leases
  - Operations are verb-based (renew, terminate)
```

### Example 2: Notifications Module (Composable)
```
Interface: Generic notification system
  - NotificationService.send(user_id, message, action)
  - NotificationService.listen(event_type) → callback

Other modules use it:
  - Maintenance publishes work_order.assigned → notifications sends alert
  - Leases publishes lease.expiring → notifications sends reminder
  - Inspections publishes inspection.due → notifications sends alert

Why this design:
  - Reusable by all modules
  - Loosely coupled (via events)
  - Each module publishes own events, notifications handles rest
```

---

## Choosing the Right Pattern

| Question | Answer → Pattern |
|----------|------------------|
| Is this a simple state machine? (3-5 states) | Pattern 1 (State Machine) |
| Do different users have different workflows? | Pattern 2 (Workflow-Based) |
| Will other modules reuse this? | Pattern 3 (Composable) |
| Do you need both state machine AND events? | Pattern 4 (Hybrid) |
| Are you unsure? | Pattern 2 (Workflow-Based) — it's safe and flexible |

---

## Red Flags in Interface Design

If you see any of these in an alternative, flag it:

1. **No state management**: "Here's a data object, do whatever you want with it" → Fragile
2. **Too many entry points**: 10+ endpoints for one concept → Inflated
3. **Unclear transitions**: "Can I call update() when status is X?" → Ambiguous
4. **All events, no logic**: "Everything is async, we'll figure it out" → Complicated
5. **All logic, no events**: "Other modules import directly" → Tightly coupled

---

## Reference: How to Describe an Interface

When presenting an alternative, use this structure:

```markdown
## Alternative X: [Name]

### Conceptual Design
[Explain the core idea in 2-3 sentences]

### Key Entities
- [Entity 1]: [brief description]
- [Entity 2]: [brief description]

### Main Workflows
1. [Workflow 1]: A → B → C
2. [Workflow 2]: X → Y → Z

### API/Interface
```
[code sketch of main methods/endpoints]
```

### Trade-offs
| Dimension | This Alternative | Implication |
|-----------|------------------|-------------|
| Simplicity | High/Med/Low | ... |
| Extensibility | High/Med/Low | ... |
| Reusability | High/Med/Low | ... |

### Best for
[When to choose this approach]

### Risks
[What could go wrong if you choose this]
```

---

## Learning More

These patterns come from:
- RESTful API Design (Richardson Maturity Model)
- Domain-Driven Design (entities, value objects, aggregates)
- Event-Driven Architecture
- Microservices patterns (communication patterns)

When proposing alternatives, you're deciding:
1. **Granularity**: One big interface (state machine) vs many small ones (REST)
2. **Coupling**: Direct imports vs events
3. **Reusability**: Module-specific vs platform-level abstraction
