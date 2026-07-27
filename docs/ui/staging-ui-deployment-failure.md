# Staging UI Deployment Failure Record

## Failure Summary

- **Staging URL tested:** https://aafc-tms-frontend-staging.up.railway.app
- **Date and time:** 2026-07-22
- **User confirmation:** User manually opened the staging application and confirmed that none of the requested changes were visible in the rendered interface.
- **Expected commit:** e548875 (branch: feature/restore-planning-workspace)

## Deployment IDs at Time of Failure

| Service | Deployment ID | Status |
|---|---|---|
| Backend | 674cbc7c | Active |
| Main TMS (connected-frontend) | 3a7362f8 | Active |
| Planning Workspace | 2135784a | FAILED |
| Planning Workspace (previous active) | 8f93e841 | Previous |

## Why the Previous Verification Was Insufficient

The previous automated Playwright test run reported 36/36 tests passing, but this did not prove the rendered UI contained the requested changes. The prior verification relied on:

1. **Source and bundle text searches** — presence of a string in the source file does not mean that source file is what Railway is serving.
2. **API endpoint existence** — a working `/api/activities` endpoint does not prove the correct frontend HTML is deployed.
3. **Assumed bundle equivalence** — no comparison was made between the local build artifact and the response body served by Railway.
4. **Deployment status alone** — a Railway deployment being "active" does not confirm it built from the correct source directory and branch.

The Playwright tests tested properties of the rendered DOM, but the assertions were too permissive — many passed because the features checked (e.g., "Add Holiday" button, "Activities" title) were also present in prior deployments.

## Conclusion

**Staging must not be considered verified.** The deployment must be investigated, corrected, and re-proven through authenticated browser screenshots showing the requested changes in the rendered interface.

## Invariants

- Production was not changed.
- This failure record documents staging only.
- No Playwright test result may be treated as proof of deployment correctness unless a build fingerprint is verified in the same test run.
