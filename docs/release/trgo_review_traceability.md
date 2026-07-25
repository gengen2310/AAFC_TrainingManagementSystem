# TRGO Review Traceability

Eight user-feedback themes raised during general-release qualification, traced to root
cause against the codebase as of 2026-07-26 (branch `feature/restore-planning-workspace`).

**Provenance note**: the exact original wording of each feedback item was lost when an
earlier session in this qualification pass was summarized — only the eight short topic
labels below survived. Each was independently investigated against the current codebase
rather than assumed from memory; findings are evidence-based (file:line citations), not
reconstructed from the lost original text.

For each item: current behaviour, verdict, and disposition (fixed this pass / deliberately
deferred with the specific blocker found / working as intended).

---

## TRGO-01: Default parade night day change scope

**Investigated**: `Squadron.default_parade_day` (`backend/app/models/organisations.py:41`)
is a plain display/default field, updated via `PATCH /squadrons/{squadron_id}`
(`backend/app/routers/organisations.py:207-228`) with no cascade logic. Actual parade-date
generation (`generate_parade_dates`, `backend/app/routers/planning.py:706-755`) takes an
explicit `weekday` parameter, not this field. Already-created `ParadeDate` rows store a
concrete ISO date string that is never re-derived from the squadron setting.

**Verdict: WORKING AS INTENDED.** No mechanism exists by which changing this setting could
retroactively alter existing/scheduled parade nights — the concern behind the feedback does
not reproduce.

**Note, not a defect**: the field is functionally inert as a UI default — both frontends
hardcode their own initial weekday selection in the generate-dates form
(`frontend/src/components/planning/SetupPanel.tsx:58`, `connected-frontend/index.html:7063`)
instead of reading `default_parade_day`. Low-priority UX polish, not fixed this pass.

**Disposition**: No fix required.

---

## TRGO-02: Inherited activities/holidays visibility model

**Investigated**: `HolidayPeriod` (`backend/app/models/planning.py:55-64`) and
`AnchorEvent` (`planning.py:67-85`) both belong to exactly one `planning_year_id` with no
cross-level query — a wing/national admin's holiday or anchor event is invisible outside
the exact planning year it was created under. This is inconsistent with two other models
that *do* correctly cascade national/wing → squadron: `CurriculumItem`
(`_curriculum_scope_query`, `planning.py:2131-2152`) and `WingHQEvent`
(`backend/app/models/wing_calendar.py`, `backend/app/routers/wing_calendar.py:293-310`,
whose own docstring states "Squadrons never copy Wing events — they see them as inherited
overlays").

**Verdict: CONFIRMED DEFECT.** Same shape of gap as DEFECT-005's CEA inheritance finding —
two of four comparable models correctly implement wing→squadron inheritance, two don't.

**Disposition: deliberately deferred**, same reasoning as DEFECT-005. A safe fix requires
deciding the canonical visibility/dedup model (should a squadron's own `PlanningYear` read
holidays/anchors by matching `wing_id` in addition to `planning_year_id`, and if so, does
anything that currently assumes strict `planning_year_id` scoping break) — this is an
architecture decision, not a quick query change, and is the same underlying pattern as
DEFECT-005's deferred piece. Recommend resolving both together in one pass, since the fix
shape (and its risks) are identical.

---

## TRGO-03: Guided training-year workflow

**Investigated**: A real 2-step setup wizard exists
(`frontend/src/components/planning/SetupPanel.tsx:47-247`, year → dates), but
`PlanningWorkspace.tsx:171-178` only renders it when the squadron has zero existing
planning years — there's no way back into it afterward, and it omits holidays entirely. A
backend rollover endpoint (`POST /years/{year_id}/rollover`, `planning.py:2630-2735`,
including a `copy_holidays` option) exists and works, but has **zero** frontend wiring — not
called anywhere in `frontend/src` or `connected-frontend/index.html`.

**Verdict: PARTIALLY IMPLEMENTED.** The guided flow only covers the rare "zero years,
absolute cold start" case; the common "roll over to next year" path is backend-complete but
has no UI trigger at all.

**Disposition: deliberately deferred.** Wiring a rollover UI (a button/flow calling the
existing, already-tested `/rollover` endpoint) is a genuinely scoped, lower-risk frontend
task compared to TRGO-02/05 — flagged as the best next candidate for a follow-up session,
specifically because the backend already exists and is tested (`test_planning.py`'s year
rollover coverage, confirmed via existing `frontend/e2e/year-rollover.spec.ts`).

---

## TRGO-04: Learning Hub link audit — RESOLVED (partial)

**Investigated**: `CurriculumItem.learning_hub_url` (`backend/app/models/training.py:32`)
has no format validation (plain `str | None`, no `HttpUrl` type). A "missing learning hub"
audit endpoint already existed (`GET /api/learning-hub-resources/missing`,
`backend/app/routers/program.py:193-197`) but targets an entirely different, parallel model
(`ProgramItem`/`LearningHubResource`) that `CurriculumItem` doesn't use, and was never
called from either frontend.

**Verdict: CONFIRMED DEFECT.** The one audit mechanism that existed pointed at the wrong
model and wasn't wired into any UI.

**Resolution (this pass)**: rather than fix the mismatched endpoint (a bigger, separate
`ProgramItem`/`CurriculumItem` relationship question flagged elsewhere as an open
architecture question), added a client-side "Missing Learning Hub link" filter checkbox to
connected-frontend's Curriculum page (`connected-frontend/index.html:834-838`,
`renderCurr()` at `:5135-5146`) — the data (`learning_hub_url`) is already loaded into
`S.curr` client-side, so this required no new backend endpoint. Verified live: toggling the
filter against seeded 703 data (which has Learning Hub links on every core item) correctly
shows "No curriculum items."

**Not done**: the equivalent filter in the React Planning Workspace's Curriculum page, and
URL format/reachability validation. Scoped follow-ups, not silently dropped.

---

## TRGO-05: Facilitator CSV import

**Investigated**: No bulk/CSV import mechanism exists for facilitators anywhere. Only
single-record `POST /facilitators` (`backend/app/routers/training.py:613`). Curriculum has
a dedicated CSV import flow (`connected-frontend/index.html:818,1950-1971`); facilitators
only have a one-at-a-time "+ Add Facilitator" modal.

**Verdict: CONFIRMED GAP — not found, not partially built.**

**Disposition: deliberately deferred.** This is a genuinely new feature (CSV parsing
endpoint, column-mapping/preview UX, dedup against the TRGO-07 fix below, error reporting
per row) comparable in size to the CEA import pipeline itself — not a same-day fix alongside
seven other items. Recommend scoping as its own piece of work, explicitly reusing the CEA
import pipeline's proven preview→commit UX pattern (`backend/app/routers/planning.py:3856
-4000`) as the template, and layering on top of TRGO-07's now-existing duplicate-detection
check so a bulk import doesn't reintroduce the exact problem TRGO-07 just fixed for
one-at-a-time creation.

---

## TRGO-06: Save-latency UX — RESOLVED (one flow)

**Investigated**: Inconsistent across the app. Session-edit
(`connected-frontend/index.html:5007-5044`) and the Planning Workspace's drawer forms
(`frontend/src/components/planning/PlanningRightDrawer.tsx`) already show proper
"Saving…"/disabled-button states. Curriculum-item create/edit in connected-frontend
(`saveCurr`, `index.html:5369-5406`) had **no** loading indicator at all — the Save button
never changed state during the network round-trip.

**Verdict: CONFIRMED DEFECT** (one flow; most others already correct).

**Resolution (this pass)**: `saveCurr()` now disables the Save button and sets its text to
"Saving…" for the duration of the request, restoring the original label in a `finally`
block so it recovers correctly on error too (`index.html:5369-5406`, button now has
`id="c-save-btn"`, `index.html:1842`). Verified live: watched the button read "Saving…"
during a real submit, then correctly close the modal and show the new item.

**Not done**: `frontend/src/routes/Facilitators.tsx`'s `AddFacModal` only disables its
button without a text change during save — a smaller, lower-priority instance of the same
pattern, not fixed this pass.

---

## TRGO-07: Duplicate facilitators — RESOLVED

**Investigated**: `add_fac` (`backend/app/routers/training.py`, pre-fix) inserted a new
`Facilitator` unconditionally with no query for an existing same-name row first. Neither
frontend performed any pre-submit check either.

**Verdict: CONFIRMED DEFECT.**

**Resolution (this pass)**: `POST /api/facilitators` now checks for an existing,
non-archived facilitator in the same squadron with a case-insensitive first+last name match
before creating. If found, returns `409 possible_duplicate` with the existing record's ID
and a plain-language message, rather than silently allowing a duplicate or (the alternative
considered and rejected) permanently blocking same-name-different-person cases. A caller can
pass `confirm_duplicate: true` to create anyway — this is a genuinely legitimate case (two
different people can share a name), not just a workaround. Scoped per squadron, matching how
a facilitator roster is actually used (confirmed via new regression test — same name in a
different squadron is never blocked). 5 new tests in `backend/tests/test_trgo_items.py`.

**Not done**: no "Add anyway" confirm-and-resubmit button wired into either frontend yet —
today a user sees the warning message (both frontends already surface backend error
messages generically) but has no one-click way to override; they'd need to change a name
slightly and retry, or a developer would need to call the API directly with
`confirm_duplicate: true`. Small, clearly-scoped frontend follow-up.

---

## TRGO-08: Date/module filtering

**Investigated**: Three different pages, three different states.
- **Curriculum** (`frontend/src/routes/Curriculum.tsx`): working phase + element ("module")
  filters. No date filter — not applicable, curriculum items aren't dated records.
- **Mission Backlog** (`frontend/src/components/planning/PlanningBottomDrawer.tsx:99-152`):
  working module/status filters, but **no date-range filter** — and the gap is end-to-end:
  the backing endpoint (`list_missions`, `backend/app/routers/planning.py:2155-2166`) has no
  `start_date`/`end_date` query parameters at all, so this isn't a UI-only gap.
- **Reports** (`frontend/src/routes/Reports.tsx`, `backend/app/routers/ops.py:87-131`): no
  date or module filter in either layer — all-time, all-items aggregates only.

**Verdict: PARTIALLY IMPLEMENTED**, unevenly across the three pages.

**Disposition: deliberately deferred.** Curriculum's existing module filter needs no
change. Mission Backlog and Reports both need new backend query parameters plus UI controls
— a real but bounded feature addition (unlike TRGO-02/05, this doesn't touch tenancy or
data-model visibility, just adds optional filter parameters to existing read endpoints), a
reasonable next follow-up once TRGO-03's rollover UI is done.

---

## Summary

| # | Theme | Verdict | Disposition |
|---|---|---|---|
| TRGO-01 | Parade night day change scope | Working as intended | No fix required |
| TRGO-02 | Inherited activities/holidays | Confirmed defect | Deferred — same architecture question as DEFECT-005 |
| TRGO-03 | Guided training-year workflow | Partially implemented | Deferred — rollover UI wiring, scoped follow-up |
| TRGO-04 | Learning Hub link audit | Confirmed defect | **Fixed** (connected-frontend filter); React app + URL validation deferred |
| TRGO-05 | Facilitator CSV import | Confirmed gap | Deferred — sized as its own feature, reuse CEA import as template |
| TRGO-06 | Save-latency UX | Confirmed defect | **Fixed** (curriculum save); facilitator modal button-text deferred |
| TRGO-07 | Duplicate facilitators | Confirmed defect | **Fixed** (backend + regression tests); frontend confirm-and-retry UX deferred |
| TRGO-08 | Date/module filtering | Partially implemented | Deferred — Mission Backlog + Reports need new filter params, scoped follow-up |

Three of eight items fixed and verified this pass (TRGO-04 partial, TRGO-06 partial,
TRGO-07 full with backend tests). Five deferred with a specific, evidence-based blocker or
scope reason recorded above — none silently dropped.
