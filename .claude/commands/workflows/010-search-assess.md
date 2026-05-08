---
name: 010-search-assess
description: Lightweight code archaeology, reuse search, and impact assessment without implementation.
model: haiku
allowed-tools: Read Grep Glob Bash
argument-hint: <feature-domain-or-question>
---

# Search And Assess

Use this for read-only investigation, reuse decisions, and impact analysis.

## Context Budget

Load at most:

1. `.claude/commands/SYSTEM_CONTRACT.md`
2. `.claude/commands/registry.yaml`
3. this workflow
4. `.claude/project-memory/module-map.md`
5. `.claude/project-memory/code-patterns.md` when reuse is relevant
6. targeted source files found by search

Do not load full `docs/` or runtime state unless the question is about active module
execution.

## Process

1. Convert the request into 3-6 search terms.
2. Search code, docs, and project memory for matching models, services, events,
   components, workflows, and tests.
3. Classify each candidate as REUSE, EXTEND, REFACTOR, or NEW.
4. Identify impacted files and validation commands.
5. Stop before implementation.

## Escalation

Escalate to the full pipeline if the assessment shows a new module, major feature,
cross-layer contract, or ambiguous product decision.

## Output

Return:

- search terms used;
- relevant findings with paths;
- reuse decision;
- impact/risk;
- recommended next workflow.
