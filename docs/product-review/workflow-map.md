# Workflow map

Status: fully measured, 2026-08-13. Baseline for §37 — click/field counts for
all 12 high-frequency workflows across both frontends, measured by code-trace
inspection of modal/form implementations. "Required fields" = frontend-validated
fields (JS guard or `required` attribute); server-side-only validation is noted
separately. Counts start from the relevant page/tab already open.

---

## Measurement table

| # | Workflow | Frontend | Steps | Required fields | Clicks | Notes |
|---|---|---|---|---|---|---|
| 1 | Add Facilitator | Main TMS | 1 | 1 | 2 | Single modal (`m-add-fac`). Family Name is the only frontend-validated field. Rank, Given Name, Type, Subject Areas are optional. Clicks: open + Save Profile. |
| 2 | Create Training Year | Planning Workspace | 4 | 1–3 | 4–11 | Four-step wizard (start → timing → dates → placement). Each step is a separate screen. Steps 2–4 are skippable. Minimum path (rollover): open + Continue + Skip×3 = 4 clicks. Step 1: Name (required); step 3 adds Start date + End date; step 4 adds Curriculum item. Up to 8+ configurable fields across all steps. |
| 3 | Generate Parade Nights | Main TMS | 1 | 2 | 2–3 | Single modal (`m-gen-dates`). Required: Start date + (End date OR Max Repeats). Optional Preview step adds 1 click before submit. Visible only to planning-write users. |
| 4 | Add Holiday / Activity | Main TMS | 1 | 0–4 | 2 | Add Holiday (`m-add-holiday`): 4 required fields (Name, Type, Start, End). Add Activity (admin): 0 required fields. Both are single-modal, 2 clicks. |
| 5 | Schedule Session | Main TMS | 1 | 0 | 2 | Quick Edit modal (`m-sess-edit`) via ✏ button on session card. All fields optional (Status, Curriculum Item, Facilitator, Room). Sessions are stub-created during Parade Night generation. |
| 5b | Schedule Session | Planning Workspace | 1 | 0 | 2 | Click empty grid cell → right drawer (`SessionForm` in `PlanningRightDrawer.tsx`). Fields: Curriculum (searchable), Activity title, Cadet group, Session#, Part#, Lead/Asst Facilitator, Room, Notes. All optional. |
| 6 | Assign Facilitator | Main TMS | 1 | 0 | 2 | Same Quick Edit modal as workflow 5. Combinable with Room assignment (workflow 7) in the same 2-click operation — no extra steps or clicks needed. |
| 7 | Assign Training Area | Main TMS | 1 | 0 | 2 | Same Quick Edit modal as workflow 6. If done together with Facilitator: still 1 Edit + 1 Save = 2 clicks total. |
| 8 | Record Outcome | Main TMS | 1–2 | 0–1 | 1–3 | Fast path: 1 click via quick-outcome buttons (✓ Delivered, Not-Delivered, ✗ Cancelled) directly on session card — no modal. Reason field is required when status is `not_delivered`, `cancelled`, `cancelled_late`, or `delivered_with_issue`; a reason modal opens automatically in those cases (+1 click + text entry). Full path via Quick Edit: 2 clicks. |
| 9 | Move Session | Main TMS | 0–1 | 0 | 0–2 | Three mechanisms in PN Detail: (a) ↑/↓ period arrows — 1 click; (b) "Move to…" modal (`m-sess-move-to`, cross-parade-night) — 2 clicks; (c) drag-and-drop via ⠿ handle on session cards — 0 clicks. Planning Workspace has **no move capability**. |
| 10 | Publish Weekly Program | Planning Workspace | 2 | 0 | 2 | Parade Nights list → click parade night → Publish button in `ParadeNightDetailView`. Main TMS `apiPublishPN()` is defined but wired to **no UI control** — dead code. Main TMS "Weekly Program" page is a print-format view only. |
| 11 | Find Curriculum | Both | 1 | 0 | 1–3 | Main TMS Curriculum tab: 9 phase tabs + element filter + progress filter + text search; items show progress inline; click → drilldown panel with session history. Planning Workspace: Mission Backlog drawer tab with status filter and search. |
| 12 | Create Account | Main TMS | 2 | 2–4 | 3 | Create modal (`m-create-account`) + one-time access-code display modal. Required fields: Display Name + Role always; Wing added for wing/sqn-scoped roles; Squadron added for sqn-scoped roles. Third click: "I have noted this code" to dismiss code display. Main TMS only (no account creation in PW). |

---

## Key findings

**Most complex workflow: Create Training Year (#2)**
4-step wizard, 4–11 clicks, up to 8+ configurable fields. The wizard steps are
skippable but the multi-page architecture surprises users expecting a single form.

**Fastest outcome recording: Record Outcome (#8)**
1 click for Delivered, Not-Delivered, or Cancelled via quick-outcome buttons
directly on the session card. Reason modal adds 1 more click for statuses that
require a reason.

**Workflows 6 and 7 share the same modal**
Assigning a Facilitator and assigning a Training Area both use `m-sess-edit`.
A user doing both in one operation incurs the same 2 clicks as doing either alone.

**Drag-and-drop IS implemented in Main TMS**
Session cards in PN Detail include a ⠿ drag handle. Planning Workspace has no
equivalent move capability.

**Publish Weekly Program is Planning Workspace only**
Main TMS `apiPublishPN()` is dead code — it is never called from any UI element.
Users relying on Main TMS alone cannot publish a Weekly Program. This is a
parity gap.

**Workflow 4 (Add Activity) has 0 required fields for admin users**
The admin activity modal applies no frontend validation, relying entirely on
server-side checks.

---

## Parity gaps identified

| Gap | Main TMS | Planning Workspace |
|---|---|---|
| Publish Weekly Program | No UI — dead code | Full Publish button |
| Move Session | 3 mechanisms incl. drag-and-drop | No move capability |
| Create Training Year | No wizard | Full 4-step wizard |
| Add Facilitator | Full modal with all fields | Consumes facilitators; no authoring |
| Create Account | Full workflow | Not present |

---

## Before/after baseline (§37)

Current baseline recorded 2026-08-13 at HEAD (pre-Phase 4 workflow efficiency
work). Target: each workflow's click count measured after Phase 4 improvements
and compared to this table. A workflow is improved if click count decreases or
required-field count stays the same or decreases without removing validation.
