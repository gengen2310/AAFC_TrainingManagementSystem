# AAFC TMS — Beta Feedback Register

Phase 2 — Next-Stage Development Program.
Created 2026-07-16. Populated during and after the 7 Wing beta period.

---

## Purpose

This register collects and classifies all feedback received during the 7 Wing beta.
Every item must be classified before Version 1 is released.

Not every request becomes a feature. Systemic problems that affect multiple squadrons
or prevent completion of the standard planning workflow take priority.

---

## Classification Guide

| Class | Definition |
|---|---|
| **defect** | System does not behave as designed or documented |
| **data-problem** | Incorrect, missing or corrupted data in the system |
| **usability-problem** | System works but is confusing, slow or error-prone for users |
| **training-issue** | User was not familiar with correct workflow; no code change needed |
| **permission-problem** | User could not access something they should, or accessed something they should not |
| **performance-problem** | System was too slow, timed out, or became unavailable |
| **enhancement** | New capability requested beyond current design |
| **not-reproducible** | Cannot reproduce with provided information |
| **duplicate** | Already captured as another entry in this register |
| **policy-decision** | Requires organisational decision, not a technical change |

---

## Severity Levels

| Severity | Definition |
|---|---|
| **critical** | Data loss, security breach, system unavailable, planning workflow impossible |
| **high** | Core workflow broken for one or more roles; significant data integrity risk |
| **medium** | Workflow degraded; workaround available; affects multiple users |
| **low** | Minor inconvenience; cosmetic; single-user issue |
| **enhancement** | No current system impact; new capability request |

---

## Release Targets

| Target | Meaning |
|---|---|
| **v1.0** | Must be resolved before 7 Wing Operational V1 release |
| **v1.1** | Planned for first post-v1.0 update cycle |
| **level-b** | Required before second-Wing pilot |
| **national** | Required before National release |
| **backlog** | Low priority; no fixed release target |
| **deferred** | Explicitly deferred with accepted risk |
| **closed-no-action** | Closed without change (training issue, duplicate, not reproducible, policy) |

---

## Status Values

`open` · `in-progress` · `resolved` · `closed` · `deferred`

---

## Register

### BF-001 — (template — replace with first real item)

| Field | Value |
|---|---|
| ID | BF-001 |
| Date received | |
| Reporter | |
| Squadron | |
| Role | |
| Page / workflow | |
| Description | |
| Expected result | |
| Actual result | |
| Screenshot/evidence | |
| Severity | |
| Frequency | |
| Affected users | |
| Root cause | |
| Proposed action | |
| Release target | |
| Status | open |
| Classification | |

---

## Summary Table (update as items are received)

| ID | Date | Squadron | Role | Page | Severity | Class | Release target | Status |
|---|---|---|---|---|---|---|---|---|
| BF-001 | | | | | | | | |

---

## Closure Criteria

All `critical` and `high` items must be `resolved` or `deferred` (with explicit risk acceptance)
before 7 Wing Operational V1 may be released.

All `medium` items affecting multiple squadrons or a core planning workflow must be resolved
or formally deferred before V1.

`low` and `enhancement` items may remain `open` for V1 with documentation.

The beta coordinator reviews this register before any GO/NO-GO decision.
