# Architecture Map: [Module Name]

**Status**: ✓ Complete  
**Date**: [Date]  
**Phase**: 1 (Architecture Discovery)  
**Module**: [module-name]  

---

## Existing Models

[Describe models that already exist in the codebase related to this module's domain]

### Model 1: [Name]
- **Purpose**: [What does it represent?]
- **Key fields**: [id, status, created_at, ...]
- **Used by**: [Which modules use it?]
- **Relevance**: [How does this relate to your module?]

Example:
> **LeaseModel**: Represents a rental lease. Has property_id, start_date, end_date, status.
> Used by leases module. Relevant to maintenance because work orders are tied to properties,
> not leases. We might extend LeaseModel or create separate WorkOrderModel.

### Model 2: [Name]
[Repeat structure]

---

## Existing Components

[Describe React/Vue components in the design system that can be reused]

### Component 1: [Name]
- **Location**: [core/ui or features/...]
- **Purpose**: [What problem does it solve?]
- **Usage**: [How to use it]
- **Extensibility**: [Can be extended or must be reused as-is?]

Example:
> **MediaUpload** (core/ui): Lets users select and upload images.
> Perfect for technicians attaching photos of maintenance work.
> It handles compression, stores to the files service.
> Can be extended with maintenance-specific handlers.

### Component 2: [Name]
[Repeat structure]

---

## Event Catalog

[Events published in domains related to this module]

### Events Already Published

#### Event 1: [name]
- **Published by**: [module name]
- **When**: [What triggers it?]
- **Payload**: [What data does it contain?]
- **Your module should**: [Listen / Ignore / Publish similar]

Example:
> **lease.terminated** (published by leases module)
> Fired when a lease ends. Contains lease_id, end_date.
> Maintenance module should listen and mark pending work orders as closed.

#### Event 2: [name]
[Repeat structure]

### Events Your Module Will Need to Publish

[These are design decisions from Phase 2, but note them here]

Example:
> - work_order.assigned: When PM assigns work to technician
> - work_order.completed: When technician marks work complete
> - work_order.cancelled: When work order is cancelled

---

## Core Services

[Existing services in the core layer that this module can use]

### Service 1: [Name]
- **Location**: [app.core.X]
- **Purpose**: [What does it provide?]
- **Methods**: [Main methods]
- **Your module can**: [How you'll use it]

Example:
> **notifications service** provides push alerts.
> Methods: send(user_id, message, action_url)
> Maintenance module can use it: notify technician when work assigned.

### Service 2: [Name]
[Repeat structure]

---

## Gaps (What's Missing)

[What models, components, events, services will be entirely new in this module?]

### New Models
- [ ] [ModelName]: [Purpose, key fields]
- [ ] [ModelName]: [Purpose, key fields]

Example:
> - WorkOrderModel: Represents a maintenance task. Fields: property_id, urgency, status, assignee, description
> - TechnicianAssignment: Links technician to work order. Fields: work_order_id, technician_id, assigned_at

### New Components
- [ ] [ComponentName]: [Purpose]
- [ ] [ComponentName]: [Purpose]

### New Events
- [ ] [Event name]: [When triggered?]
- [ ] [Event name]: [When triggered?]

### New Services
- [ ] [Service name]: [What does it provide?]

### Decisions Needed
- [ ] Should work orders be tied to properties or leases? (Impacts schema)
- [ ] Should we reuse assignment logic from [other module] or build custom?
- [ ] Where do work order photos get stored? (files service or custom?)

---

## Anti-Patterns Detected

[Name anti-patterns explicitly. See discover-codebase/reference/anti-patterns.md]

### Anti-Pattern 1: Model Blindness [CLEAR / POTENTIAL / NOT APPLICABLE]

**Finding**:
[Description of potential duplication or extension opportunity]

Example:
> POTENTIAL ISSUE: LeaseAmendmentModel in leases module tracks changes to leases.
> WorkOrderModel will track changes to work orders.
> Question: Should we extend LeaseAmendment for both, or separate models?

### Anti-Pattern 2: Island Components [CLEAR / POTENTIAL / NOT APPLICABLE]

**Finding**:
[Description of custom component vs design system]

Example:
> CLEAR: MediaUpload in core/ui already handles image compression and storage.
> Don't build custom WorkOrderPhotoUpload component.

### Anti-Pattern 3: Pub/Sub Bypass [CLEAR / POTENTIAL / NOT APPLICABLE]

**Finding**:
[Description of direct imports vs events]

Example:
> POTENTIAL ISSUE: sync logic might query technician table directly.
> Should listen to technician.online events instead.

### Anti-Pattern 4: UX Amnesia [CLEAR / POTENTIAL / NOT APPLICABLE]

**Finding**:
[Description of design that doesn't match user's actual context]

Example:
> NOT APPLICABLE: Design concept clearly emphasizes field technician (mobile, offline, field).
> This will shape interface design properly.

---

## Archaeology Notes

[Miscellaneous findings from code exploration]

- The project uses SQLAlchemy for models (consistent ORM)
- React with hooks is the pattern (match this)
- Events are pub/sub with centralized event bus (use it)
- Core services imported from app.core.* (follow this pattern)
- Models use id (string UUID), created_at, updated_at consistently

---

## Decisions for Next Phase

[What needs to be decided in Phase 2 (Design)?]

- [ ] Should work orders be tied to properties or leases?
- [ ] Can we extend [ExistingModel] or do we need new model?
- [ ] Which design system components should we use vs extend?
- [ ] What are the 3 interface alternatives worth exploring?

---

## Next Steps

1. Review this architecture map
2. Verify your understanding matches findings
3. Note any corrections or additions
4. Clear context: `/clear`
5. Move to Phase 2: `/phase-2-design <module-name>`

---

**Document Version**: 1.0  
**Created by**: discover-codebase skill  
**Reviewed by**: [Your name/approval]
