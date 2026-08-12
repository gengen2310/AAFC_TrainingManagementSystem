# AAFC TMS — V1 Go/No-Go Pre-Flight Checklist

**Audience:** System Administrator, Wing SOCAD, Commanding Officer
**Purpose:** Single-document checklist covering all human-required steps before declaring
7 Wing Operational V1 GO. Complete in order — each section has a sign-off line.
**Created:** 2026-08-12

All technical gate items (tests, migrations, code changes) are already complete as of
commit `44cfa90` (2026-08-12). The items below are the **human-action gates** that
cannot be performed by the development team.

---

## How to Use This Checklist

Work through sections in order. Each item has a ☐ checkbox. Check it when complete.
Sign each section with your name and date before proceeding to the next.

If an item reveals a problem, **do not proceed** to the next section. Raise it with the
developer on-call and document it in the beta feedback register
(`docs/next-stage/02_beta_feedback_register.md`).

---

## Section A — Individual Accountability Decision (Gap 5)

**Reference:** `docs/next-stage/05_individual_accountability_options.md`
**V1 requirement:** Decision recorded (Option C = defer is acceptable for V1)

- ☐ **A1** Read `05_individual_accountability_options.md` — understand Options A, B, and C.
- ☐ **A2** Fill in the Decision Record at the bottom of that document:
  - Choose one: `Option A` (individual accounts) / `Option B` (claimed name) / `Option C` (defer to Level B)
  - Recommended for V1: Option C (defer) — the 7WG team is small; the CO can resolve disputes by direct inquiry
  - Record the authorised person's name, role, and date
- ☐ **A3** If Option A or B is chosen, notify the developer on-call — implementation work is required before V1 release
- ☐ **A4** If Option C is chosen, confirm the organisation accepts that audit records identify role-level accounts only, not named individuals, for the duration of V1 operations

**Section A sign-off:**
Name: _______________________________ Role: _________________________ Date: __________

---

## Section B — CSRF Production Verification (Gap 20)

**Reference:** `docs/next-stage/20_csrf_assessment.md`
**V1 requirement:** Production Railway env vars confirmed; cross-origin session tested

> **Important:** Do not ask Claude Code or any AI to perform these steps. Steps B1–B3
> involve reading production environment variables. Steps must be performed directly
> by the System Administrator in the Railway dashboard.

- ☐ **B1** Open Railway dashboard → project `exemplary-emotion` → `production` environment → `aafc-tms-backend` service → **Variables** tab.
  - Confirm `COOKIE_SAMESITE=none` is set (the code default is `lax` — without this env var, the Planning Workspace cross-origin session fails)
  - Confirm `COOKIE_SECURE=true` is set

- ☐ **B2** While on the Variables tab:
  - Confirm `CORS_ALLOWED_ORIGINS` does not contain `*` (wildcard)
  - Confirm `CORS_ALLOWED_ORIGINS` lists only the two production frontend Railway domains

- ☐ **B3** Confirm `ENVIRONMENT=production` (not `staging` or `development`) is set in the production backend service

- ☐ **B4** Manual cross-origin session test:
  1. Open the production Main TMS frontend in a browser
  2. Log in with the system_admin access code
  3. Click "Planning Workspace ↗" in the navigation
  4. Planning Workspace opens in a new tab — confirm you are logged in (session is active, not showing a login screen)
  5. If the Planning Workspace shows a login screen, `COOKIE_SAMESITE` is not set correctly — stop here

**Section B sign-off:**
Name: _______________________________ Role: _________________________ Date: __________

---

## Section C — Backup Key Custody (Gap 21 — Part A)

**Reference:** `deployment/backup-dr.md`
**V1 requirement:** GPG key generated and stored; GitHub Secrets set; backup confirmed running

> The GPG public key is already committed to the repository (`.github/backup-public-key.asc`).
> Steps C1–C3 verify the private key is secure and GitHub Secrets are set.

- ☐ **C1** Confirm the GPG private key (`/tmp/backup-private-key.asc` or equivalent) is saved to **offline encrypted storage** (encrypted USB drive, offline password manager export, or equivalent air-gapped medium). The private key and passphrase must NOT be stored only on a machine connected to the internet.

- ☐ **C2** Confirm the GPG passphrase is recorded in a **password manager** accessible to the named backup key custodian. Record the custodian's name: _________________________________

- ☐ **C3** Open GitHub → Repository → **Settings** → **Secrets and variables** → **Actions**. Confirm all four secrets are present (values are hidden; only existence needs to be confirmed):
  - ☐ `BACKUP_GPG_PRIVATE_KEY`
  - ☐ `BACKUP_GPG_PASSPHRASE`
  - ☐ `PROD_DATABASE_BACKUP_URL` (Railway production Postgres public proxy URL)
  - ☐ `SUPABASE_DB_URL` (Railway staging Postgres public proxy URL — despite the name, this points to the Railway staging PostgreSQL proxy, not a Supabase service; the name is a historical artifact)

  If any secret is missing: follow `deployment/backup-dr.md § Step 4` to add it.

- ☐ **C4** Trigger a manual backup to confirm setup:
  1. GitHub → Actions → **Backup PostgreSQL — Production — Daily** → **Run workflow** → select `main` → **Run workflow**
  2. Wait for completion (typically 2–5 minutes)
  3. Confirm the run passes and an artifact appears under the run's **Artifacts** section
  4. Record the run ID here: _______________________________ Date: ___________

- ☐ **C5** Trigger a manual restore test:
  1. GitHub → Actions → **PostgreSQL Restore Test — Production — Weekly** → **Run workflow** → select `main` → **Run workflow**
  2. Wait for completion (typically 5–10 minutes)
  3. Confirm the final line of the run log reads: `RESTORE VERIFICATION PASSED`
  4. Record the run ID here: _______________________________ Date: ___________

**Section C sign-off:**
Name: _______________________________ Role: _________________________ Date: __________

---

## Section D — Disaster Recovery Rehearsal (Gap 21 — Part B)

**Reference:** `docs/next-stage/19_disaster_recovery_rehearsal.md`
**V1 requirement:** Full DR rehearsal run; RTO measured and recorded

This section requires:
- Docker Desktop installed and running
- `gpg` installed (`gpg --version`)
- `pg_restore` installed (`pg_restore --version`)
- A staging backup artifact from Section C Step C4 (or a recent automated run)

Follow `docs/next-stage/19_disaster_recovery_rehearsal.md` Parts 1–4 in full:

- ☐ **D1** Part 1 — Trigger and download a staging backup artifact (Steps 1–2 in the rehearsal doc)
- ☐ **D2** Part 2 — Restore to a disposable Docker PostgreSQL container (Steps 3–6)
- ☐ **D3** Part 3 — Smoke test the restored database (Steps 7–8): confirm `/api/health/ready` returns `{"status":"ready"}` against the local restored instance
- ☐ **D4** Part 4 — Tear down and record:
  - Stop the Docker container (`docker stop dr-rehearsal-pg`)
  - Delete the rehearsal directory
  - Record the result in the Evidence Table at the bottom of `19_disaster_recovery_rehearsal.md`:

  | Date | Run ID | Artifact size | Restore duration | Squadrons | Smoke | Operator |
  |---|---|---|---|---|---|---|
  | | | | | | | |

**Section D sign-off:**
Name: _______________________________ Role: _________________________ Date: __________

---

## Section E — Data Governance Decisions (Gap 23)

**Reference:** `docs/beta/46_data_governance_and_approval.md`
**V1 requirement:** All 9 decisions answered by an authorised person

> **Authority required:** These decisions require a person with organisational authority
> over the AAFC TMS program (Commanding Officer, SOCAD, or delegated data custodian).
> Claude Code cannot make these decisions.

Open `docs/beta/46_data_governance_and_approval.md` and fill in the decision fields for:

- ☐ **E1** Personal information policy — may real cadet names / staff names / training history be entered during V1 operations?
- ☐ **E2** Audit record access — are the current audit-visible roles correct for your organisation's accountability requirements?
- ☐ **E3** Data retention — how long should training records, audit records, and backup artifacts be retained?
- ☐ **E4** Screenshot handling — what is the approved procedure for screenshots sent to support?
- ☐ **E5** Database ownership — is Railway an approved data hosting provider? Is the data residency location acceptable?
- ☐ **E6** Recovery credential ownership — who holds the Railway account credentials and GPG backup key post-release?
- ☐ **E7** Release approval authority — who has the authority to approve the production release? (Named person required)
- ☐ **E8** Support responsibility — who handles first-line support, technical support, security escalation, and after-hours emergency?
- ☐ **E9** Post-beta data treatment — will beta data migrate to production, be purged, or be treated differently?

Confirm all 9 decisions are recorded: ☐ All 9 filled in

**Section E sign-off:**
Name: _______________________________ Role: _________________________ Date: __________

---

## Section F — Beta Feedback Register (Gap 24)

**Reference:** `docs/next-stage/02_beta_feedback_register.md`
**V1 requirement:** All feedback received during 7WG beta classified and critical/high items resolved

- ☐ **F1** Collect all feedback received from 7WG beta testers (email, in-person, Slack, etc.) and enter each item as a register row in `02_beta_feedback_register.md`

- ☐ **F2** Classify each item using the severity and class definitions in the register:
  - Severity: `critical` / `high` / `medium` / `low` / `enhancement`
  - Class: `defect` / `usability-problem` / `training-issue` / `enhancement` / etc.

- ☐ **F3** Confirm: no `critical` or `high` items remain `open` or `in-progress`. Every `critical`/`high` item must be:
  - `resolved` (fix deployed to staging, evidence recorded), or
  - `deferred` with a signed risk acceptance from the commanding officer

- ☐ **F4** Confirm all `medium` items affecting multiple squadrons or a core workflow are resolved or formally deferred

- ☐ **F5** Summary table is up to date — counts of items by severity and status:

| Severity | Open | In-progress | Resolved | Deferred | Closed |
|---|---|---|---|---|---|
| critical | | | | | |
| high | | | | | |
| medium | | | | | |
| low | | | | | |
| enhancement | | | | | |

**Section F sign-off:**
Name: _______________________________ Role: _________________________ Date: __________

---

## Section G — Final GO / NO-GO Declaration

All sections above must be signed before completing this section.

**Pre-declaration checks:**
- ☐ Sections A–F are all signed
- ☐ A fresh production database backup has been taken within the last 2 hours and the artifact confirmed in GitHub Actions (record the run ID: _________)
- ☐ Developer on-call has confirmed: test suite passes (1553+ tests), staging deploy is current, no known regressions
- ☐ The production AAFC TMS frontend and backend are confirmed running (`/api/health/ready` returns `{"status":"ready"}` with `squadrons` matching the expected production org count — confirm the expected count with the developer on-call before checking)
- ☐ A final D7 smoke test has been completed against production (see `docs/beta/D7_smoke_test_checklist.md`)

**Declaration:**

☐ GO — All gate items are satisfied. I authorise the 7 Wing Operational V1 release.

☐ NO-GO — The following items must be resolved before release:
```
(List blocking items here)
```

**Release authority (must be the person named in E7 above):**
Name: _______________________________ Role: _________________________ Date: __________
Signature: _______________________________

---

## Section H — Post-Release Actions (within 7 days of V1 go-live)

These are not V1 gates but must be completed within 7 days of go-live:

- ☐ **H1** Change all staging access codes used during the external pen test engagement (when that occurs — Level B)
- ☐ **H2** Fill in named ownership table in `docs/next-stage/25_support_runbook.md` Part 1 (System Admin, Wing Admin, Developer on-call, Railway account owner, Backup key custodian, GitHub repo admin)
- ☐ **H3** Confirm the weekly restore test GitHub Action ran and passed in the first week of production operation
- ☐ **H4** Schedule the first quarterly DR rehearsal: date ___________
- ☐ **H5** Communicate to 7WG beta testers: "V1 is live; please report any issues via [contact]"
