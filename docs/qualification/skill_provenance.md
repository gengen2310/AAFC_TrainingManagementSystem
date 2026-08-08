# Skill Provenance Log

Record of any skill/tool installed for this program, per §3's provenance checklist. Each entry below
was checked against the ten checklist items before installation, not after.

## Entry: pytest-cov 7.1.0 (2026-08-08)

Standard Python coverage-measurement plugin for pytest, needed for Phase D's statement/branch
coverage measurement (mission §6). Provenance check:

1. **Canonical repository**: https://github.com/pytest-dev/pytest-cov — maintained under the
   `pytest-dev` GitHub organisation, the same maintainers as `pytest` itself (already a direct
   dependency of this project).
2. **What it does**: wraps `coverage.py` (the de facto standard Python coverage tool, itself
   maintained by Ned Batchelder, a core CPython/testing-ecosystem contributor) as a pytest plugin —
   adds `--cov` CLI flags, no behavioural change to the app or test suite otherwise.
3. **Scripts / install/postinstall behaviour**: pure Python package, no build scripts, no
   postinstall hooks, no compiled extensions requiring special trust.
4. **Network access at install time**: standard `pip install` from PyPI only; no runtime network
   access from the tool itself.
5. **Secret/environment access**: none — reads only source files and test execution traces to
   compute coverage; does not read `.env`, credentials, or any application secret.
6. **Licence**: MIT.
7. **Exact version installed**: `pytest-cov==7.1.0` (latest at install time, verified via
   `pip index versions`).
8. **Project-local install**: installed into `backend/.venv` only (this project's own virtualenv),
   not globally.

Installed as a **dev-only** tool for measurement, not added to `requirements.txt` (which is the
runtime/production dependency list) — added to `pyproject.toml`'s existing `dev` extras group
instead, alongside the already-present `pytest`/`ruff`/`black`.
