# Quarterly DR Rehearsal Schedule

**Purpose:** Formalise the disaster-recovery rehearsal dates so the commitment is explicit, auditable, and assigned to a named role — not an intent that may be deferred indefinitely.

**Procedure:** `docs/next-stage/19_disaster_recovery_rehearsal.md`  
**Evidence table:** Appendix A of the procedure document (populated after each rehearsal).

---

## Schedule — 2026 Operational Year

| Quarter | Target window | Due date | Assigned to | Status |
|---|---|---|---|---|
| Q3 2026 (post go-live) | 2026-08-13 to 2026-08-27 | 2026-08-27 | System Admin | PENDING — first rehearsal (post-production-deploy) |
| Q4 2026 (Oct) | 2026-10-01 to 2026-10-15 | 2026-10-15 | System Admin | NOT YET SCHEDULED |
| Q1 2027 (Jan) | 2027-01-05 to 2027-01-19 | 2027-01-19 | System Admin | NOT YET SCHEDULED |
| Q2 2027 (Apr) | 2027-04-01 to 2027-04-15 | 2027-04-15 | System Admin | NOT YET SCHEDULED |

The Q3 2026 rehearsal is the first post-go-live test and should be completed within 2 weeks of the production deployment (2026-08-12). It is the DOC-06 evidence requirement for the Level A operational gate.

---

## Additional triggers (per procedure §When to Run)

These are not calendar rehearsals but must be run within 5 business days:

- After any backup credential rotation.
- After any major schema migration deployed to production.

---

## Escalation if missed

If a rehearsal is missed within its target window:

1. System Admin logs the miss and reason in the procedure's evidence table.
2. The next rehearsal is rescheduled within 30 days.
3. If two consecutive quarters are missed, the issue is escalated to the organisation's technical authority for governance review.

---

## How to update this schedule

After completing a rehearsal:

1. Update the status column in the table above to COMPLETE.
2. Record the run ID, RTO, and result in the evidence table at the bottom of `19_disaster_recovery_rehearsal.md`.
3. Add the next quarter's row if it is not already present.
