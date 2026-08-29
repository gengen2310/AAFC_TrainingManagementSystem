# Training Year context — test matrix

Date: 2026-08-29

## Note on the instruction's A–H scenarios

The superseding instruction named staging scenarios "A–H" in its §59. That
lettering is not recorded anywhere in this repository, so it cannot be
reproduced faithfully here and **this matrix is derived from the spec instead**.
Paste §59 and the rows below can be mapped to its letters.

## 1. Automated coverage

| suite | tests | what it holds |
|---|---|---|
| `backend/tests/test_year_context.py` | 25 | timezone resolution, derived state, materialise-on-write, listing, past-year lock |
| `backend/tests/test_year_copy_setup.py` | 7 | copy-setup, rollover naming, past-year 403 through a real route |
| `backend/tests/test_renumber_708_guard.py` | 6 | the v58 guard in all three states, and the audit tool's pure core |
| `backend/tests/test_wing_timezone_migration.py` | 3 | v57 backfills every wing, and keys off NULL not a code |
| `frontend/e2e-connected/year-bar.spec.ts` | 18 | the year bar in real Chromium against a real backend |
| `frontend/src/tests/resolveYearSelection.test.ts` | 9 | the TMS→PW handoff decision |

Full backend suite at the time of the deploy: **2031 passed, 9 skipped, 0
failed**. Frontend: typecheck clean, 69 vitest, `vite build` clean.

## 2. Behaviours and where each is pinned

| # | behaviour | pinned by |
|---|---|---|
| 1 | Current year is the wing-local calendar year | `test_current_year_is_the_wing_local_calendar_year` |
| 2 | **1 January performs no database write** | `test_new_years_eve_and_new_years_day_differ_with_no_database_write` |
| 3 | past/current/future are derived, not stored | `test_year_state_is_derived_not_stored` |
| 4 | Selectable years capped at current + 2 | `test_selectable_years_are_capped_at_current_plus_two` |
| 5 | A read never creates a row | `test_find_does_not_create`, `test_year_context_read_does_not_create_a_row` |
| 6 | `ensure_year_context` is idempotent | `test_ensure_creates_once_and_is_idempotent` |
| 7 | It survives losing the insert race | `test_ensure_recovers_when_it_loses_the_insert_race` (red-green verified) |
| 8 | Names are derived, never entered | `test_ensure_derives_the_name_and_never_invents_one` |
| 9 | Default listing stays materialised-only | `test_the_default_listing_stays_materialised_only` |
| 10 | Cross-squadron year read is 403 | `test_year_context_rejects_another_squadrons_year` |
| 11 | Rollover no longer arrows the name | `test_rollover_no_longer_arrows_the_year_name` |
| 12 | Past years are read-only | `test_writing_to_a_past_year_is_blocked` |
| 13 | Delegated Intervention may correct history | `test_delegated_intervention_may_correct_a_past_year` |
| 14 | Plain Proxy Mode may **not** | `test_plain_proxy_mode_is_not_enough_to_edit_history` |
| 15 | The lock covers every year-scoped endpoint | `test_the_past_year_lock_covers_every_year_scoped_write_endpoint` |
| 16 | Setup status ignores row existence | `test_setup_status_does_not_require_a_materialised_year` |
| 17 | A new wing always stores a zone | `test_a_newly_created_wing_stores_a_timezone` |
| 18 | v57 backfills every wing | `test_every_wing_is_backfilled_not_just_7wg` |
| 19 | v58 refuses any unexpected state | `test_guard_refuses_when_the_state_differs` |
| 20 | Stepping reaches a row-less year | `stepping reaches a future year that has no row at all` |
| 21 | The numeral is tabular (no layout shift) | `the year numeral is tabular…` |
| 22 | 44px hit targets | `every year-bar control meets the 44px hit target` |
| 23 | Empty future year offers exactly two actions | `an empty future year offers exactly the two things…` |
| 24 | Past year states read-only and the way out | `a past year states it is read-only…` |
| 25 | Menu tags say what a year is for | `the year menu lists what can be selected…` |
| 26 | The menu is not clipped | `the year menu is actually on screen, not clipped…` |
| 27 | Rollover notice does not move the user | `when the year rolls over mid-session…` |
| 28 | …and does not fire on a deliberately-opened past year | `deliberately opening a past year does not claim…` |
| 29 | No request is ever made for a null year id | `no request is ever made for a null planning year` |
| 30 | TMS→PW honours a handover to a row-less year | `honours a handover to a year with NO row` |

## 3. Verified on staging, 2026-08-29 (`c9c1b80`)

Live checks against `aafc-tms-backend-staging`, after deploy:

| check | result |
|---|---|
| Exactly one year reports `state=current` | **PASS** — 2026 |
| `year-context` for 2029 / 2030 | **PASS** — `state=future`, `materialised=false`, `id=null`, name `"2029 Training Year"` |
| A read creates no row | **PASS** — year count 13 → 13 across both reads |
| copy-setup into 2020 | **PASS** — 403 `past_year_read_only`, message names Delegated Intervention |
| `GET /api/setup/status` | **PASS** — 200, `planning_year_active` absent, 14 steps |
| Wings able to resolve a year | **PASS** — 15 wings, 0 with NULL timezone |
| Deploy gates | **PASS** — all backend/frontend/PW gates, incl. Playwright smoke on all three services |

The `setup/status` row is the significant one: that endpoint is what would have
500'd for ~120 squadrons under the 7WG-only backfill.

## 4. Not covered

- **v58 is unexercised.** 708's row is absent from staging, so the renumber
  no-ops there. It has unit tests for all three guard branches but no
  environment has run it for real.
- **No human validation.** No 5-second test, first-click test or screen-reader
  pass has been run on the year bar. The structural audit in the design doc is
  not a substitute — marked HUMAN VALIDATION PENDING there.
- **PW's own year UI** — PW has the corrected handoff and selection logic, but
  not the empty-year panel or past-year notice.
- **Inherited Activities is not year-scoped** — pre-existing, see the design
  doc §11.
