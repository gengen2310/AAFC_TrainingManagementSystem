# Source Precedence Rules — AAFC TMS Final Programme

**verified_against_sha:** 7c342f9  
**verified_at:** 2026-08-30

---

## Rule 1 — Later explicit product decision supersedes older conflicting assumption

SRC-001 (this programme's master instruction) is the highest-authority source.
Where SRC-001 conflicts with older planning documents or historical review findings,
SRC-001 wins.

Example applied:
- Training Year is CALENDAR CONTEXT (SRC-001 Part 17). Not a lifecycle document. Supersedes all
  older "Create/Active/Draft/Archive" year lifecycle documentation.
- Getting Started must not display "Add cadets to roster" step (SRC-001 Part 20). Supersedes
  any historical help content that includes it.

---

## Rule 2 — More specific later addendum overrides broad earlier requirement where genuinely conflicting

SRC-001 Parts 41-48 (Training Area canonical model) override older "PlanningLocation" references
in historical review documents. PlanningLocation is now the same table as TrainingArea.

---

## Rule 3 — Current source code is EVIDENCE OF IMPLEMENTATION, not product authority

Where code conflicts with SRC-001:
- SRC-001 requirement wins, unless:
  - Security invariant (CLAUDE.md / .claude/rules/security.md) blocks the change
  - Data integrity risk requires human decision
  - An explicit ACCEPTED_EXCEPTION is recorded in the gap register

---

## Rule 4 — Current specifications may be stale

Documents in docs/product-review/ reflect historical system state.
Documents marked HISTORICAL SNAPSHOT must not be used as current truth.
FIXED labels in old documents are not proof of current implementation.

Authoritative sources for current system state:
1. Code at HEAD 7c342f9
2. This programme's docs/final/ documents
3. Confirmed test evidence
4. Confirmed staging evidence

---

## Rule 5 — Visual/design decision hierarchy

AAFC VIG → brand identity (palette, logo, typeface)
Defence Writing Manual → user-facing language, grammar, abbreviations
Supplied Apple Design material → interaction reasoning, hierarchy, accessibility, craft

The Apple Design material informs interaction principles only.
Do NOT imitate Apple branding.
Do NOT use proprietary Apple assets.
Do NOT replace Montserrat with SF.

---

## Rule 6 — External engineering references are supplemental

Supplemental authorities (used for technical assurance only):
- Playwright official best practices
- FastAPI official testing guidance
- SQLAlchemy/Alembic official documentation
- WCAG 2.2
- OWASP ASVS 5.0.0
- Testing Library user-centred testing principles

These do NOT replace SRC-001 product requirements.

---

## Resolved conflicts at programme start

| Conflict | Earlier source | Later source | Resolution |
|---|---|---|---|
| Training Year lifecycle vs calendar context | Old plans (lifecycle model) | SRC-001 Part 17 | Calendar context wins |
| is_combined hardcoded False | planning.py:385 (code) | SRC-001 Part 30 | Fix required |
| capabilities absent from PW serializer | planning.py:318 (code) | SRC-001 Part 42 | Fix required |
| is_optional "future migration" | planning.py:354 (code comment) | SRC-001 Part 38 | Human decision required |
| Cadet roster in Getting Started | Historical docs | SRC-001 Part 20 | Remove from DOM |
| Stage catalogue | Narrow current list | SRC-001 Parts 26-28 | Domain analysis required |
| Safari SameSite cookie | Current code | SRC-001 Part 79 / SYN-H01 | Fix required |

---

## Source application map

| Requirement area | Primary source |
|---|---|
| Architecture, service boundaries | SRC-001, CLAUDE.md, SRC-004 |
| Security invariants | SRC-001, SRC-005, CLAUDE.md |
| Backend rules | SRC-001, SRC-006 |
| Frontend rules | SRC-001, SRC-007 |
| Training Year model | SRC-001 Parts 17-19 |
| Training Class and Stage | SRC-001 Parts 26-32 |
| Session and SessionAudience | SRC-001 Parts 22-25, 30-31 |
| Parade Night structure | SRC-001 Parts 21, 24-25 |
| Curriculum and progress | SRC-001 Parts 33-38 |
| Activities and CEA | SRC-001 Parts 45-51 |
| Facilitators | SRC-001 Parts 53-56 |
| Training Areas and capabilities | SRC-001 Parts 41-43 |
| Equipment | SRC-001 Part 44 |
| Mission Backlog | SRC-001 Part 52 |
| Plan Review and Readiness | SRC-001 Parts 57-61 |
| Account Management | SRC-001 Part 71 |
| Account Recovery | SRC-001 Parts 73-75 |
| Maintenance Mode | SRC-001 Part 70 |
| Design system | SRC-001 Parts 87-96, SRC-007 |
| Accessibility | SRC-001 Part 94, WCAG 2.2 |
| Testing | SRC-001 Parts 104-109, SRC-008 |
| Deployment | SRC-001 Parts 134-135, SRC-009 |
