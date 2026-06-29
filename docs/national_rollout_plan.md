# National rollout plan
1. **Pilot (done as demo):** 7 Wing seeded — National HQ + 16 squadrons + role codes.
2. **Per-Wing onboarding:** create the Wing + its squadrons (seed pattern or migration), issue
   hashed access codes, set parade days/times per squadron. Nothing is 7-Wing-specific.
3. **Scale validation:** run `SCALE=full` stress seed against PostgreSQL; confirm dashboard
   and report timings against the performance targets.
4. **Frontend milestone:** ship the React/TS app (login → dashboards → curriculum → parade →
   reports → proxy) with Playwright/Axe.
5. **Async milestone:** enable Celery/Redis for heavy imports/exports/report generation.
6. **Assurance:** wire the full report catalogue + year rollover/archive; external pen-test of
   access-control/IDOR before national go-live.
