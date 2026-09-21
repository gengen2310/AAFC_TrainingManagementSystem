# Production Readiness Audit — AAFC TMS v17.1

**Branch:** `release/final-production-qualification`  
**HEAD:** `bedb6b65`  
**Date:** 2026-09-21  
**Alembic head:** `7f61608fa538` (single head, confirmed)

---

## Summary

All P0 and P1 automated blockers are RESOLVED. Three human-gated items remain before
TECHNICAL GO can be declared (B-17 in progress, B-18 and B-19 pending operator action).

| Category | Result |
|---|---|
| Backend tests | ✅ 2456 pass, 12 skip, 0 fail |
| TypeScript typecheck | ✅ 0 errors |
| Frontend build | ✅ clean |
| npm audit (prod deps) | ✅ 0 HIGH/CRITICAL |
| Security greps (4 checks) | ✅ 0 matches |
| Alembic (single head) | ✅ `7f61608fa538` |
| E2E CI (6/6 jobs) | ✅ all passing |
| Accessibility audit (B-13) | ✅ 0 hard WCAG violations |
| Responsive matrix (B-14) | ✅ 7 viewports (partial — zoom P3) |
| Migration rehearsal (B-15) | ✅ 70/70 forward/rollback confirmed |
| Issue #62 DoD (7 items) | ✅ all browser-verified |
| HARD-09 native dialogs | ✅ 0 live call-sites |
| `/code-review ultra` (B-17) | 🔄 IN PROGRESS |
| Staging load test (B-18) | ⏳ HUMAN GATE |
| Executive GO/NO-GO (B-19) | ⏳ HUMAN GATE |

---

## Blocker Map — Closure Record

### P0 Blockers (all RESOLVED)

| ID | Description | Fix | Evidence |
|---|---|---|---|
| B-01 | CLASS-06 pw-nc-classes / E2E CI | Option B: removed test; documented USER-AUTHORISED REMOVAL | commit `86c3011e` |
| B-02 | session-status-reason-tags.spec.ts (firefox) | `P.currentYearId = null` + term reset + 10s timeout | commit `86c3011e` |
| B-03 | main-tms.spec.ts API shape + race (chromium) | flat array shape; `{ timeout: 15000 }` on `#m-add-fac` | commit `86c3011e` |
| B-04 | `#m-text-input` not closing in webkit | re-entry guard + promise resolution fix | commit `2abb12bb` |
| B-20 | SYN-H01: `COOKIE_SAMESITE=none` Railway env var | Verified Railway staging env var set; `Set-Cookie` confirms `SameSite=none; Secure` | curl evidence 2026-09-21 |

### P1 Blockers (all RESOLVED)

| ID | Description | Fix | Evidence |
|---|---|---|---|
| B-05 | Add Cadet not browser-verified | Browser: `openAddCadetModal` 4-step PASS | session 2026-09-20 |
| B-06 | CEA import error not browser-verified | Browser: missing-header CSV → actionable error PASS | session 2026-09-20 |
| B-07 | Print workflow not live-verified | Browser: session → print → timing chain verified | session 2026-09-20 |
| B-08 | Outcome entry duplication not verified | Browser: single canonical Needs Attention queue confirmed | session 2026-09-20 |
| B-09 | Unit Setup ↔ PW not live-verified | Browser: TMS create/edit/archive → PW Year 2026 reflection PASS | session 2026-09-20 |
| B-11 | apple-design pass not run | G1 contrast fixes applied (5 findings); G3-G12 visual PASS | commit `74410440` |
| B-12 | frontend-design rubric not run | Full rubric spot-check PASS 2026-09-20 | commit `74410440` |
| B-13 | 15 accessibility gates unmeasured | Structural audit: 0 hard WCAG violations across 5 pages; PW axe WCAG 2.1 AA via spec | commit `7f66e812` |
| B-14 | Responsive matrix not run | 7-viewport spec; B-24 390px overflow fixed | commit `7f66e812` |
| B-15 | Migration rehearsal doc stale vs HEAD | Alembic head unchanged at `7f61608fa538`; doc updated | commit `7f66e812` |
| B-21 | `POST /api/cadets` missing cross-squadron fence | Added foreign-squadron `service_number` check → HTTP 409 | commit `b51fcf98` |
| B-22 | `POST /api/cadets` omits `created_by` | `created_by=p.user_id` added to `Cadet(...)` constructor | commit `b51fcf98` |
| B-23 | Activity override modal doesn't close after Clear | `closeModal()` call added after Clear handler | commit `93558780` |
| B-24 | 390px CSS overflow (411 > 390) | Padding/width fix in connected-frontend CSS | commit `93558780` |
| B-25 / K-001 | 5 spike-alert tests deselected in deploy-staging.sh | All 5 tests now PASS; `deploy-staging.sh` has no deselections | confirmed 2026-09-21 |
| B-26 | Year selector inconsistent across surfaces | Planning Checks year selector wired to consistent state | commit `5370e2d3` |
| DES-M01 | Planner cell type below 9px minimum (7px/8px) | Raised 4 inline styles to 9px in planner cell renderer | commit `c22b90c9` |
| DES-M02 | Focus ring consistency (outline:none without replacement) | All 5 outline:none overrides verified to have box-shadow replacements | code audit `bedb6b65` |
| DES-M06 | :focus-visible coverage completeness | Catch-all + per-component rules comprehensive; PASS | code audit `bedb6b65` |
| DES-H03 | Touch target sizes | --ctl-min:44px token enforced on all button variants via min-height/min-width | code audit `bedb6b65` |
| K-008 | Nullable stage_id on sessions | Stale column reference; session_audience.training_class_id = 0 NULL rows; dev orphans are seed artifact | code audit `bedb6b65` |

### P2 Blockers (resolved)

| ID | Description | Fix |
|---|---|---|
| B-10 | Matrix dead DOM/JS/CSS not removed | Dead code removed (`#curr-matrix-view`, `openCurrMatrix()`, CLASS-MATRIX-01 CSS) | commit `93558780` |

### Human Gates (pending)

| ID | Description | Required action |
|---|---|---|
| B-17 | `/code-review ultra` | **IN PROGRESS** 2026-09-21 — incorporate findings before TECHNICAL GO |
| B-18 | Staging: load test + backup + rollback rehearsal | Operator: run `deploy-staging.sh`, then load test script, then backup/restore drill |
| B-19 | Executive GO/NO-GO | Sign-off on exact commit `7f66e812` (or post-ultrareview fix SHA) |
| B-27 | Fresh backup immediately post-production deploy | Take backup before declaring production healthy (existing backup at incompatible schema) |

---

## Test Pyramid

| Layer | Count | Status |
|---|---|---|
| Backend pytest | 2456 pass, 12 skip | ✅ |
| vitest (frontend unit) | 144 pass, 21 files | ✅ |
| E2E connected (45 specs) | All passing, 3 browsers | ✅ |
| E2E PW (14 specs incl. axe + responsive) | All passing | ✅ |

---

## Security Verification

All four security greps return 0 matches (run 2026-09-21):

```
grep -Rc -E "your unit only|Controlled access for training" connected-frontend backend
grep -Rc -E "View current code|Show access code|Reveal code|Display existing code" connected-frontend backend
grep -Rc -E "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code|localStorage" connected-frontend
grep -Rc -E "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend
```

---

## Migration Status

- Single Alembic head: `7f61608fa538`
- Chain rehearsed 70/70 forward + 70/70 rollback against PostgreSQL (see `docs/final/09-migration-rehearsal.md`)
- `deploy-staging.sh` step 10 re-rehearses the full chain before every staging/production deploy
- **B-27 risk**: Production DB backup is at schema revision `a4e9507a9c51` (missing `session_audiences`). Take a fresh backup immediately after production deploy and before declaring healthy.

---

## Staging Deploy Command

```bash
STAGING_RESCUE=1 bash scripts/deploy-staging.sh
```

(from source repo root, with Railway env vars set; requires `RAILWAY_TOKEN` and service IDs)

---

## Post-ultrareview

If B-17 (`/code-review ultra`) surfaces P0/P1 findings, fix them, commit, push, and update the HEAD reference above before proceeding to B-18 staging deploy.

The commit SHA submitted to human gates should be the **post-ultrareview-fix SHA**, not `7f66e812`.
