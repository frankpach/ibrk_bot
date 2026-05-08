---
name: 110-discovery
description: Discovery phase - grill the user about the module/feature to reach shared understanding. Produces 2 artifacts (design-concept + persona-journey) and updates .state/.
model: sonnet
allowed-tools: Read Grep Glob Write
argument-hint: [module-name]
---

# Phase 0: Discovery — Grill for Shared Understanding

## Pre-Phase Gate (MANDATORY)

Before starting, verify state is initialized:

1. Read `.claude/current-dev-issues/.state/project-map.yaml`
   - If missing: run `/100-state-init <module-name>` first
   - If `phase_0.status` is already `complete`: confirm with user before re-running
2. Read `.claude/current-dev-issues/.state/current-objective.md`
   - Confirm objective is Phase 0

## Purpose

Reach **shared understanding** with the user about what will be built. This is HUMAN IN LOOP — the AI asks relentless questions until alignment is achieved.

**Output**: Two artifacts that capture the problem, solution, personas, journeys, constraints, and open questions.

## Future Development Capture

When discovery uncovers useful but out-of-scope ideas, write detailed notes to
`.claude/dev-future/<module-or-system>/`. Add only stable, product-facing summaries to
`docs/06-roadmap/`. Do not expand the active module scope just because a future
idea was captured.

## Prerequisites

- `/100-state-init <module-name>` already run — `.state/` exists
- Client/PM has communicated a need (Slack message, email, brief, or meeting notes)
- You have 30-45 minutes for this conversation
- You're prepared to make decisions on key questions

## Process

### Step 1: Invoke grill-me

```
/grill-me <client-brief>
```

Pass in whatever you have:
- A Slack message from the client
- An email describing the need
- A vague idea ("add gamification to the course platform")
- Meeting transcript
- Feature request from user feedback

### Step 2: Answer Questions

The AI will ask you 5-15 questions, one at a time. For each:
- **Read** the AI's recommended answer
- **Decide**: Do you agree? Disagree? Want to refine?
- **Respond** with your answer

Examples of questions you'll see:
- "What's the primary user for this feature?"
- "What problem does it solve?"
- "Are there existing patterns in the codebase we should follow?"
- "What's the timeline constraint?"
- "Should this integrate with existing modules or be standalone?"

### Step 3: Stop When Aligned

The grilling session ends when:
- Both you and the AI agree you have shared understanding
- All critical questions are answered
- You're confident about the scope and direction

**Don't prematurely stop** if you're uncertain. The investment in alignment now saves rework later.

## Output Artifacts (2 required)

After grilling session, produce BOTH artifacts using `formats-complete.md` as format reference:

**Artifact 1** — Design Concept:
```
docs/dev/artifacts/<module-name>/01-design-concept.md
```
Format: see `.claude/commands/artifacts-template/01-design-concept-TEMPLATE.md`

**Artifact 2** — Persona Journey:
```
docs/dev/artifacts/<module-name>/02-persona-journey.md
```
Format: see `.claude/commands/artifacts-template/02-persona-journey-TEMPLATE.md`

## Post-Phase State Update (MANDATORY)

After both artifacts are saved, update `.state/`:

1. **project-map.yaml**:
   - `phase_0.status: complete`
   - `phase_0.completed_at: <ISO8601>`
   - `phase_0.artifacts: [path/01-design-concept.md, path/02-persona-journey.md]`
   - `personas: [list from design concept]`
   - `constraints.timeline: <from design concept>`
   - `open_questions: [list from design concept]`
   - `assumptions: [list from design concept]`
   - `next_action.phase: 1`
   - `next_action.goal: "Run Phase 1 architecture discovery"`

2. **current-objective.md**:
   - Update Phase to `Phase 1 — Architecture`
   - Update Next Action to invoke `/120-architecture`

## After Discovery

1. Verify both artifacts saved to `docs/dev/artifacts/<module-name>/`
2. Verify `.state/project-map.yaml` updated (phase_0.status = complete)
3. **Clear context**: `/clear` (manually)
4. **Move to Phase 1**: `/120-architecture <module-name>`

## Rules

- **HITL (Human In The Loop)**: You cannot delegate this to an agent. You're the one answering questions.
- **No premature exit**: Grill until you're confident about the direction.
- **Be honest**: If you don't know the answer, say so. The AI will note it as an assumption.
- **Decisions matter**: The choices you make here shape the entire module design.

## Time Budget

- **Min**: 15 minutes (very clear brief)
- **Typical**: 30-45 minutes (most modules)
- **Max**: 90 minutes (complex or ambiguous features)

If it's taking longer, you're probably overthinking. Say "I think we're aligned" and move forward.

## Context Management

**Before starting**:
- ~40KB system prompt + brief
- Fresh context (0 tokens used)

**During Phase 0**:
- Grilling conversation grows context
- Typical: 20-40k tokens by end
- Still within smart zone ✓

**After Phase 0**:
- Manual context clear (user runs `/clear`)
- Next phase starts fresh

## Next Phase

```
/120-architecture <module-name>
```

Provide the design concept artifact path when asked.
