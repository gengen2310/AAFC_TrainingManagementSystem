# MANUAL ACTION REQUIRED: GitHub Branch Protection

**Status:** NOT CONFIGURED. The `main` branch currently reports protection disabled and has no required status checks.

Configure a branch protection rule for `main` before beta/release approval.

## Required settings

- Require a pull request before merging.
  - Required approvals: 1.
  - Dismiss stale approvals when new commits are pushed.
- Require status checks to pass before merging.
  - Require branches to be up to date before merging.
  - Require all release-qualification checks below:
    - `pytest (Python 3.13, SQLite)`
    - `TypeScript typecheck (Planning Workspace)`
    - `Frontend build (Planning Workspace)`
    - `PostgreSQL migration rehearsal`
    - `Planning Workspace E2E (chromium)`
    - `Planning Workspace E2E (firefox)`
    - `Planning Workspace E2E (webkit)`
    - `Connected Frontend E2E (chromium)`
    - `Connected Frontend E2E (firefox)`
    - `Connected Frontend E2E (webkit)`
    - `pip-audit (backend)`
    - `npm audit (Planning Workspace)`
- Require conversation resolution before merging.
- Do not allow force pushes.
- Do not allow branch deletion.

## Why these checks are required

- `pytest` protects backend behaviour, tenancy and RBAC contracts and includes SQLite migration regressions.
- TypeScript and build checks prove the Planning Workspace compiles as the module that is actually deployed.
- PostgreSQL migration rehearsal exercises the production database dialect before a merge.
- All three Planning Workspace browsers validate the `/planning` module contract rather than a retired React TMS shell.
- All three Connected Frontend browsers validate the authoritative Main TMS surface and its cross-interface handoff.
- Dependency audits prevent known backend or production-frontend High/Critical vulnerabilities from entering `main` unnoticed.

## Workflow ownership

- `.github/workflows/backend-tests.yml`: pytest, typecheck, build, PostgreSQL migration rehearsal.
- `.github/workflows/e2e-tests.yml`: Planning Workspace and Connected Frontend matrices for Chromium, Firefox and WebKit.
- `.github/workflows/dependency-audit.yml`: pip-audit and npm audit.

This file is a release-control specification only. It does not claim the repository is protected until GitHub reports the rule as enabled.
