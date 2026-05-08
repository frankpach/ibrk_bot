# Issue [NNN]: [Title]

**Module**: module-name-slug
**Type**: AFK | HITL
**Effort**: S | M | L | XL
**Blocked by**: NNN, NNN | None
**Requires review**: false | true (HITL only)

---

## WHY — The Human Problem

[Why does this issue exist? What user pain does it solve?
Do NOT start coding until you understand this section.
The LLM must understand the human problem before designing anything.]

**User pain**: [1-2 sentences describing the frustration or gap]
**Business impact**: [What happens if this is NOT built?]
**Success signal**: [How will a user know this works? What changes for them?]

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| [Name] | [role] | mobile/desktop | field/office | [what they want to do] | [their main limitation] |
| [Name] | [role] | mobile/desktop | field/office | [what they want to do] | [their main limitation] |

**Primary user**: [Name] — design for them first.

---

## WHAT — Constraints

Rules this issue MUST follow. Non-negotiable.

**Architecture**:
- [ ] All responses via `StandardResponse` / `StandardListResponse`
- [ ] All queries filtered by `tenant_id` — no bypass
- [ ] No direct imports from other business modules (`app.modules.X` → `app.modules.Y`)
- [ ] Errors via `APIException` only — never `HTTPException`
- [ ] No business logic in route handlers (routes → services → repositories → DB)

**Module-specific rules** (from `.state/constraints.md`):
- [ ] [Module-specific constraint 1]
- [ ] [Module-specific constraint 2]

**Module context**:
- Related modules: [list modules this issue touches or depends on]
- Module registry: `.claude/current-dev-issues/.state/module-registry.md`
- Read before starting: `.claude/current-dev-issues/.state/constraints.md`

---

## HOW — Implementation Approach

[High-level approach only. Do NOT skip to this section.
Only fill this after WHY/WHO/WHAT are understood.]

**Backend**:
- [What model/table is affected]
- [What service methods to add]
- [What endpoint(s) to create]

**Frontend**:
- [What component(s) to build or extend]
- [What API calls to make]
- [What state to manage]

**Events**:
- Publishes: [event name + payload, or "none"]
- Consumes: [event name + action, or "none"]

---

## Code Search (MANDATORY before writing any code)

Run `/skills/planning/code-search [feature-description]` and verify:

- [ ] Existing models checked — document findings in `.state/code-index.yaml`
- [ ] Existing components checked — document reuse decision
- [ ] Existing services checked — document reuse decision
- [ ] Events already published checked — document if we should consume them

**Reuse decision** (fill after search):
- Reuse as-is: [list]
- Extend: [list]
- Build new: [list + justification]

---

## Reference Documents

Read these before implementing. Do NOT guess — the answers are in these files.

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `.claude/current-dev-temp/[prd-filename].md` | Acceptance criteria, edge cases |
| Spec | `.claude/current-dev-temp/[spec-filename].md` | Technical details, field definitions |
| Architecture map | `docs/dev/artifacts/[module]/03-architecture-map.md` | Existing code to reuse |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | Rules that apply |
| Project map | `.claude/current-dev-issues/.state/project-map.yaml` | Phase status, open decisions |

---

## User Stories Covered

- US-N: [Story title from PRD]
- US-N: [Story title from PRD]

---

## Acceptance Criteria

- [ ] [Specific, testable criterion — not vague]
- [ ] [Another criterion]
- [ ] All existing tests still pass (no regressions)
- [ ] TypeScript: 0 errors
- [ ] ESLint: 0 errors, 0 warnings
- [ ] Coverage >= 80% for new code

---

## Definition of Done

- [ ] All acceptance criteria checked
- [ ] All tests passing (unit + integration)
- [ ] No console errors or warnings
- [ ] No TypeScript errors (mypy for backend, tsc for frontend)
- [ ] Lint clean
- [ ] Code review approved (HITL issues only)
- [ ] Issue moved to `done/` in `current-dev-issues/`
- [ ] `.state/project-map.yaml` issue status updated to `complete`
- [ ] `.state/test-status.md` updated with latest run
