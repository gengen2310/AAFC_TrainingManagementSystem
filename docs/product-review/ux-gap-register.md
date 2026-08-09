# UX gap register

Status: initial pass, 2026-08-09. This register tracks UX/product findings
specific to this program (§0-§60's design principles) that are not yet formal
engineering gap-register entries with severity/root-cause/fix. Items that
graduate to a confirmed, reproducible defect move to
`docs/remediation/master_gap_register.csv` under the WRITE-*/CLASS-*/UX-*
prefixes; this document is the earlier-stage working list.

## Confirmed this pass (from direct code inspection)

1. **No universal search/command palette (§6)** — not found anywhere in
   either frontend. Genuine gap, not yet built.
2. **No "What changed?" view (§40)** — not found. Genuine gap.
3. **No Needs Attention consolidated queue as a single surface (§39)** —
   individual pieces exist (readiness warnings, Mission Backlog) but not
   consolidated into one prioritised action queue. Partial gap.
4. **No pre-flight/readiness check UI matching §38's exact format** — the
   readiness percentage/data exists (`dashboard.py`'s readiness functions)
   but not yet confirmed whether the frontend renders it as an explainable
   checklist (✓/! per item) vs a single percentage. Needs a rendered check,
   not yet done this pass.
5. **Rank stored as free text on `Facilitator`, not the canonical AAFC rank
   model (§16)** — `Facilitator` model fields not yet inspected in this pass
   for rank storage shape; flagged for the next discovery pass rather than
   guessed here.
6. **Holiday type defect (§14.2) — does NOT reproduce against current code.**
   Reported symptom: Holiday types appear as `school_holiday` regardless of
   actual meaning. Actual reproduction result: `HolidayPeriod.holiday_type`
   defaults to `"school_holiday"` at the model/API level (confirmed,
   `planning.py:62` and `992`), but connected-frontend's own create/edit
   Holiday modals (`index.html:1797-1834`) already present a required
   (`Type *`) 5-option selector — School Holiday, Public Holiday, Squadron/
   Wing/National Stand-Down — and a broader display label map
   (`_HOL_TYPE_LABELS`, `index.html:9561`) covering 8 types including
   `local_closure`/`training_pause`/`other`. Every holiday created through
   the normal UI form already gets a real, chosen type. **Root cause of the
   part that IS real**: `export_import.py` (CSV/CEA import) has zero
   references to `holiday_type` — there is no holiday import path at all
   currently, so this isn't a live bug today, but if/when a bulk-import path
   for holidays is added (addendum §41), it would need to either map a
   source type or explicitly flag `type: unknown` for correction rather than
   silently defaulting to `school_holiday` — the addendum's underlying
   principle ("unknown means unknown, not silently mapped") is correct
   guidance for that future work, even though no current holiday actually
   exhibits the reported symptom. Not logged as a gap-register defect since
   nothing is currently broken; noted here as a design constraint for when
   holiday import is built.

## Deferred to their own tracked work (not re-litigated here)

- Training Class model — see `parallel-class-impact-analysis.md`, tracked as
  CLASS-01 through CLASS-14 in the master gap register.
- Defence writing / plain-language content review — see
  `docs/standards/defence-writing-ui-standard.md`, tracked as WRITE-01 through
  WRITE-07.
- Dashboard chart-specific gaps — see `dashboard-metric-dictionary.md`.

## Explicitly not yet investigated this pass

Sections 11-13 (flexible time blocks, plan-faster productivity features,
smart planning assistance), 32-34 (404 defect, Firefox, maintenance mode),
36 (visual design), 41-42 (bulk import, CEA relationship) — all real,
in-scope items from the governing instructions that a single discovery pass
could not cover exhaustively. Listed here so they are visible as open rather
than silently dropped; each needs its own targeted investigation before a
fix is attempted, per this program's own discovery-before-coding rule (§2).
