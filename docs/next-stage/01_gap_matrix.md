# AAFC TMS — Next-Stage Gap Matrix

Phase 1 — Next-Stage Development Program.
Created 2026-07-16. Verified against repository at `43b880c` / branch `next-stage/v1-operational`.

---

## How to Read This Document

**Classification:**
- `COMPLETE WITH EVIDENCE` — gap is closed; evidence is on record
- `PARTIALLY COMPLETE` — partial implementation exists; specific work remains
- `NOT IMPLEMENTED` — no implementation exists
- `OBSOLETE` — gap no longer applies to current architecture
- `MANUAL OR POLICY DECISION REQUIRED` — no technical implementation until org approves

**Release columns:**
- `7WG V1` — required before 7 Wing Operational Version 1
- `Wing B` — required before a second Wing is activated
- `National` — required before National rollout

---

## Gap Matrix

| # | Area | Current state | Evidence | Missing requirement | Risk | 7WG V1 | Wing B | National | Decision |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Legacy page retirement | PARTIALLY COMPLETE | 9 dead divs removed RC1 (`e918f3e`); `nav('planning-year')→'activities'` redirect at line 2997 | (a) Stale "Annual Program" text at line 6842; (b) Audit remaining orphan JS and confirm all are active or remove | Low — functional redirect exists; label is misleading | ✅ clean up stale text | — | — | — |
| 2 | Main TMS / Planning Workspace visual unification | NOT IMPLEMENTED | `_PLANNING_PAGES=[]`; two separate services with no shared design tokens or shared nav | Shared typography, colour tokens, nav structure, logout, session expiry, planning-year context displayed consistently in both frontends | Medium — users experience two products | ✅ nav/session/logout unification | ✅ complete design tokens | ✅ complete | — |
| 3 | TrainingArea vs PlanningLocation overlap | NOT IMPLEMENTED | Two tables: `training_areas` (Main TMS) and `planning_locations` (Planning Workspace); `planning.py:1205` bridges them with a fallback lookup | Canonical model decision; migration; single API source; duplicate-prevention rule | Medium — data can diverge; assignment may reference wrong record | ✅ decision + migration plan | ✅ migration complete | ✅ | DECISION: adopt `training_areas` as canonical; deprecate `planning_locations` as adapter (see `04_canonical_data_model.md`) |
| 4 | Facilitator records across interfaces | PARTIALLY COMPLETE | One canonical `Facilitator` table; `PlanningFacilitatorLeave` is a supplement, not a duplicate | Expose leave records in Main TMS `page-facilitators`; expose facilitator load from Main TMS scheduling in Planning Workspace | Low — data is consistent; UI gap only | ✅ cross-expose leave | — | — | — |
| 5 | Individual accountability | NOT IMPLEMENTED | Shared access codes only; `User.display_name` is a role name; `created_by` identifies role, not person | Individual identity → see Phase 6 options (Option A: individual accounts; Option B: dual-factor identification) | High — cannot attribute actions to a person; audit is role-level only | ✅ present options | ✅ implement approved model | ✅ enforce | **MANUAL APPROVAL REQUIRED** before implementation |
| 6 | Silent last-write-wins concurrency | NOT IMPLEMENTED | No `version` field on any mutable model; no 409 Conflict responses anywhere | Optimistic locking on critical records; 409 on stale write; frontend conflict resolution UI | High — concurrent edits silently overwrite; data loss in multi-user scenario | ✅ | ✅ | ✅ | — |
| 7 | Operationally limited to 7 Wing (hardcoded strings) | PARTIALLY COMPLETE | Core RBAC uses `wing_id` FKs throughout; bootstrap endpoint hardcodes `Wing.code=="7WG"` and "703 Squadron AAFC"; `auth.py:21` hardcodes "7 Wing SOCAD" | Remove Wing-specific strings from bootstrap, error messages, and auth copy; make bootstrap Wing-configurable | Medium — system works for 7WG; any other Wing onboarding via bootstrap would fail or require code change | — | ✅ | ✅ | — |
| 8 | Multi-Wing onboarding not automated | NOT IMPLEMENTED | `seed_all.py` is 7WG-specific demo data; `staging_seed.py` creates a single system_admin only; no repeatable Wing onboarding script | Idempotent Wing onboarding script/API: inputs Wing name/code/TZ/squadrons/parade-night defaults/term dates/holidays/accounts; outputs dry-run report, created org records, onboarding audit, rollback procedure | High — onboarding a real second Wing currently requires manual DB operations | — | ✅ | ✅ | — |
| 9 | Wing and National reports show 7WG data only | PARTIALLY COMPLETE | Report RBAC correctly scopes by `wing_id`/`national_id`; no multi-Wing synthetic dataset exists to test cross-Wing aggregation | Synthetic second Wing in staging; verify Wing reports show only that Wing; verify National aggregates all Wings; verify no cross-Wing data leak in reports | High — unproven aggregation path | — | ✅ | ✅ | — |
| 10 | Incomplete report catalogue | PARTIALLY COMPLETE | Five report pages exist: `curriculum-coverage`, `training-balance`, `facilitator-load`, `risk-bottlenecks`, `reports` (Training Summary); report definitions undocumented | Tier-1 report definitions; per-report: who uses it, decision supported, scope, period, source, calculation, drill-down, export, permission, performance target | Medium — current reports functional; catalogue not prioritised or complete | ✅ Tier 1 defined | ✅ Tier 2 defined | ✅ Tier 3 defined | See `09_report_prioritisation.md` |
| 11 | Year rollover not E2E proven | PARTIALLY COMPLETE | Planning year create/manage API exists; `PlanningYear` model with `parade_dates` generation; no browser E2E test; no rollover procedure document | Browser E2E test for full rollover: create next year, adjust parade dates, review holidays, verify historical sessions unchanged; documented procedure for Squadron Admin | High — rollover is annual critical event | ✅ | ✅ | ✅ | — |
| 12 | Playwright E2E coverage incomplete | PARTIALLY COMPLETE | 35 tests in 7 files; covers auth, nav, dashboard, session lifecycle, cross-interface, holidays/resources, wing-proxy | Add specs for: parade nights CRUD, scheduling (create/cancel/reschedule), facilitator assignment, leave conflict detection, room/equipment conflict detection, weekly program, reports, maintenance mode, year rollover, multi-Wing scope; accessibility with Axe | High — missing coverage on critical planning workflows | ✅ core workflows | ✅ multi-Wing | ✅ accessibility | — |
| 13 | Accessibility automation | NOT IMPLEMENTED | No Axe or equivalent integration; no keyboard-only workflow test; no zoom/contrast test | Axe integration in Playwright; keyboard-only navigation for all core workflows; focus order; label coverage; colour contrast; 1280×720, 1024×768, 125% zoom | Medium — no AODA/WCAG evidence | — | ✅ | ✅ | — |
| 14 | Production-scale load testing | NOT IMPLEMENTED | 7 Wing beta: 100 users, 5 endpoints, P95=548ms, CONDITIONAL PASS; no multi-Wing or higher-user test | 250, 500, 800-user tests with synthetic multi-Wing data; establish max stable user count, degradation point, recovery time; realistic workload (not just health checks) | High — unknown behaviour beyond 7WG scale | — | ✅ 250-user | ✅ 500-user | — |
| 15 | Distributed rate limiting | PARTIALLY COMPLETE | DB-backed `IpLoginAttempt` rate limiter exists and works across gunicorn workers; covers login endpoint only | Evaluate whether per-account and per-endpoint rate limiting is needed beyond login for multi-instance scale; implement if justified | Medium — login is protected; other endpoints unprotected from abuse at scale | — | ✅ evaluate | ✅ implement if needed | — |
| 16 | Synchronous imports/exports/reports | PARTIALLY COMPLETE | Celery + Redis infrastructure exists (`backend/app/workers/celery_app.py`); `JobStatus` model exists; `generate_export` task is a placeholder stub; Redis not provisioned in Railway; all actual import/export routes are synchronous | Measure actual request durations for heavy operations; implement async job dispatch for operations that exceed 30s or risk timeout at scale; connect `JobStatus` to a frontend polling endpoint | Medium — synchronous works for 7WG scale; risk at multi-Wing scale with large imports | — | ✅ measure + plan | ✅ implement for heavy ops | — |
| 17 | Production monitoring and alerting | PARTIALLY COMPLETE | Structured JSON access log per request (main.py); `X-Response-Time-ms` header; no correlation IDs; no request ID propagation; no error-rate monitoring; no alerting; no dashboard | Correlation IDs on every request; error-rate monitoring; latency monitoring; login-failure monitoring; backup-failure alerting; service restart alerting; support runbook tied to alerts | High — cannot diagnose production incidents without correlation IDs | ✅ correlation IDs | ✅ full alerting | ✅ | — |
| 18 | Maintenance mode limited | PARTIALLY COMPLETE | Blocks WRITE methods for non-system_admin; system_admin bypasses; login/logout/health exempt; audited; message configurable | (a) Optionally block logins during maintenance; (b) Expose expected return time via API; (c) Safely drain background jobs if Celery is in use; (d) Frontend maintenance page (not just API 503) | Low for 7WG; medium at scale | ✅ login-block option | ✅ | ✅ | — |
| 19 | Session revocation limited | PARTIALLY COMPLETE | JTI field exists in JWT payload; no JTI blacklist; no forced logout after access code reset; no server-side session invalidation | (a) On access code reset: invalidate all active tokens for that user; (b) On account disable: invalidate; (c) On role change: optionally invalidate; lightweight JTI blocklist (DB or Redis) | High — revoking a compromised code does not invalidate existing session tokens | ✅ | ✅ | ✅ | — |
| 20 | CSRF controls | PARTIALLY COMPLETE | CORS locked per environment (no wildcard); `SameSite` cookie config says `lax` but architecture requires `none` for cross-origin Planning Workspace handoff; no CSRF tokens | (a) Confirm `COOKIE_SAMESITE=none` is set in Railway production env vars (code default is `lax`); (b) Document CORS+SameSite as the CSRF mitigation strategy; (c) Assess whether CSRF tokens are required given the auth model | Medium — CORS+SameSite provides strong mitigation if correctly configured | ✅ verify + document | ✅ | ✅ | — |
| 21 | Backup and restore continuous verification | PARTIALLY COMPLETE | Daily backup + weekly restore workflows active; last proven runs documented; backup key custody pending (5 human actions); no quarterly restore rehearsal schedule | (a) Complete backup key custody (5 human actions); (b) Schedule quarterly restore rehearsal; (c) Run disaster recovery rehearsal in staging (service deletion, bad migration, restore from backup) | High — backup workflows exist but not rehearsed end-to-end for a genuine outage | ✅ key custody + DR rehearsal | ✅ | ✅ | — |
| 22 | External penetration testing | NOT IMPLEMENTED | No external pen test conducted; internal security tests (IDOR, auth, lockout, role bypass) pass at rc3 | Independent external penetration test covering auth, session, IDOR, Wing isolation, CSRF, XSS, import abuse, audit integrity, dependency scan | Critical for National — required before releasing beyond 7WG beta | — | ⚠️ recommended | ✅ required | **MANUAL APPROVAL REQUIRED** — budget and scope from org |
| 23 | Data governance, retention, named ownership | MANUAL OR POLICY DECISION REQUIRED | No formal governance decisions documented; `46_data_governance_and_approval.md` template exists with 9 pending decisions | Organisation must decide: personal data policy, cadet data policy, audit log access, retention periods, archive/delete requirements, incident reporting, production data ownership, support ownership, account removal | Critical — cannot store personal data without governance decisions | ✅ decisions made | ✅ | ✅ | **MANUAL GOVERNANCE DECISION REQUIRED** for every item |
| 24 | Beta feedback not collected | NOT IMPLEMENTED | No formal feedback register exists at program start | Create `02_beta_feedback_register.md` (done); populate during beta; classify all items before V1 release | Medium — systemic bugs may exist that testing did not catch | ✅ | — | — | Register created; items to be populated |
| 25 | Release and support process not documented for others | PARTIALLY COMPLETE | 35 beta-gate docs in `docs/beta/`; release process required Claude Code involvement; no support runbook for a non-developer operator | (a) Concise support runbook covering common issues; (b) Release checklist requiring no Claude Code; (c) Incident response steps; (d) Account recovery procedure; (e) Named support ownership | High — if the developer is unavailable, no one else can run a deployment or diagnose a failure | ✅ | ✅ | ✅ | — |

---

## Gap Counts by Classification

| Classification | Count |
|---|---|
| COMPLETE WITH EVIDENCE | 0 |
| PARTIALLY COMPLETE | 15 |
| NOT IMPLEMENTED | 7 |
| OBSOLETE | 0 |
| MANUAL OR POLICY DECISION REQUIRED | 3 |

---

## V1 Gate Summary (7WG Operational V1)

Gaps that must be **closed or formally deferred with risk acceptance** before 7 Wing Operational V1:

| # | Gap | V1 requirement |
|---|---|---|
| 1 | Legacy text cleanup | Fix stale "Annual Program" link |
| 2 | Visual/session unification | Nav/session/logout unified between frontends |
| 3 | Location data model | Decision recorded; migration plan written |
| 4 | Facilitator leave cross-exposure | Leave visible in Main TMS |
| 5 | Individual accountability | Options presented; decision recorded (even if deferred) |
| 6 | Optimistic locking | Implemented on critical records; regression tests pass |
| 10 | Report catalogue | Tier 1 defined and implemented |
| 11 | Year rollover | E2E browser test passes; procedure documented |
| 12 | Playwright E2E | Core workflow coverage: parade nights, scheduling, facilitators, reports |
| 17 | Monitoring | Correlation IDs in production logs |
| 18 | Maintenance mode | Login-block option implemented |
| 19 | Session revocation | Forced logout on code reset |
| 20 | CSRF assessment | `COOKIE_SAMESITE=none` verified and documented |
| 21 | Backup/restore | Key custody complete; DR rehearsal run |
| 24 | Beta feedback | Register populated; all critical/high items resolved |
| 25 | Support runbook | Written and reviewed by a non-developer |

---

## Level B Gate Summary (Second Wing Pilot)

Additional requirements beyond Level A:

| # | Gap | Level B requirement |
|---|---|---|
| 7 | 7WG hardcodes | All Wing-specific strings removed from code |
| 8 | Wing onboarding | Idempotent onboarding script; dry-run report; rollback |
| 9 | Multi-Wing reports | Verified with synthetic second Wing in staging |
| 14 | Load testing | 250-user test with multi-Wing data |
| 15 | Rate limiting | Non-login endpoints evaluated; implemented if needed |
| 16 | Background jobs | Heavy operations measured; async dispatch if needed |
| 22 | Pen test | External pen test recommended before second real Wing |
| 23 | Data governance | All decisions resolved |
| 5 | Individual accountability | Approved model implemented |
| 2 | Visual unification | Shared design tokens complete |

---

## Level C Gate Summary (National Readiness)

Additional requirements beyond Level B:

| # | Gap | National requirement |
|---|---|---|
| 13 | Accessibility | Axe automation pass; keyboard-only workflows |
| 14 | Load testing | 500-user test; degradation and failure points documented |
| 16 | Background jobs | Async dispatch implemented for heavy operations |
| 17 | Monitoring | Full alerting stack operational |
| 22 | Pen test | External pen test REQUIRED (not just recommended) |
| 23 | Data governance | National governance approval |
| 10 | Reports | Tier 2 and Tier 3 defined and implemented |

---

## Decision Log

| Gap # | Decision | Date | Authority |
|---|---|---|---|
| 3 | Adopt `training_areas` as canonical location model; `planning_locations` to be migrated and deprecated | 2026-07-16 (proposed) | Pending confirmation |
| 5 | Individual accountability model (Option A vs B) | — | MANUAL APPROVAL REQUIRED |
| 22 | External pen test budget and scope | — | MANUAL APPROVAL REQUIRED |
| 23 | All data governance decisions | — | MANUAL GOVERNANCE REQUIRED |
