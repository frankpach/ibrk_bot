---
name: 120-architecture
description: Architecture discovery phase - map existing models, components, events, and core services. Produces an architecture map document.
model: haiku
allowed-tools: Read Grep Glob Bash
argument-hint: [module-name]
---

# Phase 1: Architecture — Map What Exists

## Purpose

Explore the **existing codebase** to understand what models, components, events, and services already exist. This prevents:
- Duplicating models that already exist 80%
- Building custom components when the design system already has them
- Bypassing pub/sub when events already exist
- Missing opportunities to reuse core services

**Output**: An architecture map that describes the landscape and identifies gaps.

## Future Development Capture

If architecture discovery finds reusable opportunities, deferred refactors, or
future modules outside the active scope, record the detailed finding in
`.claude/dev-future/<module-or-system>/`. Promote a concise summary to
`docs/06-roadmap/` only when it affects platform direction or module sequencing.

## Pre-Phase Gate (MANDATORY)

Before starting:
1. Run `/state-validator 120-architecture` — must PASS before proceeding
2. Read `.claude/current-dev-issues/.state/project-map.yaml` → confirm `phase_0.status: complete`
3. Read `.claude/current-dev-issues/.state/current-objective.md` → confirm Phase 1 is the goal

## Prerequisites

- `/state-validator 120-architecture` passes
- Phase 0 complete: both artifacts exist at `docs/dev/artifacts/<module-name>/01-design-concept.md` and `02-persona-journey.md`
- Fresh context (user has cleared it)

## Process

### Step 1: Invoke discover-codebase

```
/discover-codebase <module-name>
```

The skill will:
1. Read the design concept from Phase 0
2. Automatically explore `/docs` (visión, stack, modules)
3. Search the codebase for:
   - Relevant SQLAlchemy models
   - React components in the design system
   - Events in the event bus
   - Core services available
4. Produce an architecture map

### Step 2: Review the Map

The output will be a prose description (not a table) like:

```
The leases module has LeaseModel representing a lease contract. 
The properties module has PropertyModel for real estate. 
Both can have maintenance work orders tied to them. 

Core services available: notifications (to alert PMs), tasks (for scheduling), 
audit (to log changes). 

Events in the event bus: lease.expires_soon, lease.terminated, payment.overdue.

No existing work order or maintenance system — this module will be new.
```

**Don't just scan it** — really understand:
- What models exist that relate to your domain?
- What components can you reuse?
- What events are already being published?
- What core services can you delegate to?

### Step 3: Identify Gaps

The map highlights what's **missing**:
- A new model you need to create
- A new component type not yet built
- A new event category not yet published
- A new service responsibility

These gaps become part of the design in Phase 2.

## Output Artifacts (3 required)

After archaeology, produce ALL THREE artifacts using `formats-complete.md` as format reference:

**Artifact 1** — Architecture Map:
```
docs/dev/artifacts/<module-name>/03-architecture-map.md
```
Format: see `.claude/commands/artifacts-template/03-architecture-map-TEMPLATE.md`

**Artifact 2** — Constraints:
```
docs/dev/artifacts/<module-name>/04-constraints.md
```
Format: see `.claude/commands/artifacts-template/04-constraints-TEMPLATE.md`
Populate: Module-Specific Constraints + Module Dependencies sections from what was discovered.

**Artifact 3** — Why Decisions (via /context-promoter):
```
docs/dev/artifacts/<module-name>/05-why-decisions.md
```
After writing artifacts 1-2, invoke `/context-promoter target:decisions` to extract decisions from this session into `05-why-decisions.md`.
Format: see `.claude/commands/artifacts-template/05-why-decisions-TEMPLATE.md`

## Post-Phase State Update (MANDATORY)

After all 3 artifacts are saved, update `.state/`:

1. **project-map.yaml**:
   - `phase_1.status: complete`
   - `phase_1.completed_at: <ISO8601>`
   - `phase_1.artifacts: [path/03-architecture-map.md, path/04-constraints.md, path/05-why-decisions.md]`
   - `code_index: <populated from discovered models, components, events, services>`
   - `next_action.phase: 2`

2. **code-index.yaml**: populate from architecture map findings

3. **constraints.md**: append module-specific constraints from artifact 04

4. **module-registry.md**: populate related modules table from `backend/config/modules.json`

5. **decisions.md**: append decisions from artifact 05

6. **current-objective.md**: update to Phase 2

## Detection of Anti-Patterns

While exploring, the skill will flag:

### Anti-Pattern 1: Model Blindness
> "I notice LeaseAmendment table exists. Your module needs to track lease changes. Should you extend LeaseAmendment or create a new table?"

**Action**: Decide whether to reuse or extend existing models.

### Anti-Pattern 2: Island Components
> "I see MediaPicker is available in core/ui. Your module needs file upload. Reuse it."

**Action**: Plan to use core/ui components instead of building new ones.

### Anti-Pattern 3: Pub/Sub Bypass
> "The events module publishes lease.expired. Should your module listen instead of polling?"

**Action**: Prefer events over direct database queries.

## After Architecture Discovery

1. **Copy the artifact path**: `/docs/dev/artifacts/<module-name>/02-architecture-map.md`
2. **Review for risks**: Does the map reveal anything that changes your design?
3. **Clear context**: `/clear` (manually)
4. **Move to Phase 2**: Invoke `/130-design <module-name>`

Pass the architecture map when prompted in Phase 2.

## Rules

- **No guessing**: The skill reads actual code. Trust its findings.
- **Archaeology, not invention**: This phase is about understanding, not designing.
- **Ask clarifying questions**: If the map is unclear, ask the skill to elaborate.

## Context Management

**Before starting**: Fresh context after Phase 0 clear

**During Phase 1**:
- Skill does the exploration (uses grep, reads files)
- You review the output
- Typical: 15-20k tokens

**After Phase 1**:
- Manual context clear (user runs `/clear`)
- Next phase starts fresh

## Time Budget

- **Min**: 10 minutes (simple feature)
- **Typical**: 15-20 minutes (most modules)
- **Max**: 30 minutes (complex domain with many dependencies)

## Next Phase

```
/130-design <module-name>
```

You'll propose 2-3 interface alternatives based on this architecture map.
