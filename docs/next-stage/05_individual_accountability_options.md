# AAFC TMS — Individual Accountability Options

**Audience:** Commanding Officer, System Administrator, Wing SOCAD
**Gap register:** Gap #5 (individual accountability)
**Prepared:** 2026-08-12
**Status:** OPTIONS PRESENTED — DECISION REQUIRED BEFORE IMPLEMENTATION

---

## Current State

AAFC TMS uses shared access codes per role per unit:
- One `sqn_admin` code shared by all administrators of 703 SQN
- One `sqn_general` (read-only) code shared by all general viewers
- One `wing_admin` code, one `wing_viewer` code, one `national_admin` code, etc.

The `created_by` field on records stores the role account's user ID (e.g.,
"sqn_admin of 703 SQN"), not the name or identity of the individual who made the change.

**What this means for audit:** The system can answer "which role changed this record and when"
but not "which specific person changed this record."

**Risk classification:** This is acceptable for the 7WG beta where there is a single small
team, but it prevents individual accountability and makes investigating a disputed change
impossible.

---

## Options

### Option A — Individual Accounts (email + PIN or passphrase)

Each staff member gets a personal account with a unique credential. The current shared-code
system is deprecated. Audit records identify the individual by name and account ID.

**How it would work:**
- Replace `AccessCode` table with user accounts: `email` + hashed `pin` (or passphrase)
- Onboarding: Wing SOCAD creates an account for each staff member, assigns their role
- Login: staff enter their email and PIN; receive a JWT scoped to their role
- Audit: all `created_by` fields reference the individual's account
- Account recovery: SOCAD resets the PIN (no self-service password reset needed at this phase)

**Pros:**
- Complete individual audit trail — every action is attributed to a named person
- A compromised credential affects one person, not the entire role
- Industry-standard model; familiar to staff used to work email/apps
- Enables per-person role changes without disrupting others
- Natural foundation for future MFA

**Cons:**
- Significant migration effort: all existing `User` model records must be replaced or
  extended; `created_by` history references old role accounts (irreversibly)
- Onboarding friction: every staff member needs an account created by the SOCAD
- More operational burden: accounts must be disabled when staff leave
- Requires a UI for account self-management or SOCAD management
- Migration to individual accounts would break any existing sessions

**Implementation effort:** High (2–3 sprints minimum; new Account model, new login flow,
SOCAD account management UI, migration script, historical audit caveat)

---

### Option B — Dual-Factor Identification (keep shared codes; add name capture at session start)

Keep the existing shared access-code system. Add a personal identifier capture at login: staff
enter the shared code plus a display name (their name or badge number). The display name is
stored in the JWT and recorded on every audit action.

**How it would work:**
- Modify login: after accepting the access code, prompt for "Your name (for audit records)"
- Store `claimed_name` in the JWT payload and `User` session
- On every audited action, record both `created_by` (role account) and `claimed_name`
- No changes to the `AccessCode` system, RBAC, or existing session mechanics

**Pros:**
- Minimal migration effort — no changes to database schema for existing records
- Maintains the simplicity of shared codes (tribal knowledge, easy onboarding)
- Audit trail improves from "which role" to "which role, claimed by [name]"
- Provides plausible accountability without full individual identity management

**Cons:**
- Not cryptographically verified — any user can claim any name
- Does not prevent credential sharing within a role
- Does not provide the ability to disable a single person's access without changing the
  shared code for everyone in that role
- "Claimed name" is a field of convenience, not a security control; a bad actor can
  trivially attribute their actions to a colleague

**Implementation effort:** Low (1 sprint: login form change, JWT claim addition, audit
log display update)

---

### Option C — No Change; Defer to National Decision

Accept role-level accountability as sufficient for the 7WG beta and document the limitation.
Revisit when National deployment is planned.

**Pros:** No implementation effort; no disruption to beta users
**Cons:** Audit records permanently cannot attribute actions to individuals during this period

**When this is acceptable:** 7WG beta with a small, known team and a commanding officer who
can resolve disputes by direct inquiry.

---

## Recommendation for 7WG Operational V1

**Recommended: Option C (defer) for V1, with Option A committed to before Level B.**

Rationale:
- The 7WG beta team is small and the CO can resolve any disputed action through direct inquiry
- Individual accountability is a prerequisite for Level B (multiple Wings) and National
- Option B (claimed name) provides no real security benefit and may give false confidence
- Option A is the right long-term answer; beginning the design now preserves the path

**Required decision before Level B activation:**
- Organisation must approve Option A or B before a second Wing is onboarded
- Option A requires a named project sponsor, timeline, and migration plan
- This decision cannot be deferred past Level B

---

## Decision Record

| Field | Value |
|---|---|
| Decision | To be recorded here after authorisation |
| Authorised by | MANUAL APPROVAL REQUIRED — Commanding Officer / Wing SOCAD / System Owner |
| Date | — |
| Option selected | — |
| Implementation sprint | — |
| Notes | — |
