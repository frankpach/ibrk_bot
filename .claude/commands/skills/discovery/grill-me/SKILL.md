---
name: grill-me
description: Discovery phase - interview the user about requirements until shared understanding is reached. Produces 2 artifacts (design-concept + persona-journey) and updates .state/.
model: sonnet
allowed-tools: Read Grep Glob Write
argument-hint: [module-name]
---

# Grill Me — Reach Shared Understanding

Interview the user relentlessly about what they want to build until both parties have shared understanding.

This skill is invoked in Phase 0 (Discovery).

## Input

A brief description of what the user wants to build:
- Slack message, email, meeting notes
- Vague idea ("add material requests to work orders")
- Feature request from feedback

## Output (2 artifacts — both required)

**Artifact 1** — Design Concept:
```
docs/dev/artifacts/<module-name>/01-design-concept.md
```
Format: see `artifacts-template/01-design-concept-TEMPLATE.md` and `artifacts-template/formats-complete.md`

Sections: problem statement, solution outline, key personas, constraints (timeline/technical/business), scope (in/out), open questions, assumptions.

**Artifact 2** — Persona Journey:
```
docs/dev/artifacts/<module-name>/02-persona-journey.md
```
Format: see `artifacts-template/02-persona-journey-TEMPLATE.md` and `artifacts-template/formats-complete.md`

Sections: one journey per persona (steps, emotional state, pain, opportunity), journey intersections, critical flows.

## Process

1. **Read .state/** (if exists):
   - `.claude/current-dev-issues/.state/project-map.yaml` — check if phase_0 already started
   - `.claude/current-dev-issues/.state/current-objective.md` — confirm Phase 0 is current goal

2. **Ask clarifying questions** (one at a time) about:
   - The problem being solved (WHY)
   - Who the users are — personas, devices, environments, goals, constraints (WHO)
   - Success criteria (how will users know it works?)
   - Constraints: timeline, technical, business
   - Integration with existing modules
   - Scope: what is explicitly OUT

3. **For each persona discovered**, ask specifically:
   - What device and environment do they use?
   - Walk me through their journey step by step
   - Where does the current process break down?
   - What does "done" look like for them?

4. **User answers** (or says "I don't know" — record as assumption)

5. **Record assumptions** explicitly

6. **Stop when aligned** — both agree on scope, direction, and personas

7. **Write both artifacts** using `formats-complete.md` format conventions

## State Updates (MANDATORY after artifacts are saved)

Update `.claude/current-dev-issues/.state/`:

**project-map.yaml**:
```yaml
phase_0:
  status: complete
  completed_at: <ISO8601>
  artifacts: [docs/dev/artifacts/<module>/01-design-concept.md, .../02-persona-journey.md]
personas: [<list from design concept — name, device, environment, goal, constraint>]
constraints:
  timeline: <from design concept>
open_questions: [<list>]
assumptions: [<list>]
next_action:
  phase: 1
  goal: "Run Phase 1 architecture discovery"
```

**current-objective.md**: update phase to Phase 1, next action to `/120-architecture`

## Rules

- **HITL**: Cannot be delegated to an agent
- **One question at a time**: Don't overwhelm
- **Be honest**: If you don't know, say so
- **Decisions matter**: Choices here shape the entire module design
- **No premature optimization**: Design once, code once
- **Both artifacts are mandatory**: Do not skip persona-journey

## Time Budget

- Small feature: 15 minutes
- New module: 30-45 minutes
- Complex/ambiguous: 90 minutes (or rescope it)
