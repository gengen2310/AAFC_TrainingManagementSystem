# MANUAL ACTION REQUIRED: GitHub Branch Protection

**Status:** NOT YET CONFIGURED — requires repository admin access.

The following branch protection settings must be configured by a repository admin at:
GitHub → Settings → Branches → Add branch protection rule → Branch name: `main`

## Required settings

- [x] Require a pull request before merging
  - Required approvals: 1
  - Dismiss stale pull request approvals when new commits are pushed: Yes
- [x] Require status checks to pass before merging
  - Require branches to be up to date before merging: Yes
  - Required checks:
    - `pytest (Python 3.13, SQLite)`
    - `TypeScript typecheck (Planning Workspace)`
    - `Frontend build (Planning Workspace)`
    - `PostgreSQL migration rehearsal`
    - `Planning Workspace E2E (chromium)`
    - `pip-audit (backend)`
    - `npm audit (Planning Workspace)`
- [x] Require conversation resolution before merging
- [x] Do not allow force pushes
- [x] Do not allow deletions

## Why each requirement matters

- **pytest**: catches backend regressions before merge; was previously not gated (CI-001)
- **typecheck**: prevents broken TypeScript from reaching main
- **build**: confirms the Planning Workspace actually builds before merge
- **migration rehearsal**: the project experienced a migration that passed SQLite
  but failed against populated PostgreSQL — this gate prevents that class of error
- **E2E (chromium)**: minimum browser coverage gate
- **pip-audit / npm audit**: catches new dependency CVEs before they enter main
- **Force push protection**: prevents history rewriting of the release branch

## Workflow file locations

The required CI checks are defined in:
- `.github/workflows/backend-tests.yml` — pytest, typecheck, build, migration rehearsal
- `.github/workflows/e2e-tests.yml` — Playwright E2E
- `.github/workflows/dependency-audit.yml` — pip-audit, npm audit

## Note on automated configuration

Claude Code does not have sufficient GitHub permissions to configure branch protection
rules programmatically on this repository. This document serves as the specification
for the admin action required before the beta release.
