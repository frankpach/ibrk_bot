# Design Concept: [Module Name]

**Status**: ✓ Complete  
**Date**: [Date]  
**Module**: [module-name]  

---

## Problem Statement

[What problem does this module solve? From the user/stakeholder perspective.]

Example:
> "Field technicians spend 2 hours per day traveling between properties, waiting to hear what work they should do next. The leases module can't handle maintenance requests, so PMs spend time on phone calls coordinating. There's no way to track if maintenance work is actually done."

---

## Solution

[What will be built to solve this problem?]

Example:
> "A maintenance module that lets PMs create and assign work orders to technicians. Technicians can see assigned work on their phone, update status as they work, and attach photos. Work order status syncs back to PMs automatically."

---

## Key Personas

### Persona 1: [Name/Role]
- **Who**: [Description]
- **Device**: [Mobile/Desktop/Tablet]
- **Environment**: [Office/Field/Vehicle/etc]
- **Goal**: [What do they want to accomplish?]
- **Biggest constraint**: [Time/Attention/Bandwidth/Connectivity/etc]

Example:
> **Field Technician (Maria)**
> - Moves between 5-10 properties per day
> - Uses iPhone, spotty 4G connectivity
> - Needs to complete work before sun sets
> - Goal: See what work to do, complete it, confirm completion
> - Biggest constraint: Time (2 hours per work order max)

### Persona 2: [Name/Role]
[Repeat structure]

### Persona 3: [Name/Role]
[Repeat structure]

---

## Constraints

### Timeline
- **Due date**: [Date]
- **Estimated effort**: [2 weeks / 1 month / etc]
- **Blocking issues**: [What depends on this module?]

Example:
> Due end of Q2. Property team needs this before they can launch the new "maintenance included" lease tier.

### Technical
- **Architecture**: [REST API / GraphQL / WebSockets / etc]
- **Database**: [New tables? Extensions? Migrations?]
- **Frontend framework**: [React / Vue / etc]
- **External dependencies**: [APIs, third-party services]

Example:
> - Backend: FastAPI, SQLAlchemy models
> - Frontend: React hooks, TypeScript
> - External: Twilio for SMS alerts (already available)

### Business
- **Budget**: [If applicable]
- **Compliance**: [GDPR, HIPAA, PCI, etc]
- **Success metrics**: [How will we know this is successful?]

Example:
> - Success: 80% of technicians sync work orders within 5 min of assignment
> - Compliance: All work order data at rest is encrypted (per property data agreement)

---

## Scope: In vs Out

### In Scope
- Field technician can view assigned work orders
- Field technician can update status (started, completed, on_hold)
- Field technician can attach photos and notes
- PM can create and assign work orders
- PM can see real-time status of all work orders
- Offline sync (works when connectivity is spotty)
- Push notifications when assigned

### Out of Scope
- Scheduling or forecasting (future feature)
- Integration with accounting system (future feature)
- Mobile app for iOS/Android (uses web app, not native)
- Historical reporting (future feature)
- Customer-facing notifications (out of scope for maintenance module)

**Why out of scope?**
> We're starting with the MVP: create, assign, complete. Analytics and deeper integrations can be added later once we validate the core workflow.

---

## Open Questions

- [ ] Should work order be tied to a property or a lease?
  - *Implication*: Determines database model, could affect how we display related leases
- [ ] Who can create work orders? Only PMs or also property managers?
  - *Implication*: Affects access control and API design
- [ ] What happens if a technician is offline when a work order is assigned?
  - *Implication*: Determines sync strategy, notification timing
- [ ] Should we send SMS alerts or just in-app notifications?
  - *Implication*: Affects Twilio usage, phone number management

---

## Assumptions

**If you don't have an answer to a question, note it as an assumption:**

- [ ] Assumption: Work orders are tied to properties, not leases
  - *To verify*: Ask property team what's most useful
- [ ] Assumption: Only PMs can create work orders (not property managers)
  - *To verify*: Confirm with stakeholder
- [ ] Assumption: Technicians always have a phone (iPhone/Android)
  - *To verify*: Check tech requirements in field team survey
- [ ] Assumption: Push notifications go via browser (not SMS)
  - *To verify*: Cost vs user preference

---

## Success Criteria

How will we know this module is successful?

- [ ] **Adoption**: 80% of technicians using the app within 2 weeks
- [ ] **Speed**: Work order status updates within 5 minutes of completion
- [ ] **Accuracy**: 95% of work orders marked complete match physical reality
- [ ] **Reliability**: < 1% of offline sync failures requiring manual intervention
- [ ] **User satisfaction**: NPS > 40 from field team

---

## Related Modules

- **Leases**: Work orders may reference leases. Can we query lease data?
- **Notifications**: Send alerts when work assigned. Use notifications module?
- **Files**: Store work order photos. Use files service?
- **Audit**: Log all work order changes for compliance. Use audit service?

---

## Next Steps

1. Validate assumptions with stakeholders (check questions above)
2. Clear context
3. Phase 1: `/phase-1-architecture maintenance` → explore existing code
4. Phase 2: `/phase-2-design maintenance` → design interface
5. Continue through phases...

---

## Sign-Off

| Role | Name | Date | Sign-Off |
|------|------|------|----------|
| Product Manager | [Name] | [Date] | ✓ |
| Engineering Lead | [Name] | [Date] | ✓ |
| Field Operations | [Name] | [Date] | ✓ |

---

**Document Version**: 1.0  
**Last Updated**: [Date]  
**Approved**: ✓ Yes / ⚠️ Needs revision
