---
name: 310-retrospective
description: Retrospective phase - extract process lessons and promote reusable improvements.
model: sonnet
allowed-tools: Read Grep Glob Bash Write
argument-hint: <sprint-name>
---

# Phase 10: Retrospective

Reflect on the sprint and improve the system.

## Context Budget

Read only:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `docs/dev/artifacts/<module>/` summaries for completed modules
5. `.claude/project-memory/known-risks.md`
6. `.claude/project-memory/code-patterns.md`
7. quality and review reports

Do not load all issue files unless diagnosing a repeated execution failure.

## Process

1. Gather sprint metrics from artifacts and state summaries.
2. Identify what reduced tokens, what increased tokens, and where context was
   overloaded.
3. Identify workflow, skill, docs, and memory improvements.
4. Write `docs/dev/artifacts/_retro/<sprint>/retro-report.md`.
5. Promote reusable process lessons to:
   - `.claude/project-memory/known-risks.md`
   - `.claude/project-memory/code-patterns.md`
   - `docs/dev/project-memory.md`
6. If process files need changes, create a small follow-up issue or run
   `/020-quick-task`.

## Output

- sprint retro report;
- promoted process lessons;
- concrete next workflow/system improvements;
- token-efficiency findings.
