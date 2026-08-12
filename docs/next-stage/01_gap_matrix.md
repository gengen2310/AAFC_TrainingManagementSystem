# AAFC TMS — Next-Stage Gap Matrix

Phase 1 — Next-Stage Development Program.
Created 2026-07-16. Verified against `43b880c`. Last updated 2026-08-12 against `cf9a377` (main branch).

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
| 1 | Legacy page retirement | COMPLETE WITH EVIDENCE | Stale "Annual Program" text removed; `nav('planning-year')→'activities'` redirect confirmed working; orphan JS audited | — | Low | ✅ done | — | — | — |
| 2 | Main TMS / Planning Workspace visual unification | PARTIALLY COMPLETE | Nav/session/logout unification DONE: Planning Workspace has "← Main TMS" link (`aafc-tms-base` meta); connected-frontend has "Planning Workspace ↗" nav; cross-session cookie handoff works (`SameSite=None`); `token_version` revocation shared across both | Shared design tokens (CSS variable names differ: `--blue` vs `--aafc-blue`; same underlying palette) — Level B requirement, not Level A | Medium — users experience two products | ✅ nav/session/logout DONE | ✅ complete design tokens | ✅ complete | — |
| 3 | TrainingArea vs PlanningLocation overlap | COMPLETE WITH EVIDENCE | Decision recorded in `04_canonical_data_model.md`; `training_areas` is canonical; `planning_locations` inert (no new writes); fallback resolver in `planning.py:1600` bridges legacy room IDs | Phase 2 (table drop) is Level B — not required for Level A since table is inert | Medium | ✅ decision + migration plan DONE | ✅ migration complete | ✅ | DECISION: adopt `training_areas` as canonical; deprecate `planning_locations` as adapter (see `04_canonical_data_model.md`) |
| 4 | Facilitator records across interfaces | COMPLETE WITH EVIDENCE | One canonical `Facilitator` table; `PlanningFacilitatorLeave` supplement linked via `facilitator_id` FK; leave records fully exposed in Main TMS `page-facilitators` (`connected-frontend/index.html:8533–8597`: `_showAddFacLeaveForm`, `_submitFacLeave`, `_deleteFacLeave`) | — | Low | ✅ done | — | — | — |
| 5 | Individual accountability | PARTIALLY COMPLETE | Shared access codes only; `User.display_name` is a role name; `created_by` identifies role, not person; options documented in `05_individual_accountability_options.md` | Organisation must choose Option A (individual accounts) or defer; decision recorded even if deferred | High — cannot attribute actions to a person; audit is role-level only | ✅ options presented | ✅ implement approved model | ✅ enforce | **MANUAL APPROVAL REQUIRED** before implementation |
| 6 | Silent last-write-wins concurrency | COMPLETE WITH EVIDENCE | Phase 7 optimistic locking: `version` field on ParadeNight, ScheduledSession, PlanningYear, PlanningNotice; 409 Conflict on stale write; 22 concurrency regression tests in `test_concurrency.py`; committed `4d08c5e` | — | High | ✅ done | ✅ done | ✅ done | — |
| 7 | Operationally limited to 7 Wing (hardcoded strings) | COMPLETE WITH EVIDENCE | `/bootstrap-staging` (`system.py:433`) is fully parameterized: accepts `wing_code`/`sqn_code`/`sqn_name` body params, falls back to first active Wing/Squadron; display names generated from `wing.code`/`sqn.code` dynamically; `auth.py:21` uses generic "Wing SOCAD"; `seed_all.py` is 7WG-specific by design (synthetic demo data, not a production path) | `seed_all.py` Wing specifics are intentional demo data — onboarding new Wings uses `10_wing_onboarding_runbook.md` + `/bootstrap-staging`, not seed_all | Medium | ✅ done | ✅ done | ✅ done | — |
| 8 | Multi-Wing onboarding not automated | PARTIALLY COMPLETE | `backend/app/seeds/second_wing_seed.py`: idempotent Wing + 2 squadrons + 4 accounts + PlanningYear + 7 Canadian holidays; `DRY_RUN=1` preview mode; structured JSON onboarding report; audit log entries tagged `staging_onboarding`; staging-only (refused in production); rollback procedure documented in `10_wing_onboarding_runbook.md §7`; troubleshooting guide in §8 | No multi-Wing Wing-onboarding API (only CLI seed); full TZ field not in Wing model; §0 governance gate not yet passed for any second Wing | High | — | ✅ script + runbook | ✅ | See `10_wing_onboarding_runbook.md` |
| 9 | Wing and National reports show 7WG data only | PARTIALLY COMPLETE | Report RBAC correctly scopes by `wing_id`/`national_id`; no multi-Wing synthetic dataset exists to test cross-Wing aggregation | Synthetic second Wing in staging; verify Wing reports show only that Wing; verify National aggregates all Wings; verify no cross-Wing data leak in reports | High — unproven aggregation path | — | ✅ | ✅ | — |
| 10 | Incomplete report catalogue | PARTIALLY COMPLETE | 12 report endpoints implemented across 3 tiers (5 squadron, 5 wing, 2 national); Tier 1–3 catalogue documented in `09_report_catalogue.md` with per-report: scope, source, calculation, decision signals, permissions, performance target | Export (PDF/CSV) for Tier 1 reports; date-range filter; 2 wing endpoints not yet wired to UI cards; Tier 3 requires Level B multi-Wing data | Medium | ✅ Tier 1 defined | ✅ Tier 2 defined | ✅ Tier 3 defined | See `09_report_catalogue.md` |
| 11 | Year rollover not E2E proven | COMPLETE WITH EVIDENCE | Phase 8: 10/10 E2E tests in `test_year_rollover_e2e.py` (years 2161–2179; covers full round-trip, date-shift, holidays, idempotency, RBAC, operational sessions); operator procedure in `docs/next-stage/08_year_rollover_procedure.md`; committed `992dc34` | — | High | ✅ done | ✅ done | ✅ done | — |
| 12 | Playwright E2E coverage incomplete | PARTIALLY COMPLETE | 114 tests in 22 spec files (Phase 12 complete); covers auth, nav, dashboard, session lifecycle (cancel/reschedule/RBAC), cross-interface, holidays/resources, wing-proxy, parade nights, year rollover, facilitators, facilitator leave/archive/restore, reports, accessibility, session archive/restore, cadet class membership, planning conflicts, mission backlog, weekly program | Remaining: multi-Wing scope tests; Axe accessibility automation | High | ✅ core workflows done | ✅ multi-Wing | ✅ Axe | — |
| 13 | Accessibility automation | NOT IMPLEMENTED | No Axe or equivalent integration; no keyboard-only workflow test; no zoom/contrast test | Axe integration in Playwright; keyboard-only navigation for all core workflows; focus order; label coverage; colour contrast; 1280×720, 1024×768, 125% zoom | Medium — no AODA/WCAG evidence | — | ✅ | ✅ | — |
| 14 | Production-scale load testing | NOT IMPLEMENTED | 7 Wing beta: 100 users, 5 endpoints, P95=548ms, CONDITIONAL PASS; no multi-Wing or higher-user test | 250, 500, 800-user tests with synthetic multi-Wing data; establish max stable user count, degradation point, recovery time; realistic workload (not just health checks) | High — unknown behaviour beyond 7WG scale | — | ✅ 250-user | ✅ 500-user | — |
| 15 | Distributed rate limiting | PARTIALLY COMPLETE | Per-IP sliding window `api_rate_limit` middleware (`main.py:200`) covers ALL non-exempt `/api/` endpoints; DB-backed `IpLoginAttempt` covers login specifically; both work across gunicorn workers via shared DB | Per-IP counter shared across Railway replicas only if they share the same DB connection — evaluate for multi-replica deployment; per-account limiting not implemented | Medium | ✅ done | ✅ evaluate multi-replica | ✅ implement if needed | — |
| 16 | Synchronous imports/exports/reports | PARTIALLY COMPLETE | Dispatcher pattern implemented: `POST /api/jobs/export` creates `JobStatus` record, tries Celery, falls back to sync (`dispatcher.py`); polling endpoint `GET /api/jobs/{id}` wired; streaming CSV/XLSX/PDF export routes functional; at 7WG scale all exports < 1s | Celery task (`generate_export`) is a stub — sync fallback records success without writing a real file; Redis not provisioned; no presigned-URL or object-storage path for large files; no frontend polling UI | Medium | ✅ measured (< 1s at V1 scale) | ✅ implement async file gen if load test shows timeouts | ✅ | — |
| 17 | Production monitoring and alerting | COMPLETE WITH EVIDENCE | Correlation IDs: `X-Request-ID` accepted from client or generated per-request, echoed in response, included in every access log line (`main.py:237–247`); structured JSON access log with method, path, status, duration, client IP, `req_id`; `X-Response-Time-ms` response header | Error-rate monitoring, login-failure alerting, backup-failure alerting, service restart alerting — Level B/C items | High | ✅ done | ✅ full alerting | ✅ | — |
| 18 | Maintenance mode limited | COMPLETE WITH EVIDENCE | Write-blocking + login-blocking both implemented: `maintenance_block_logins` SystemSetting + `_maint_cache["block_logins"]` (`main.py:15–41`); login endpoint gated when `block_logins=true`; audited; message and `block_reads` also configurable | (b) Expected return time via API; (c) Celery drain; (d) Frontend maintenance banner — Level B/C items | Low for 7WG | ✅ done | ✅ | ✅ | — |
| 19 | Session revocation limited | COMPLETE WITH EVIDENCE | `token_version` field on User model; JWT carries `tv` claim; `dependencies.py:117` raises 401 `session_revoked` if `tv ≠ user.token_version`; `auth.py:247` increments `token_version` on code reset, immediately invalidating ALL existing tokens for that user — no JTI blacklist or Redis required | On account disable/role change: incrementing `token_version` (same reset-code path) achieves the same effect; no automated hook yet — documented operator step | High | ✅ done | ✅ done | ✅ done | — |
| 20 | CSRF controls | PARTIALLY COMPLETE | CORS locked per environment (no wildcard); Bearer token architecture makes Planning Workspace CSRF-immune; cookie fallback mitigated by CORS; CSRF assessment documented in `20_csrf_assessment.md`; CSRF tokens assessed as not required | (a) Operator must confirm `COOKIE_SAMESITE=none` and `COOKIE_SECURE=true` in Railway production env vars — code default is `lax`; this is a production deployment checklist item | Medium — architecture is sound; production verification is a manual step | ✅ assessed + documented | ✅ | ✅ | See `20_csrf_assessment.md` |
| 21 | Backup and restore continuous verification | PARTIALLY COMPLETE | Daily backup + weekly restore workflows active; last proven runs documented; backup key custody pending (5 human actions); no quarterly restore rehearsal schedule | (a) Complete backup key custody (5 human actions); (b) Schedule quarterly restore rehearsal; (c) Run disaster recovery rehearsal in staging (service deletion, bad migration, restore from backup) | High — backup workflows exist but not rehearsed end-to-end for a genuine outage | ✅ key custody + DR rehearsal | ✅ | ✅ | — |
| 22 | External penetration testing | NOT IMPLEMENTED | No external pen test conducted; internal security tests (IDOR, auth, lockout, role bypass) pass at rc3 | Independent external penetration test covering auth, session, IDOR, Wing isolation, CSRF, XSS, import abuse, audit integrity, dependency scan | Critical for National — required before releasing beyond 7WG beta | — | ⚠️ recommended | ✅ required | **MANUAL APPROVAL REQUIRED** — budget and scope from org |
| 23 | Data governance, retention, named ownership | MANUAL OR POLICY DECISION REQUIRED | No formal governance decisions documented; `46_data_governance_and_approval.md` template exists with 9 pending decisions | Organisation must decide: personal data policy, cadet data policy, audit log access, retention periods, archive/delete requirements, incident reporting, production data ownership, support ownership, account removal | Critical — cannot store personal data without governance decisions | ✅ decisions made | ✅ | ✅ | **MANUAL GOVERNANCE DECISION REQUIRED** for every item |
| 24 | Beta feedback not collected | NOT IMPLEMENTED | No formal feedback register exists at program start | Create `02_beta_feedback_register.md` (done); populate during beta; classify all items before V1 release | Medium — systemic bugs may exist that testing did not catch | ✅ | — | — | Register created; items to be populated |
| 25 | Release and support process not documented for others | COMPLETE WITH EVIDENCE | 280-line operator runbook in `docs/next-stage/25_support_runbook.md`; covers common failure modes, Railway deploy procedure, account recovery, DR steps, incident response; written for non-developer operators | Named support ownership (a named person/role responsible for first response) — human decision | High | ✅ done | ✅ done | ✅ done | — |

---

## Gap Counts by Classification

| Classification | Count | Gaps |
|---|---|---|
| COMPLETE WITH EVIDENCE | 10 | 1, 3, 4, 6, 7, 11, 17, 18, 19, 25 |
| PARTIALLY COMPLETE | 10 | 2, 5, 8, 9, 10, 12, 15, 16, 20, 21 |
| NOT IMPLEMENTED | 4 | 13, 14, 22, 24 |
| OBSOLETE | 0 | — |
| MANUAL OR POLICY DECISION REQUIRED | 1 | 23 |

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
| 3 | Adopt `training_areas` as canonical location model; `planning_locations` to be migrated and deprecated | 2026-08-12 | Decision recorded in `docs/next-stage/04_canonical_data_model.md`; Phase 2 (table drop) deferred to Level B |
| 5 | Individual accountability model (Option A vs B): options presented in `05_individual_accountability_options.md`; Option C (defer to National) recommended for V1 | — | **MANUAL APPROVAL REQUIRED** — CO / Wing SOCAD / System Owner |
| 20 | CSRF mitigation: CORS + SameSite=None is sufficient; CSRF tokens not required given Bearer token architecture; assessed in `20_csrf_assessment.md` | 2026-08-12 | Decision recorded by program lead; production env var verification required before deployment |
| 22 | External pen test budget and scope | — | MANUAL APPROVAL REQUIRED |
| 23 | All data governance decisions | — | MANUAL GOVERNANCE REQUIRED |
