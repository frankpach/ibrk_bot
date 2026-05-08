---
name: generate-afk-prompt
description: Generate and save AFK prompt for next issue from .claude/current-dev-issues into timestamped file
model: haiku
allowed-tools: Read Grep Glob Bash Write
---

# Generate AFK Prompt

## Purpose

Read the next open issue from `.claude/current-dev-issues/`, generate a complete AFK (Automated, Fully Known) prompt, and save it to a timestamped file in the same directory.

If a prompt already exists, replace it with the new one.

## Process

1. **Find next open issue** from `.claude/current-dev-issues/*.md`
2. **Extract issue metadata**: objective, scope, acceptance criteria, blockers
3. **Read recent context**: Last 5 commits, git status
4. **Build prompt** with:
   - Issue content
   - Operating rules (TDD, contracts, validation gates)
   - Stop condition (<promise>NO MORE TASKS</promise>)
   - Execution instructions
5. **Save prompt** to `.claude/current-dev-issues/PROMPT-{timestamp}.md`
6. **Replace old prompt** if it exists (same directory)

## Input

None (reads from `.claude/current-dev-issues/`)

## Output

File: `.claude/current-dev-issues/PROMPT-{YYYYMMDD-HHMMSS}.md`

Contains:
- Complete AFK prompt ready to paste into Claude Code
- Issue reference
- All context (commits, rules, contracts)
- Timestamp for uniqueness

## Usage

```bash
/generate-afk-prompt
```

Then:
```bash
cat .claude/current-dev-issues/PROMPT-*.md | claude code --mode=print
```

Or copy the content and paste into Claude Code CLI.

## Rules

1. Find FIRST open issue (not in done/)
2. Extract full issue content
3. Include all operating rules
4. Generate unique filename with timestamp
5. Replace old PROMPT files
6. Do NOT generate prompt if no issues remain
