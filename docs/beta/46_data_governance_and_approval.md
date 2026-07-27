# AAFC TMS — Data Governance and Organisational Approval

Phase 13 (Operational Release Gate). Governance checklist and decisions required before release.
Created: 2026-07-14.

---

## Purpose

This document captures data governance decisions that must be made by authorised people — not by technology. Claude Code can prepare the system but cannot approve policy, accept organisational risk, or authorise access to real personal information.

---

## Personal Information in Beta

### What information may be entered during beta?

| Data type | Decision required | Notes |
|---|---|---|
| Real cadet names | **MANUAL APPROVAL REQUIRED** | The system has cadet records functionality. The organisation must decide whether real cadet names may be entered during beta. Default recommendation: use synthetic names (Cadet [Surname]) until the production environment is formally classified. |
| Real staff names (facilitators) | **MANUAL APPROVAL REQUIRED** | Facilitator records are used for scheduling. Recommend using real names for operational accuracy; confirm organisational authority to store staff names in this system. |
| Training history / attendance | **MANUAL APPROVAL REQUIRED** | Session attendance and completion are recorded. Confirm this is within the authorised scope of the system. |
| Medical or dietary information | NOT APPLICABLE | The TMS does not have fields for medical information. Do not enter medical information. |
| Financial information | NOT APPLICABLE | The TMS does not have fields for financial records. Do not enter financial information. |

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Who May See Audit Records

Audit records capture all privileged actions (who changed what, when). They are:
- Permanent (cannot be deleted or modified)
- Accessible to `system_admin`, Wing Admin, Wing Viewer, National Admin, National Viewer, and `auditor` roles
- Scoped to the organisation level of the viewer

**Decision required**: Is the audit log accessible to the correct set of roles for your organisation's accountability requirements? Should access be restricted further?

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Data Retention

| Item | Current behaviour | Decision required |
|---|---|---|
| Training records (sessions, curriculum) | Retained indefinitely unless manually archived/deleted | How long should training records be retained? Is there a mandated retention period? |
| Audit records | Retained indefinitely (no delete endpoint) | Is indefinite audit retention acceptable, or is there a required retention period? |
| Backup artifacts | 30-day retention in GitHub Actions (current workflow default) | Is 30 days sufficient? What is the minimum required for the organisation? |
| Access codes (hashed) | Retained until account is deleted | Is there a policy for account lifecycle and deletion? |

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Screenshot Handling

Users may take screenshots for support purposes. Screenshots may contain:
- Planning data (curriculum, parade nights, facilitator names)
- Access code entry fields (though codes themselves are not displayed)
- Cadet names if visible on screen

**Decision required**: What is the approved procedure for handling screenshots sent to support? Where may they be stored? Who may access them?

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Database Ownership

| Item | Current | Confirmation required |
|---|---|---|
| Database provider | Railway (managed PostgreSQL) | Is Railway an approved data hosting provider for this data? |
| Database location (region) | Railway default (US/EU depending on Railway plan) | Is the data residency location acceptable? |
| Database access | Railway account owners | Who is the authorised database owner? |

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Recovery Credential Ownership

GPG keys for backup decryption and Railway account credentials are currently held by the development team. Post-release:

- Who holds the Railway account credentials?
- Who holds the GPG backup key and passphrase?
- What is the handover process when the development team is no longer the primary operator?

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Release Approval Authority

**Who has the authority to approve the production release?**

This must be a named person with organisational authority over the AAFC TMS program.

**Release approval authority**: ___________________
**Position/role**: ___________________
**Approval date**: ___________
**Approval method** (e.g. email, signed document, in-person): ___________________

---

## Support Responsibility Post-Release

**Who is responsible for first-line support after release?**

| Role | Person | Contact |
|---|---|---|
| First-line support (access issues, general questions) | ___________________ | ___________________ |
| Technical support (system errors, data issues) | ___________________ | ___________________ |
| Security escalation | ___________________ | ___________________ |
| After-hours emergency | ___________________ | ___________________ |

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Post-Beta Data Treatment

After the beta period:

| Question | Decision |
|---|---|
| Will beta data be migrated to the permanent production system? | |
| Will beta data be purged at end of beta? | |
| Will squadrons be informed of what happens to their beta data? | |
| What defines "end of beta"? | |

**Decision**: ___________________
**Approved by**: ___________________ Date: ___________

---

## Governance Checklist Status

This document is **NOT COMPLETE** until all sections above have been answered by the authorised organisational decision-maker.

| Section | Status |
|---|---|
| Personal information policy | PENDING |
| Audit record access | PENDING |
| Data retention | PENDING |
| Screenshot handling | PENDING |
| Database ownership | PENDING |
| Recovery credential ownership | PENDING |
| Release approval authority | PENDING |
| Support responsibility | PENDING |
| Post-beta data treatment | PENDING |
