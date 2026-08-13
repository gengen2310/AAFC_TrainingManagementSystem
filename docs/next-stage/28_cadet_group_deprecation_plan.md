# Session.cadet_group and Cadet.phase — Formal Deprecation Plan

**Gap register:** CLASS-16  
**Priority:** LOW  
**Status:** Deprecation notice issued 2026-08-13; migration schedule below.

---

## Background

`Session.cadet_group` (a free-text field, values: orientation/initial/junior/intermediate/senior) was the original mechanism for indicating which group of cadets a session was intended for. It predates the Training Class architecture (CLASS-01 through CLASS-14, now CLOSED).

`SessionAudience` (migration v49, table `session_audience`) is the structural replacement. It is a proper many-to-many join from `Session` to `TrainingClass`, with per-class outcome overrides.

The model docstring at `training.py:401–403` already states: "Session.cadet_group and Cadet.phase remain in place as free-text compatibility fields; this table is additive, not a replacement, until every consumer has migrated."

This document formalises that migration plan.

---

## Consumer Inventory

### Backend — `planning.py` (26 references)

| Usage type | Line examples | Migration path |
|---|---|---|
| **ORDER BY** — sort sessions by cadet_group in queries | 1531, 1813, 1836, 1958 | Replace with `SessionAudience` join, sort by `TrainingClass.sequence` |
| **Request schema** — `CreateSessionBody.cadet_group: str` | 1558, 2983 | Add `training_class_ids: list[str]` as optional param; both accepted during transition |
| **Validation** — `cadet_group not in CADET_GROUPS` guard | 1599, 3002 | Drop after frontend migrated |
| **Write** — assign `cadet_group` on Session creation | 1629, 3029 | Write `SessionAudience` rows instead (or in addition) |
| **Response field** — `"cadet_group": s.cadet_group` in JSON | 344, 2843, 3177, 4091, 4221, 4342 | Add `training_classes` array alongside; deprecate `cadet_group` field after frontends updated |
| **Filter** — `filter(Session.cadet_group == group_val)` | 3702 | Replace with `SessionAudience` join filter |
| **Set comprehension** — `{s.cadet_group for s in …}` | 2202, 2345, 2350 | Derive from `SessionAudience` instead |

### Backend — `training.py` (7 references)

| Usage type | Lines | Migration path |
|---|---|---|
| **Request schema** — `CreateSessionBody.cadet_group: str | None` | 604 | Add `training_class_ids: list[str]` alongside |
| **Write** — assign `cadet_group` on Session creation | 707 | Write `SessionAudience` rows |

### Connected-frontend (`index.html`) — 10 references

| Usage | Migration path |
|---|---|
| Session creation/edit forms — `cadet_group` `<select>` | Replace with `<select>` from `GET /api/training-classes` list |
| Session list display — shows `cadet_group` label | Show `class.display_name` from audience API instead |
| Filter controls — group filter uses cadet_group | Replace with training_class filter |

### Planning Workspace (`frontend/src/`) — 30 references

| Usage | Migration path |
|---|---|
| Session form — `cadet_group` field | Replace with Training Class selection from API |
| Session display — shows group label | Show class name from `session.training_classes` |
| Parade Night Builder components | Audit all `cadet_group` references in `ParadeNightBuilder` |

---

## Migration Phases

### Phase A — Backend dual-write (Level B)

Add `training_class_ids: list[str]` as an optional parameter to session creation/edit endpoints. When supplied: write `SessionAudience` rows. Continue writing `cadet_group` for backwards compatibility. No consumer is broken.

**Estimated scope:** `planning.py` session create/edit endpoints (~3 endpoints).

### Phase B — Frontend migration to Training Class selector (Level B)

Replace `cadet_group` `<select>` in both frontends with a `TrainingClass` multi-selector that calls `GET /api/training-classes?squadron_id=…`. The frontend sends `training_class_ids` instead of `cadet_group`. The backend continues accepting both during transition.

**Estimated scope:** Main TMS session modals (~3 occurrences); Planning Workspace session components (~4 components).

### Phase C — Backend response field deprecation (Level C)

Add `training_classes` array to session response bodies alongside `cadet_group`. Frontend consumes the new field. After verification, remove `cadet_group` from response bodies. Deploy to staging; verify no frontend breaks.

### Phase D — Database field removal (National release)

After Phase C is verified:
- Alembic migration: remove `Session.cadet_group` column and `Cadet.phase` column.
- Remove `CADET_GROUPS` constant from `planning.py`.
- Remove all validation guards.
- Remove `cadet_group` from all backend queries and response schemas.

This phase requires explicit authorisation per `.claude/rules/capability-preservation.md` — it permanently removes a stored field.

---

## Dependencies

| Dependency | Status |
|---|---|
| `SessionAudience` table and CRUD | CLOSED (CLASS-02, CLASS-07) |
| `TrainingClass` CRUD API | CLOSED (CLASS-04) |
| Training Class selector in frontend | CLASS-16 Phase B |
| Level B Wing activation in staging | HUMAN GATE (HG-01) |

---

## Not yet deprecated: `Cadet.phase`

`Cadet.phase` (a free-text phase string on the Cadet model) is a separate field from `Session.cadet_group`. It is NOT addressed by the `CadetClassMembership` model (CLASS-03) until individual cadet-class tracking is confirmed as a product decision (addendum §38/§39). Until that decision is made, `Cadet.phase` is intentionally retained as-is. It is explicitly out of scope for this deprecation plan.

---

## Review date

2026-11-01 — reassess at Level B milestone, when the Training Class selector should be complete in both frontends.
