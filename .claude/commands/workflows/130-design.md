---
name: 130-design
description: Design phase - propose interface alternatives and choose the best one. Produces an interface design document.
model: sonnet
allowed-tools: Read Grep Glob
argument-hint: [module-name]
---

# Phase 2: Design — Propose & Choose Interfaces

## Purpose

Take the architecture map from Phase 1 and propose **2-3 radically different interface alternatives**, then choose one based on your design philosophy.

**Output**: An interface design that describes the primary contract, key workflows, and trade-offs made.

## Future Development Capture

When an interface alternative is rejected but may matter later, store the detailed
variant in `.claude/dev-future/<module-or-system>/`. Keep the active design artifact
focused on the chosen direction. Promote to `docs/06-roadmap/` only when the
rejected alternative becomes a stable future roadmap item.

## Prerequisites

- Phase 0 (Discovery) is complete
- Phase 1 (Architecture) is complete
- Design concept saved to `/docs/dev/artifacts/<module-name>/01-design-concept.md`
- Architecture map saved to `/docs/dev/artifacts/<module-name>/02-architecture-map.md`
- Fresh context (user has cleared it)

## Process

### Step 1: Invoke design-interface

```
/design-interface <module-name>
```

The skill will:
1. Read the design concept from Phase 0
2. Read the architecture map from Phase 1
3. Understand existing components, models, events, and services
4. Propose 2-3 radically different interface alternatives:
   - **Alternative A**: Depth-first (minimal surface, maximum behavior)
   - **Alternative B**: User-first (matches real workflows, device-aware)
   - **Alternative C**: Reusability-first (composable, extensible by other modules)
5. Present trade-offs for each
6. Give its recommendation with explicit reasoning

### Step 2: Choose One

The skill will ask:
> "Which alternative resonates with you? (A/B/C) Or would you like a hybrid?"

**Respond with**:
- A single letter (A, B, or C)
- Reason for your choice
- Any adjustments you want to make

The skill does NOT advance until you've chosen. This decision shapes the entire remaining plan.

### Step 3: Review the Chosen Design

The skill will produce a design document describing:
- The chosen interface in prose (not pseudocode)
- Key methods/endpoints
- Major workflows (the 2-3 paths users will take)
- Components that must be built or extended
- Where this fits in the architecture

**Don't just skim it** — really understand:
- Can a developer execute this without coming back to ask "what did you mean?"
- Does it match your mental model from Phase 0?
- Are the trade-offs you chose worth the benefits?

## Output Artifact

Skill automatically saves to:

```
/docs/dev/artifacts/<module-name>/03-interface-design.md
```

**Format**:
```markdown
# Interface Design: <Module Name>

## Chosen Alternative
[Which of the 3, and why]

## Primary Interface
[Description of the main contract]

## Key Workflows
1. [First critical user journey]
2. [Second critical user journey]
3. [Third critical user journey]

## Components to Build
- [Component A]
- [Component B]

## Components to Reuse/Extend
- [Design system component X]
- [Service Y]

## Events to Publish
- [Event name]: [when triggered]

## Events to Consume
- [Event name]: [what it triggers]

## Trade-offs Made
- [What you're optimizing for]
- [What you're sacrificing]
- [Why this is the right choice]
```

## Anti-Pattern: Interface Inflation

While the skill proposes interfaces, watch for:

> "You've proposed 12 different entry points. That's overengineering. Can 80% of users accomplish their goals with 3?"

**Action**: Prefer simplicity. Deep is better than broad.

## After Design

1. **Copy the artifact path**: `/docs/dev/artifacts/<module-name>/03-interface-design.md`
2. **Review the trade-offs**: Does the design you chose align with the problem you defined in Phase 0?
3. **Clear context**: `/clear` (manually)
4. **Move to Phase 3**: Invoke `/140-requirements <module-name>`

Pass the interface design when prompted in Phase 3.

## Rules

- **Your choice matters**: This interface is your commitment. Once chosen, issues will be built to this spec.
- **Don't design by committee**: You pick one. The team will implement it.
- **Defend the trade-offs**: If you choose A because it's "simpler," be ready to hear that C would have been more reusable.

## Context Management

**Before starting**: Fresh context after Phase 1 clear

**During Phase 2**:
- Skill does the exploration and proposal (uses models from Phase 1 output)
- You choose an interface
- Typical: 15-20k tokens

**After Phase 2**:
- Manual context clear (user runs `/clear`)
- Next phase starts fresh

## Time Budget

- **Min**: 10 minutes (one clear alternative)
- **Typical**: 20 minutes (3 alternatives, thoughtful choice)
- **Max**: 30 minutes (complex design with difficult trade-offs)

## Next Phase

```
/140-requirements <module-name>
```

You'll define the PRD and acceptance criteria based on this interface design.
