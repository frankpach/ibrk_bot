# UX Considerations — The User is First

When proposing interface alternatives in Phase 2, always consider the actual user and their context. This document guides you through thinking about UX.

## The UX-First Principle

**Bad UX design process**: 
1. Start with the data model
2. Design an interface to expose it
3. Hope users can figure it out

**Good UX design process**:
1. Start with the user and their context
2. Design an interface for that context
3. Make the data model fit

**The difference**: One is technically elegant. One is usable.

---

## Key Dimensions of Context

For each user, understand these dimensions:

### 1. Device
- **Desktop** (1920x1080+, mouse/keyboard, 1-2m away)
  - Large text OK
  - Precise mouse clicks OK
  - Complex layouts OK
  - Focus: power user efficiency

- **Tablet** (1024x768, touch, 1m away)
  - Medium text required
  - Touch targets: 44x44px minimum
  - Slightly complex layouts OK
  - Focus: touch-friendly power users

- **Mobile** (375x812, touch, 30cm away)
  - Large text required
  - Touch targets: 48x48px minimum
  - Simple, linear layouts only
  - Focus: speed and simplicity

### 2. Environment
- **Office** (stationary, good lighting, focused time)
  - Desktop workflow
  - Can read dense tables
  - Can follow multi-step processes
  - Focus: efficiency, accuracy

- **Outdoor** (moving, variable lighting, weather)
  - Mobile workflow
  - Need high contrast
  - Can't see small text in sunlight
  - Focus: speed, visibility

- **Vehicle** (moving, distracted, limited attention)
  - Mobile workflow
  - Very simple
  - Can only use one hand
  - Focus: voice input, large buttons

### 3. Biggest Constraint
For each user type, what's their limiting factor?

- **Field technician**: Battery life, connectivity, time (work to complete before sun sets)
- **Office manager**: Time (hundreds of items to review), data density (want to see a lot)
- **Executive**: Attention (5 minutes max), key metrics only
- **Customer**: Simplicity (don't know the system)

Optimize for the constraint.

---

## Example: Work Order Management

### WRONG: One Design Fits All
```
Work Order Detail (Desktop View)
┌──────────────────────────────────────────┐
│ Work Order #123                          │
│ Property: 123 Main St                    │
│ Assignee: John Smith                     │
│ Status: assigned                         │
│ Urgency: high                            │
│ Created: 2024-04-29 08:00 UTC           │
│ Updated: 2024-04-29 08:15 UTC           │
│ Description: [long text]                 │
│ Notes: [empty]                           │
│ Photos: [0 attached]                     │
│ [Save] [Cancel]                          │
└──────────────────────────────────────────┘

This works for a manager at a desk.
But a field technician:
  - Can't see it on phone (too wide)
  - Can't tap the buttons (too small)
  - Doesn't have time for all this scrolling
  - Doesn't have connectivity to upload photos
```

### RIGHT: Design for Each User

**Technician on Mobile (Field, Time Constraint)**:
```
┌─────────────────────┐
│ 123 Main St         │
│ URGENT              │
│ Filter replaced     │
│ [START WORK]        │ ← Big button, one tap
└─────────────────────┘

(Offline, locally stored)
When online, sync happens in background.
```

**Manager on Desktop (Office, Density Constraint)**:
```
┌────────────────────────────────────────────────┐
│ ID   Address         Status  Urgency  Assigned │
│ 123  123 Main St     started high     J.Smith  │
│ 124  456 Oak Ave     assigned high    M.Chen   │
│ 125  789 Pine Ln     completed med    J.Smith  │
│ [View Details] [Reassign] [Archive]          │
└────────────────────────────────────────────────┘

(Desktop, lots of data, can review 100 items)
```

**Executive on Tablet (Office, Attention Constraint)**:
```
┌──────────────────────┐
│ Today's Summary      │
│ 12 Started           │
│ 8 Completed         │
│ Avg time: 2.5 hours  │
│ On track: ✓          │
└──────────────────────┘

(Key metrics, 30 seconds to understand)
```

---

## Device-Specific Patterns

### Mobile-First Patterns

**For field technicians**:
1. **Offline-first**: Data syncs when online
2. **Simple linear flow**: One action per screen
3. **Large touch targets**: 48px minimum
4. **Voice input**: Hands might be full
5. **Battery-conscious**: Minimize location tracking, notifications
6. **High contrast**: Works in sunlight

**Example workflow**:
```
Screen 1: List of assigned work orders
  - Scroll to find one
  - Tap to open

Screen 2: Work order detail
  - [START WORK] button fills screen
  
Screen 3: In progress
  - [TAKE PHOTO] button
  - [ADD NOTE] button
  - [COMPLETE] button
  - Each is full-width, easy to tap
```

### Desktop-First Patterns

**For office managers**:
1. **Online always**: Assume good connectivity
2. **Data density**: Show lots of info at once
3. **Power user shortcuts**: Keyboard navigation, bulk actions
4. **Precision input**: Small click targets OK
5. **Multi-tasking**: Keep windows side-by-side
6. **Typography**: Can read small text

**Example layout**:
```
Left sidebar: Filter & search
Center: Table of work orders
Right sidebar: Detail view of selected item

Can review 50 items in 10 minutes.
```

---

## The Three Questions (Before You Design)

Ask these for each user persona:

### Question 1: What's the Primary Goal?
- Technician: "Complete work and record completion"
- Manager: "Dispatch work and track progress"
- Executive: "Understand if we're on track"

Design the interface around THAT goal. Everything else is secondary.

### Question 2: What's the Environment?
- Technician: Mobile, field, moving between properties
- Manager: Desktop, office, stationary
- Executive: Tablet, meetings, 5 minutes at a time

Optimize for that environment.

### Question 3: What's the Time Constraint?
- Technician: "I have 30 min for this work order, then move to the next"
- Manager: "I have 2 hours to dispatch 50 work orders"
- Executive: "I have 5 minutes to check status"

This determines how much data they can review and how complex the interface can be.

---

## Red Flags: UX Problems

If you design something and see these flags, rethink it:

### Flag 1: It Doesn't Work Offline
> "What if the technician loses connectivity?"

If the answer is "the app doesn't work", that's a problem for field users.
Build offline-first.

### Flag 2: It Requires Small, Precise Touches
> "On a phone screen, this button would be 20x20 pixels"

Phones require 48x48px touch targets minimum.
If you can't hit that on mobile, the design doesn't work for mobile users.

### Flag 3: It Shows More than the User Can Understand
> "The manager sees 50 fields and doesn't know which matter"

Data overload is UX failure.
Show what matters first, let them drill down for details.

### Flag 4: It Requires Steps the User Doesn't Have Time For
> "The technician has 30 minutes for the work order, but the form takes 10 minutes to fill out"

If the process takes too long, users will skip steps.
Streamline the critical path.

### Flag 5: It's Inconsistent Across Devices
> "On desktop you press Save, on mobile you press OK"

Users shouldn't have to learn a different interface for each device.
Find a consistent metaphor.

---

## Persona-Based Design

### Persona 1: Field Technician
- **Device**: Mobile (on the job)
- **Environment**: Outdoors, moving between locations
- **Goal**: Complete work order quickly and accurately
- **Biggest constraint**: Time (need to finish before dark)
- **Connectivity**: Spotty (relies on offline)
- **Input method**: Touch (sometimes one-handed)

**Design for them**:
- Offline-first sync
- Simple linear workflows
- Large touch targets
- Voice input support
- Battery-efficient
- High contrast for outdoor visibility

### Persona 2: Office Manager / Dispatcher
- **Device**: Desktop (in office)
- **Environment**: Office, stationary
- **Goal**: Assign work, monitor progress, handle exceptions
- **Biggest constraint**: Volume (50+ work orders to manage)
- **Connectivity**: Always online
- **Input method**: Mouse/keyboard

**Design for them**:
- Data-dense display
- Bulk actions
- Quick filtering/search
- Keyboard shortcuts
- Can show complex relationships

### Persona 3: Executive / Owner
- **Device**: Tablet or phone (on the go)
- **Environment**: Office or meetings
- **Goal**: Understand health of operations
- **Biggest constraint**: Attention (5 minutes max)
- **Connectivity**: Always online
- **Input method**: Touch

**Design for them**:
- Key metrics only
- Clear at a glance
- No drilldown needed
- Simple visuals (numbers, status badges)

---

## Anti-Pattern: UX Amnesia

**You have UX Amnesia if**:
- The design concept describes a field technician, but the interface is a desktop form
- The design concept emphasizes offline use, but the interface requires connectivity
- The design concept emphasizes speed, but the interface requires 10 clicks
- You never mention the user or their device in the interface description

**You're avoiding UX Amnesia if**:
- Each alternative explicitly describes "this is optimized for [user] on [device] with [constraint]"
- You explain why the design fits the user's context
- You acknowledge trade-offs: "This alternative is great for [user A] but bad for [user B]"

---

## Device-Specific Checklist

### Mobile Checklist
- [ ] Works offline (data syncs when connected)
- [ ] Touch targets minimum 48x48px
- [ ] Linear workflows (one action per screen)
- [ ] Large, readable text
- [ ] High contrast (works in bright sunlight)
- [ ] Minimal data entry (pre-fill when possible)
- [ ] Voice input for hands-free operation (if applicable)

### Tablet Checklist
- [ ] Touch targets minimum 44x44px
- [ ] Medium complexity layouts (2-column is OK)
- [ ] Readable text at arm's length
- [ ] Works with or without keyboard/mouse
- [ ] Landscape and portrait orientations

### Desktop Checklist
- [ ] Can display 100+ items (tables with pagination/scroll)
- [ ] Precise mouse clicks supported
- [ ] Keyboard shortcuts for power users
- [ ] Can show related data side-by-side
- [ ] Small text is acceptable if needed

---

## Example: Comparing Alternatives on UX

### Alternative A: Depth-First
**Good for**: Office manager, desktop, wants all controls in one place
**Bad for**: Field technician, mobile, offline, time constraint

### Alternative B: User-First
**Good for**: Everyone (each gets an interface for their context)
**Bad for**: More code to maintain, risk of inconsistency

### Alternative C: Reusability-First
**Good for**: Building a platform, enables multiple modules to use same patterns
**Bad for**: More abstraction, harder to learn initially

**On UX specifically**:
- A is device-agnostic → doesn't optimize for any device
- B is device-specific → optimizes for each device
- C is architecture-first → UX is secondary

Choose B if UX is the priority (it usually should be).

---

## The Golden Rule

> When in doubt, optimize for the primary user.

For a maintenance module, the primary user is the field technician (that's who delivers value). So:
- Optimize for mobile
- Optimize for offline
- Optimize for speed
- Optimize for the technician's workflow

Everything else is secondary.
