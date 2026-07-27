# AAFC TMS — Account and Role Release Matrix

Phase 7 (Operational Release Gate). All roles, their permissions, and readiness status for beta release.
Created: 2026-07-14.

---

## Purpose

This document defines which roles are released to which users, what access they have, and what account creation actions are required before releasing codes.

---

## Role Definitions

| Role | Scope | Navigation | Write access |
|---|---|---|---|
| `sqn_general` | Single squadron | Dashboard, Schedule, Wing Calendar, Training Sessions, CEA Curriculum | Read-only most; can create attendance records |
| `sqn_admin` | Single squadron | Full squadron nav: all of sqn_general + Accounts, Parade Nights, Planning Year, Settings | Full write for their squadron |
| `wing_admin` | Wing (all squadrons in wing) | Wing overview, Wing Calendar, Wing accounts, Wing facilitators | Wing-level; cannot write to squadron operational data |
| `wing_viewer` | Wing (read-only) | Same nav as wing_admin, no write buttons | Read-only |
| `national_admin` | All wings + all squadrons | National overview, national accounts, all data | National-level write |
| `national_viewer` | National (read-only) | Same nav as national_admin, no write buttons | Read-only |
| `auditor` | Cross-organisation audit log | Audit log, system summary | Read-only audit data |
| `system_admin` | System console | System console, maintenance, backup log, scope map | System-level; no operational data access |

---

## Roles Released in Beta

| Role | Released in beta? | Max accounts | Notes |
|---|---|---|---|
| `sqn_general` | YES | ~5 per squadron × 16 = ~80 | Primary user class; receives access code via release communication |
| `sqn_admin` | YES | 1–2 per squadron × 16 = ~32 | Squadron setup and account management |
| `wing_admin` | YES | 1–2 per wing | Wing oversight |
| `wing_viewer` | YES | Optional — as needed | Passive observers |
| `national_admin` | YES | 2 | AAFC national program staff |
| `national_viewer` | YES | Optional | Passive national observers |
| `auditor` | YES | 1 | Audit log reviewer |
| `system_admin` | YES — restricted | 1 | System operator only; not distributed to beta users |

---

## Account Pre-Creation Requirements

Before release:

| Action | Responsible | Status |
|---|---|---|
| Create `system_admin` account | System engineer | PENDING — requires production deployment of DEFECT-001 fix + staging confirmation |
| Create 16 `sqn_admin` accounts (one per squadron) | System engineer or National Admin | PENDING |
| Create Wing admin account(s) | System engineer or National Admin | PENDING |
| Create National Admin accounts (2) | System engineer | PENDING |
| Create UAT tester accounts (4 from `37_user_acceptance_test_plan.md`) | System engineer | PENDING |
| Verify each account in staging before mirroring in production | System engineer | PENDING |
| Distribute access codes via secure channel (one-time display only) | Release controller | PENDING |
| Record which code belongs to which person (separate secure register) | Release controller | PENDING |
| Confirm audit log records each account creation | Release controller | PENDING |

---

## Per-Squadron Account Readiness

| Squadron | sqn_admin created? | sqn_general count | Codes distributed? |
|---|---|---|---|
| 1 | PENDING | PENDING | PENDING |
| 2 | PENDING | PENDING | PENDING |
| 3 | PENDING | PENDING | PENDING |
| 4 | PENDING | PENDING | PENDING |
| 5 | PENDING | PENDING | PENDING |
| 6 | PENDING | PENDING | PENDING |
| 7 | PENDING | PENDING | PENDING |
| 8 | PENDING | PENDING | PENDING |
| 9 | PENDING | PENDING | PENDING |
| 10 | PENDING | PENDING | PENDING |
| 11 | PENDING | PENDING | PENDING |
| 12 | PENDING | PENDING | PENDING |
| 13 | PENDING | PENDING | PENDING |
| 14 | PENDING | PENDING | PENDING |
| 15 | PENDING | PENDING | PENDING |
| 16 | PENDING | PENDING | PENDING |

---

## Access Code Distribution Rules

**Derived from system security invariants — do not modify:**

1. Access codes are one-time display only. After creation, the code cannot be re-shown. Record it immediately after creation.
2. Access codes must be distributed via a private channel (not publicly visible email threads, shared documents, or chat channels).
3. Access codes must NOT be embedded in any document, email body, or message that could be forwarded or logged publicly.
4. If a code is compromised (shared accidentally, displayed publicly, sent to wrong person): reset the account immediately via the Accounts page. Issue a new code. Audit log will record the reset.
5. A separate register of "account → code → recipient" must be maintained offline (not in this document). This register is a sensitive operational document.

---

## Role Change Procedure During Beta

If a user's role needs to be changed after account creation:

1. Wing Admin or National Admin logs into the TMS
2. Navigates to Accounts page
3. Changes the role for the relevant account
4. The change takes effect on the user's next API call (existing session updates within ~30 seconds)
5. The role change is recorded in the audit log

**Do not** delete and recreate accounts to change roles — this loses the access code and creates a new account in the audit log.

---

## Suspended / Locked Accounts

If an account must be suspended:

- A Wing Admin or National Admin can lock the account via the Accounts page
- Locked accounts cannot log in; existing sessions expire at next JWT refresh (typically within 15 minutes)
- The lockout is audited
- Accounts locked after 5 failed login attempts are automatically released after 30 minutes, or can be manually unlocked by a Wing Admin

---

## Post-Release Account Audit

At T+24 hours:

1. National Admin or Wing Admin reviews the Accounts page
2. Confirm all created accounts show at least one login in the audit log
3. Identify any accounts that were not used — follow up with the user
4. Identify any unexpected accounts (not in the pre-release list) — escalate
5. Record findings in the incident log

**Matrix release status**: PENDING — all accounts to be created and verified before codes are distributed.
