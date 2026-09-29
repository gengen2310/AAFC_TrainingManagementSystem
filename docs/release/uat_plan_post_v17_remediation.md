# AAFC TMS — UAT Plan: post-v17.1 remediation (PR #65)

**Status: PENDING.** Prepared 2026-09-29 for human testers. Automated tests cannot certify this plan;
only representative, non-developer users can. Supersedes nothing: `docs/beta/37_user_acceptance_test_plan.md`
remains the historical beta plan.

---

## Preconditions (must be true before testers start)

1. PR #65's branch is deployed to **staging** (not production) and its SHA is recorded below.
2. Staging `/api/health/ready` returns 200 and Alembic head matches the branch (`alembic heads`).
3. Staging holds **synthetic data only**. Testers must not enter real names, real personal details or real codes.
4. One test account per profile below exists (created through Account Management by an administrator).
   Codes are issued through a secure channel and are **never** written in this document or its results.

| Item | Value (fill in) |
|---|---|
| Staging SHA | |
| Staging Main TMS URL | |
| Staging Planning Workspace URL | |
| UAT window | |
| Coordinator | |

---

## Tester profiles

| ID | Role | Unit | Why |
|---|---|---|---|
| T1 | `sqn_admin` (experienced) | 703 SQN | Primary planner; exercises every write workflow |
| T2 | `sqn_general` (less experienced) | 703 SQN | **New read-only model** (see §C); UX clarity |
| T3 | `sqn_admin` | a different 7WG squadron | Tenancy isolation against T1's data |
| T4 | `wing_viewer` | 7WG | Wing read-only scope |
| T5 | `wing_admin` | 7WG | Wing scope, Proxy Mode into a squadron |
| T6 | `national_viewer` | National | National read-only rollups |
| T7 | `national_admin` | National | Account creation authority, Delegated Intervention |
| T8 | `auditor` | National | Audit read access, no writes anywhere |
| T9 | `system_admin` | System | System Console; browsing via scope bar is read-only until Intervention |

Record for every task: **Pass / Fail / Blocked**, the time taken, and any wording that confused you.

---

## A. Everyone (T1–T9)

| # | Task | Expected |
|---|---|---|
| A1 | Sign in with your code in a private window | Your unit and role are shown; no other unit's name appears |
| A2 | Open every item in the left navigation | Every page loads; nothing shows "error", a raw code, or a blank panel |
| A3 | Sign out, then press Back | You are not returned into the app without signing in again |
| A4 | Open Help & Reference, then Getting Started | Content matches what you see in the app (terms: *Needs Attention*, *Cadet Management*) |

## B. Squadron administrator (T1; T3 repeats B1 and B9 only)

| # | Area | Task | Expected |
|---|---|---|---|
| B1 | Training Dashboard | Review the dashboard for the current training year | Training Classes and Class Forecasts show real, non-empty values; spacing is readable |
| B2 | Activities | Add a local Activity, then a Holiday Period; view Inherited Activities | Only three concepts appear: **Activities, Holiday Periods, Inherited Activities** — no "Anchor Events" or "Wing HQ Events" |
| B3 | Unit Settings | Open **Training Classes** (it lives in Unit Settings); add a class, edit it, archive and restore it | Each change sticks after reload; archived classes are hidden until "Show archived" |
| B4 | Parade Nights | Open a Parade Night; plan a session with a Curriculum Item, **one Lead Facilitator, two Assistant Facilitators**, and a Room; save; reload | All four persist; you are **not** asked to pick a Phase; the Lead is not offered as an Assistant |
| B5 | Weekly Program | Open the Weekly Program for that night; print it | The session, its Training Class, Lead, Assistants and Room appear correctly on screen and in print |
| B6 | Cadet Management | Add a cadet; open the **CEA Import** tab and preview a small synthetic CSV | Both are inside Cadet Management; the preview shows what will change before you commit |
| B7 | Needs Attention | Review training requirements; open "View PN" on a scheduled item | It is the single place for outstanding work; there is no separate Mission Backlog page |
| B8 | Account Management | Add an account for your squadron; type slowly in the name field | The form never resets while typing; scope is fixed to your squadron |
| B9 | Isolation (T3) | Look for T1's cadets, classes, sessions or accounts | None are visible anywhere |
| B10 | Past years | Open a past training year from the year bar | It is clearly read-only and says how corrections are made |
| B11 | Planning Workspace | Open Planning Workspace from Main TMS | It opens already signed in, on your squadron, without a second login |

## C. Squadron general — read-only model (T2) — **decided 2026-09-28**

| # | Task | Expected |
|---|---|---|
| C1 | Open Unit Settings | Visible. Every field is greyed out; there is no Save button, no Access Code change, no User Directory |
| C2 | In Unit Settings, view Training Classes, Training Years and Custom Training Phases | All three are listed; no Add / Edit / Delete buttons |
| C3 | Open Activities, Parade Nights, Weekly Program, Cadet Management | You can read them; you cannot change anything |
| C4 | Open Account Management | Your squadron's accounts are listed; no Add, Disable, Archive, Reset Code or Change Scope actions; no codes are ever shown |
| C5 | Open Audit | Your squadron's activity history is shown (not a "cannot read" message) and nothing from other squadrons |
| C6 | Look for any way into Planning Workspace | There is **none**: no nav link, no Settings button |

## D. Wing, National, Auditor, System (T4–T9)

| # | Who | Task | Expected |
|---|---|---|---|
| D1 | T4, T5 | Open Wing Overview and Wing HQ Calendar | Only 7WG squadrons appear |
| D2 | T5 | Enter Proxy Mode into 703; make one small change; exit | A reason is required; the change is attributed in Audit |
| D3 | T5, T7 | Add Account: choose role, then Wing, then Squadron | The Squadron list follows the chosen Wing; you cannot pick a Squadron with no Wing |
| D4 | T6, T7 | Open National Overview | Figures load for every Wing |
| D5 | T8 | Try to change anything anywhere | No write controls are offered |
| D6 | T9 | Browse a squadron via the scope bar; then try a change | Browsing needs no reason; a change requires Delegated Intervention |
| D7 | T9 | System Console → maintenance mode on, then off (agree timing with the coordinator) | Other testers see the maintenance state; normal service returns after switching off |

---

## Results

| Tester | Task | Result | Time | Notes / confusing wording |
|---|---|---|---|---|
| | | | | |

## Defects found

| ID | Tester | Task | What happened | Severity (P0–P3) | Screenshot ref |
|---|---|---|---|---|---|
| | | | | | |

## Sign-off

UAT is complete only when every tester profile has run its tasks, every Fail is triaged, and the
coordinator signs below. Technical CI evidence does **not** substitute for this sign-off.

| Coordinator | Date | Decision (accept / accept with conditions / reject) |
|---|---|---|
| | | |
