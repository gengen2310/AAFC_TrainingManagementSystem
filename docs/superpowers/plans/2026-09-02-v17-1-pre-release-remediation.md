# AAFC TMS v17.1 Pre-Release Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all confirmed pre-release defects and execute the remaining assurance domains as release-qualification tests, producing a release candidate build on `fix/v17-1-pre-release-remediation`.

**Architecture:** FastAPI backend (Python 3.13, SQLAlchemy 2.0, Alembic) + two frontends: `connected-frontend/index.html` (plain HTML/JS SPA) and `frontend/` (React/Vite Planning Workspace). Both frontends share one backend; cross-origin session handoff uses `aafc_session` cookie with `SameSite=None; Secure`. This architecture is preserved; no consolidation.

**Tech Stack:** Python/FastAPI/SQLAlchemy/pytest, TypeScript/React/Vite/Playwright, GitHub Actions CI, Railway (deployment), PostgreSQL (production), SQLite (local/CI tests only for backend unit tests — NOT for migration assurance).

**Spec:** This plan implements the instructions in the user's remediation brief (2026-09-02), grounded in the frozen audit report at `https://claude.ai/code/artifact/3be74479-fce3-4e55-8c31-8c4089c2de3a`.

## Global Constraints

- Work branch: `fix/v17-1-pre-release-remediation` branched from `origin/main` (currently `3aa7fec7`)
- Never push to `main` directly; never force-push; never rewrite history
- Never deploy production; never reset shared databases
- Never weaken security controls to make tests pass
- Every finding fix requires a regression test where technically practical
- Never alter a test because the product fails it — determine root cause first
- PostgreSQL-compatible behaviour required for all production paths; SQLite test pass ≠ migration correctness
- Do not reintroduce Programme Action Centre or Program Audit into user navigation
- Tenancy hierarchy: National → Wing → Squadron only; Flights are not tenants
- Commit each phase separately with the commit message format specified below

## Phase 0 Reconciliation (already performed — documented here for record)

**Baseline established 2026-09-02:**

| Item | Value |
|---|---|
| Local HEAD at audit freeze | `7ab602b4` |
| origin/main at plan creation | `3aa7fec7` |
| Remediation branch base | `3aa7fec7` (origin/main) |
| Commits after freeze | 3 (see below) |
| Alembic head | `b1c2d3e4f5a6` |
| Backend tests collected | 2153 |
| TypeScript | Clean (tsc --noEmit passes) |
| E2E tests total | 423 tests in 25 files |
| react-router-dom installed | 6.30.4 |

**Commits after 7ab602b4 — already on origin/main:**
- `34e847fb` — fix(deploy): refresh index before dirty check (deploy script) — unrelated to security findings
- `7581823f` — fix: assistant facilitator dropped at creation — this RESOLVES `NEW-DATA-01` (assistant_facilitator_id not persisting)
- `3aa7fec7` — fix(security): code rotation crash-safe + gitignore CSV — unrelated to open findings

**Finding ledger at plan creation:**

| ID | Finding | Severity | Status |
|---|---|---|---|
| F-001 | XSS: `u.title` unescaped at `index.html:6467` | P0 | **OPEN** |
| INT-001 | Curriculum import accepts `squadron_id` without existence check | P2 | **OPEN** |
| SYN-H01 | Cookie auth: SameSite=None+Secure not validated as a pair | P1 | **OPEN** |
| CI-001 | No backend pytest CI workflow | P1 | **OPEN** |
| NEW-DEP-01a | react-router CVE-2025-68470 (open redirect via backslash) | Moderate | **OPEN** |
| NEW-DEP-01b | react-router GHSA-jjmj open redirect → XSS | Moderate | **OPEN** |
| F-002 | (from earlier audit phase — requires inspection) | TBD | **REQUIRES VALIDATION** |
| F-005 | (from earlier audit phase — requires inspection) | TBD | **REQUIRES VALIDATION** |
| NEW-AUTH-01 | (from earlier audit phase — requires inspection) | TBD | **REQUIRES VALIDATION** |
| ENV-001 | Local SQLite missing `class_number` migration | Info | **ENVIRONMENT** (not a product fix) |
| NEW-IDOR-01/02/03 | Cross-tenant IDOR | P0 | **ALREADY FIXED** (verified via matrix) |
| NEW-SEC-02 | Security hardening (from prior session) | P1 | **ALREADY FIXED** |
| NEW-DATA-01 | assistant_facilitator_id not persisting | P1 | **ALREADY FIXED** (commit 7581823f) |

---

## Task 0: Branch Setup

**Files:**
- No files modified — git operations only

**Interfaces:**
- Produces: `fix/v17-1-pre-release-remediation` branch at `3aa7fec7`; all subsequent tasks work on this branch

- [ ] **Step 1: Fast-forward local main and create the remediation branch**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git fetch origin
git checkout main
git merge --ff-only origin/main   # brings local main to 3aa7fec7
git checkout -b fix/v17-1-pre-release-remediation
```

Expected: new branch at `3aa7fec7`, working tree clean (only `secret_codes_2026.csv` untracked, not staged).

- [ ] **Step 2: Verify starting state**

```bash
git status          # only secret_codes_2026.csv untracked; nothing staged
git log --oneline -5
```

Expected: branch `fix/v17-1-pre-release-remediation`, HEAD `3aa7fec7`.

---

## Task 1: Fix F-001 — XSS in renderProgramAudit() + full output-encoding review

**Files:**
- Modify: `connected-frontend/index.html` (line 6467 + surrounding review)
- Test: `backend/tests/test_xss_regression.py` (new file — backend-side rendering test using TestClient)

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `u.title` escaped; all API-derived fields in `renderProgramAudit()` either escaped or provably not HTML-injectable; dead `page-program-audit` and `page-programme-action-centre` DOM removed if safe; regression test confirms payload cannot execute

> **NOTE:** `connected-frontend/index.html` is a single 400KB+ file. Edit surgically — do not rewrite the whole file.

- [ ] **Step 1: Find all API-sourced innerHTML assignments in renderProgramAudit()**

```bash
# Identify the function boundaries
grep -n "function renderProgramAudit\|^function " connected-frontend/index.html | head -20
# Should show renderProgramAudit at ~line 6433
# Find the end: look for the next `^function ` or `^}` at column 0 after 6433
```

- [ ] **Step 2: Read renderProgramAudit() in full**

```bash
sed -n '6433,6530p' connected-frontend/index.html
```

Identify every `${...}` expression inserted into a template literal that ends up in `el.innerHTML`. Check: `u.code`, `u.title`, `cov.decision`, `decLabel`, `pct`, numeric values (safe), `esc()` calls (safe).

- [ ] **Step 3: Fix F-001 — wrap u.title in esc()**

Find this exact expression at line 6467:
```javascript
unscheduled.slice(0,20).map(u=>`<span style="font-size:var(--fs-2xs);background:var(--surface-2);border:1px solid var(--border);border-radius:4px;padding:2px 7px">${esc(u.code?u.code+' ':'')+(u.title||'')}</span>`).join('')+
```

Replace with:
```javascript
unscheduled.slice(0,20).map(u=>`<span style="font-size:var(--fs-2xs);background:var(--surface-2);border:1px solid var(--border);border-radius:4px;padding:2px 7px">${esc((u.code?u.code+' ':'')+( u.title||''))}</span>`).join('')+
```

The `esc()` function already exists in the file — it HTML-encodes `<`, `>`, `&`, `"`, `'`. Confirm by running:
```bash
grep -n "^function esc\|^const esc\|esc=" connected-frontend/index.html | head -5
```

- [ ] **Step 4: Scan renderProgramAudit() for other unescaped API-derived strings**

Check each field the function consumes from API responses (check around lines 6433–6530):
- `d.coverage.total` / `d.coverage.scheduled` / `d.coverage.delivered` / `d.coverage.coverage_pct` — numeric values inserted as numbers. Safe.
- `cov.decision` — used in a CSS class lookup (`b-ok`/`b-amber`/`b-red`). Safe as-is (server returns enum strings, not used in innerHTML directly).
- `decLabel` — derived from `cov.decision` via hardcoded ternary, not from API string. Safe.
- `unscheduled.length` — numeric. Safe.
- `u.code` — already wrapped in `esc()`. Safe.
- `u.title` — FIXED in Step 3.

Document any additional unsafe fields found and fix them in the same edit.

- [ ] **Step 5: Broader scan — find dangerous innerHTML patterns in connected-frontend**

```bash
# innerHTML assignments with template literals (most common XSS vector)
grep -n "innerHTML\s*=" connected-frontend/index.html | grep '\${' | grep -v 'esc(' | head -30
```

For each hit: check whether the interpolated value is API-derived or is a hardcoded string / number. Only API-derived strings need escaping. Numeric fields (counts, percentages) are safe. Fix any that are genuinely dangerous (unescaped API-sourced strings directly in innerHTML).

```bash
# insertAdjacentHTML calls
grep -n "insertAdjacentHTML" connected-frontend/index.html | head -10

# Dynamic href/src with API-sourced values (potential open redirect / script-src injection)
grep -n "\.href\s*=\|\.src\s*=" connected-frontend/index.html | grep -v "//\|http" | head -20
```

Report findings. Fix any confirmed injectable patterns with `esc()`. Do not blindly escape hardcoded strings.

- [ ] **Step 6: Assess Programme Action Centre and Program Audit DOM for safe removal**

```bash
# Find the page elements
grep -n "page-programme-action\|page-program-audit" connected-frontend/index.html | head -20
# Confirm neither appears in NAV_BY_SCOPE
sed -n '5936,5970p' connected-frontend/index.html
# Check for JS event listeners or function calls that reference them
grep -n "page-programme-action\|programme-action\|renderProgrammeAction\|loadProgrammeAction" connected-frontend/index.html | head -20
grep -n "page-program-audit\|renderProgramAudit\|loadProgramAudit" connected-frontend/index.html | head -20
```

**Expected findings:**
- `page-programme-action` at line ~2246 and `page-program-audit` at ~2251 are DOM elements not in `NAV_BY_SCOPE` — not reachable via navigation
- `renderProgramAudit()` is defined and CALLED somewhere (the XSS exists because it runs) — find the call site
- If `renderProgramAudit()` is called on a timer or on a live API endpoint: remove the call but keep the fix (the function may be called defensively from dead code)
- If the function is only reachable via dead navigation code: remove both the DOM element and the render function

**Removal decision (apply only if safe):**
If `page-programme-action` DOM section and `page-program-audit` DOM section have no live code paths (no call in `nav()`, no timer, no event handler that isn't behind a dead nav gate), remove them:
```bash
# Lines to remove — identify precise line ranges via grep -n first, then delete those ranges
# Typical pattern: <div id="page-program-audit" class="page">...</div> block
```

Do not remove `page-audit` (the real audit log page for wing/national/auditor roles — confirmed in NAV_BY_SCOPE).

- [ ] **Step 7: Write regression test**

Create `backend/tests/test_xss_regression.py`:

```python
"""Regression test: F-001 XSS — u.title escaping in renderProgramAudit output.

Tests that the /api/reports/program-audit endpoint does NOT return an HTML
payload that would execute when inserted into innerHTML. The actual HTML
escaping happens in the frontend's esc() function; this test verifies the
backend does not independently inject unescaped HTML (belt-and-suspenders),
and that the frontend esc() helper used for u.title correctly neutralises
the canonical XSS payload.

The esc() function is a pure JS function in connected-frontend/index.html.
We verify it here by extracting its source and running it via js2py or by
checking the pattern directly.
"""
import re


def _esc_py(s: str) -> str:
    """Python equivalent of the JS esc() helper in connected-frontend/index.html.
    Mirrors: s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
              .replace(/"/g,'&quot;').replace(/'/g,'&#39;')
    """
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&#39;")
    )


XSS_PAYLOAD = '<img src=x onerror="window.__xss_test=1">'
NORMAL_TITLE = "Ground School Part 1"
EMPTY_TITLE  = ""


def test_esc_helper_neutralises_xss_payload():
    """esc() must not pass through any HTML tag that could execute."""
    result = _esc_py(XSS_PAYLOAD)
    assert "<img" not in result
    assert "onerror" not in result.lower()
    assert "&lt;img" in result


def test_esc_helper_preserves_normal_title():
    """Normal curriculum title must survive round-trip without alteration."""
    result = _esc_py(NORMAL_TITLE)
    assert result == NORMAL_TITLE


def test_esc_helper_handles_empty():
    result = _esc_py(EMPTY_TITLE)
    assert result == ""


def test_frontend_renderprogram_audit_applies_esc_to_title():
    """Verify that the template expression at index.html:6467 now wraps u.title
    inside esc(). This is a static source check — it will catch if someone
    reverts the fix.
    """
    with open("connected-frontend/index.html", encoding="utf-8") as f:
        source = f.read()

    # Find the specific unscheduled items map expression
    # The fixed form must be: esc(...u.title...) with title inside esc()
    # The broken form was: esc(u.code...') + (u.title||'')  — title outside esc
    pattern_broken = re.compile(
        r"esc\(u\.code[^)]*\)\s*\+\s*\(u\.title",
        re.MULTILINE,
    )
    pattern_fixed = re.compile(
        r"esc\([^)]*u\.title",
        re.MULTILINE,
    )
    assert not pattern_broken.search(source), (
        "F-001 REGRESSION: u.title is outside esc() in the unscheduled items template. "
        "The XSS fix has been reverted."
    )
    assert pattern_fixed.search(source), (
        "F-001: Could not find esc() wrapping u.title in the unscheduled items template. "
        "Verify the fix was applied correctly."
    )
```

- [ ] **Step 8: Run the regression test**

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/test_xss_regression.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 9: Run full backend test suite**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -15
```

Expected: ≥2153 passed, 0 failed.

- [ ] **Step 10: Commit**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git add connected-frontend/index.html backend/tests/test_xss_regression.py
git status  # verify no unintended files
git commit -m "fix(security): close F-001 stored XSS — escape u.title in renderProgramAudit

The unscheduled curriculum items template at connected-frontend/index.html
interpolated u.title directly into innerHTML while u.code was correctly
wrapped with esc(). A national_admin who can set a curriculum item title
to '<img src=x onerror=...>' could execute JS in any user's browser who
views the Program Audit section.

Fix: wrap u.title inside the same esc() call as u.code.
Also: full output-encoding review of renderProgramAudit() — no other
unescaped API-derived string injections found (numeric values are safe).
Dormant Program Audit / Programme Action Centre DOM removed if confirmed
dead (no live nav path).
Regression test: test_xss_regression.py verifies esc() neutralises the
canonical XSS payload and that the source-level fix is not reverted."
```

---

## Task 2: Session Reference Integrity — Regression Coverage

**Files:**
- Modify: `backend/tests/test_session_reference_integrity.py` (create new or extend existing)
- Inspect: `backend/app/routers/training.py` (POST/PATCH `/api/parade-nights/{id}/sessions`)

**Interfaces:**
- Consumes: nothing from earlier tasks (independent)
- Produces: regression tests covering all 5 session foreign references; any missing server-side validation added to `training.py`

> **Context:** Prior audit found and fixed cross-squadron TrainingClass, Facilitator, TrainingArea references and assistant_facilitator_id persistence (commit 7581823f). This task VERIFIES those fixes and adds coverage for `curriculum_item_id`.

- [ ] **Step 1: Read the session create/update endpoints**

```bash
cd backend
# Find session create
grep -n "def.*session\|@router.*session\|training_class_id\|facilitator_id\|assistant_facilitator\|training_area_id\|curriculum_item_id" app/routers/training.py | grep -v "#" | head -50
# Read the create handler (typically around POST /parade-nights/{id}/sessions)
```

Confirm:
1. `training_class_id` is validated against the session's squadron (reject cross-squadron reference)
2. `facilitator_id` is validated against the session's squadron
3. `assistant_facilitator_id` is validated (fix from 7581823f — verify it's present in both create and update paths)
4. `training_area_id` is validated against the session's squadron
5. `curriculum_item_id` — check whether validation exists or is missing

- [ ] **Step 2: Write failing tests for any missing validation**

Create `backend/tests/test_session_reference_integrity.py`:

```python
"""Regression tests: session foreign reference integrity.

Verifies that session create (POST) and update (PATCH) reject cross-squadron
references for all five foreign-key fields. The cross-squadron isolation must
be server-side — frontend hiding is not an authorization control.

Setup: two squadrons (A and B), one sqn_admin for each.
A session in squadron A must reject references to objects owned by squadron B.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import (
    User, Squadron, ParadeNight, TrainingClass, Facilitator,
    TrainingArea, CurriculumItem, Wing,
)
from app.security import create_token

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def cross_sqn_setup():
    """Create two squadrons with objects in each."""
    db = SessionLocal()
    try:
        # Reuse seeded squadrons — find any two with sqn_admin users
        sqn_a = db.query(Squadron).filter(Squadron.is_archived == False).first()
        sqn_b = db.query(Squadron).filter(
            Squadron.is_archived == False, Squadron.id != sqn_a.id
        ).first()
        admin_a = db.query(User).filter(
            User.role == "sqn_admin", User.squadron_id == sqn_a.id, User.is_archived == False
        ).first()
        admin_b = db.query(User).filter(
            User.role == "sqn_admin", User.squadron_id == sqn_b.id, User.is_archived == False
        ).first()
        pn_a = db.query(ParadeNight).filter(
            ParadeNight.squadron_id == sqn_a.id
        ).first()
        tc_b = db.query(TrainingClass).filter(
            TrainingClass.squadron_id == sqn_b.id
        ).first()
        fac_b = db.query(Facilitator).filter(
            Facilitator.squadron_id == sqn_b.id
        ).first()
        ta_b = db.query(TrainingArea).filter(
            TrainingArea.squadron_id == sqn_b.id
        ).first()
        # National curriculum item (should be usable from squadron A)
        nat_ci = db.query(CurriculumItem).filter(
            CurriculumItem.owning_level == "national"
        ).first()
        # Squadron B curriculum item (should NOT be usable from squadron A sessions)
        sqn_b_ci = db.query(CurriculumItem).filter(
            CurriculumItem.squadron_id == sqn_b.id
        ).first()

        tok_a = create_token(str(admin_a.id), {}, token_version=admin_a.token_version)
        tok_b = create_token(str(admin_b.id), {}, token_version=admin_b.token_version)

        yield {
            "sqn_a_id": sqn_a.id, "sqn_b_id": sqn_b.id,
            "pn_a_id": pn_a.id if pn_a else None,
            "tc_b_id": tc_b.id if tc_b else None,
            "fac_b_id": fac_b.id if fac_b else None,
            "ta_b_id": ta_b.id if ta_b else None,
            "nat_ci_id": nat_ci.id if nat_ci else None,
            "sqn_b_ci_id": sqn_b_ci.id if sqn_b_ci else None,
            "tok_a": tok_a, "tok_b": tok_b,
        }
    finally:
        db.close()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _create_session(pn_id, tok, extra=None):
    body = {
        "title": "Ref integrity test",
        "start_time": "19:00",
        "end_time": "21:30",
    }
    if extra:
        body.update(extra)
    return client.post(f"/api/parade-nights/{pn_id}/sessions", json=body, headers=_auth(tok))


def test_cross_sqn_training_class_rejected_on_create(cross_sqn_setup):
    s = cross_sqn_setup
    if not s["pn_a_id"] or not s["tc_b_id"]:
        pytest.skip("Insufficient seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"training_class_id": s["tc_b_id"]})
    assert r.status_code in (400, 403, 422), (
        f"Cross-squadron TrainingClass must be rejected; got {r.status_code}: {r.json()}"
    )


def test_cross_sqn_facilitator_rejected_on_create(cross_sqn_setup):
    s = cross_sqn_setup
    if not s["pn_a_id"] or not s["fac_b_id"]:
        pytest.skip("Insufficient seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"facilitator_id": s["fac_b_id"]})
    assert r.status_code in (400, 403, 422), (
        f"Cross-squadron Facilitator must be rejected; got {r.status_code}: {r.json()}"
    )


def test_cross_sqn_assistant_facilitator_rejected_on_create(cross_sqn_setup):
    s = cross_sqn_setup
    if not s["pn_a_id"] or not s["fac_b_id"]:
        pytest.skip("Insufficient seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"assistant_facilitator_id": s["fac_b_id"]})
    assert r.status_code in (400, 403, 422), (
        f"Cross-squadron assistant Facilitator must be rejected; got {r.status_code}: {r.json()}"
    )


def test_cross_sqn_training_area_rejected_on_create(cross_sqn_setup):
    s = cross_sqn_setup
    if not s["pn_a_id"] or not s["ta_b_id"]:
        pytest.skip("Insufficient seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"training_area_id": s["ta_b_id"]})
    assert r.status_code in (400, 403, 422), (
        f"Cross-squadron TrainingArea must be rejected; got {r.status_code}: {r.json()}"
    )


def test_national_curriculum_item_accepted_from_squadron(cross_sqn_setup):
    """National curriculum items are intentionally visible to all squadrons."""
    s = cross_sqn_setup
    if not s["pn_a_id"] or not s["nat_ci_id"]:
        pytest.skip("Insufficient seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"curriculum_item_id": s["nat_ci_id"]})
    # Must not be rejected for cross-scope reasons (400/403 due to curriculum ownership)
    # May fail for other reasons (duplicate, etc.) — only check it's not a scope rejection
    assert r.status_code != 403, (
        f"National curriculum item must not be scope-rejected from squadron; got 403: {r.json()}"
    )


def test_cross_sqn_curriculum_item_rejected(cross_sqn_setup):
    s = cross_sqn_setup
    if not s["pn_a_id"] or not s["sqn_b_ci_id"]:
        pytest.skip("Insufficient seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"curriculum_item_id": s["sqn_b_ci_id"]})
    assert r.status_code in (400, 403, 422), (
        f"Squadron B curriculum item must be rejected in Squadron A session; "
        f"got {r.status_code}: {r.json()}"
    )


def test_invalid_uuid_rejected(cross_sqn_setup):
    s = cross_sqn_setup
    if not s["pn_a_id"]:
        pytest.skip("No parade night in seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"facilitator_id": "not-a-uuid"})
    assert r.status_code in (400, 422), f"Malformed UUID must return 4xx; got {r.status_code}"


def test_nonexistent_uuid_rejected(cross_sqn_setup):
    import uuid
    s = cross_sqn_setup
    if not s["pn_a_id"]:
        pytest.skip("No parade night in seeded data")
    r = _create_session(s["pn_a_id"], s["tok_a"], {"facilitator_id": str(uuid.uuid4())})
    assert r.status_code in (400, 404, 422), (
        f"Non-existent Facilitator UUID must return 4xx; got {r.status_code}"
    )
```

- [ ] **Step 3: Run tests — expect some to fail if server-side validation is missing**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_session_reference_integrity.py -v 2>&1 | tee /tmp/session_ref_results.txt
```

- [ ] **Step 4: For each FAILING test, fix the product**

For each failing test, read the relevant handler in `backend/app/routers/training.py`. The validation pattern to use:

```python
# Pattern: fetch-then-check (for objects that must belong to session's squadron)
if body.facilitator_id:
    fac = db.get(Facilitator, body.facilitator_id)
    if not fac:
        raise HTTPException(400, detail={"error": "facilitator_not_found"})
    if fac.squadron_id != pn.squadron_id:
        raise HTTPException(400, detail={"error": "facilitator_wrong_squadron"})

# Pattern for curriculum_item_id: allow national items, reject cross-sqn items
if body.curriculum_item_id:
    ci = db.get(CurriculumItem, body.curriculum_item_id)
    if not ci:
        raise HTTPException(400, detail={"error": "curriculum_item_not_found"})
    if ci.owning_level == "squadron" and ci.squadron_id != pn.squadron_id:
        raise HTTPException(400, detail={"error": "curriculum_item_wrong_squadron"})
    # wing and national curriculum items are allowed
```

Apply consistently to both POST (create) and PATCH (update) paths, and to any assign-mission endpoint if it exists.

- [ ] **Step 5: Re-run the integrity tests after fixes**

```bash
python -m pytest tests/test_session_reference_integrity.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run the full backend suite**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

Expected: ≥2153 passed, 0 failed (or higher if new tests were added).

- [ ] **Step 7: Commit**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git add backend/tests/test_session_reference_integrity.py backend/app/routers/training.py
git commit -m "test(security): session reference integrity regression coverage

Adds regression tests for all five session foreign-key fields:
training_class_id, facilitator_id, assistant_facilitator_id,
training_area_id, curriculum_item_id.

Tests verify: valid same-squadron reference accepted; cross-squadron
reference rejected; non-existent UUID rejected; national curriculum items
accepted from squadron context; malformed UUID returns 4xx.

Any missing server-side validation added to the create/update paths
in training.py to make the tests pass."
```

---

## Task 3: Fix INT-001 — Import Endpoints Missing Squadron Existence Check

**Files:**
- Modify: `backend/app/routers/training.py` (lines ~4717+ for `/api/curriculum/import`, ~4915+ for `import-xlsm`, ~5076+ for `import-csv`)
- Modify: `backend/tests/test_curriculum_import.py` (extend existing) OR create `backend/tests/test_import_integrity.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `squadron_id` existence + scope validation in all three import endpoints; regression tests

- [ ] **Step 1: Read all three import endpoints**

```bash
cd backend
sed -n '4717,4800p' app/routers/training.py  # import_curriculum
echo "==="
sed -n '4915,4990p' app/routers/training.py  # import_curriculum_xlsm
echo "==="
sed -n '5076,5140p' app/routers/training.py  # import_curriculum_csv
```

Confirm: does each endpoint fetch and validate `squadron_id` existence before using it? Does it check scope (national_admin/system_admin can import into any squadron; other roles cannot use this endpoint at all per existing role check)?

- [ ] **Step 2: Check if PostgreSQL FK enforcement alone prevents orphan creation**

The `curriculum_item.squadron_id` column has a foreign key to `squadron.id` in the model. PostgreSQL will enforce this at the DB layer — so an orphan CANNOT be created in production (it will raise an IntegrityError). However, the caller would receive a 500 rather than a clean error. Fix this at the API layer regardless.

- [ ] **Step 3: Add the validation — squadron existence + scope check**

Add the following pattern immediately after role check in each import endpoint:

```python
# In import_curriculum (and xlsm, csv variants):
from ..models import Squadron  # add to imports at top if not present

sqn_id = body.squadron_id  # may be None for national-level import
if sqn_id:
    sqn = db.get(Squadron, sqn_id)
    if not sqn:
        raise HTTPException(404, detail={
            "error": "squadron_not_found",
            "message": f"Squadron {sqn_id!r} does not exist.",
        })
    if sqn.is_archived:
        raise HTTPException(400, detail={
            "error": "squadron_archived",
            "message": "Cannot import into an archived squadron.",
        })
    # national_admin and system_admin may import into any squadron (no scope restriction)
    # This is by design — these roles have national scope
```

The malformed UUID case is already handled by Pydantic if `squadron_id` is typed as `Optional[UUID]` in the request schema. Verify:

```bash
grep -n "class CurriculumImportIn\|squadron_id.*UUID\|squadron_id.*str" app/models/ app/routers/training.py 2>/dev/null | head -10
```

If `squadron_id` is typed as `str`, add explicit UUID validation:
```python
import uuid as _uuid
if sqn_id:
    try:
        _uuid.UUID(sqn_id)
    except ValueError:
        raise HTTPException(422, detail={"error": "invalid_uuid", "field": "squadron_id"})
```

- [ ] **Step 4: Write regression tests**

In `backend/tests/test_curriculum_import.py` or a new file, add:

```python
def test_import_nonexistent_squadron_returns_404(client, national_admin_headers):
    """INT-001: importing into a non-existent squadron must return 404, not 500."""
    import uuid
    body = {
        "items": [],
        "squadron_id": str(uuid.uuid4()),  # random, does not exist
        "owning_level": "squadron",
    }
    r = client.post("/api/curriculum/import", json=body, headers=national_admin_headers)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.json()}"


def test_import_malformed_squadron_uuid_returns_4xx(client, national_admin_headers):
    """Malformed UUID must return 4xx, not 500."""
    body = {
        "items": [],
        "squadron_id": "not-a-valid-uuid",
        "owning_level": "squadron",
    }
    r = client.post("/api/curriculum/import", json=body, headers=national_admin_headers)
    assert r.status_code in (400, 422), f"Expected 4xx, got {r.status_code}: {r.json()}"


def test_import_without_squadron_id_proceeds(client, national_admin_headers):
    """None squadron_id (national import) must not trigger squadron check."""
    body = {
        "items": [],
        "squadron_id": None,
        "owning_level": "national",
    }
    r = client.post("/api/curriculum/import", json=body, headers=national_admin_headers)
    # May return 200 with empty results — just must not 404/500 on squadron validation
    assert r.status_code not in (404, 500), f"None squadron_id caused unexpected error: {r.json()}"
```

Note: `national_admin_headers` fixture must exist in `conftest.py`. Check existing fixtures:
```bash
grep -n "def national_admin\|national_admin_headers\|def.*admin_headers" tests/conftest.py | head -10
```

If no such fixture exists, create the headers inline:
```python
# At top of test file, after imports:
from app.models import User
from app.security import create_token
from app.database import SessionLocal

def _nat_admin_token():
    db = SessionLocal()
    u = db.query(User).filter(User.role == "national_admin").first()
    tok = create_token(str(u.id), {}, token_version=u.token_version)
    db.close()
    return {"Authorization": f"Bearer {tok}"}
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_curriculum_import.py -v 2>&1 | tail -20
```

Expected: all new tests PASS. Existing import tests still PASS.

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

- [ ] **Step 7: Commit**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git add backend/app/routers/training.py backend/tests/test_curriculum_import.py
git commit -m "fix(import): validate squadron existence in curriculum import endpoints

INT-001: /api/curriculum/import, /api/curriculum/import-xlsm, and
/api/curriculum/import-csv accepted squadron_id without confirming the
referenced Squadron exists. A non-existent UUID would reach the DB and
return 500 (IntegrityError from PostgreSQL FK) instead of a clean 404.

Fix: add squadron existence check before processing import body.
Archived squadron returns 400. national_admin/system_admin scope is
unchanged (they may import into any squadron — by design).
Regression tests added."
```

---

## Task 4: Fix SYN-H01 — Cookie Configuration Hardening

**Files:**
- Modify: `backend/app/config.py` (validate_for_production + staging validation)
- Modify: `backend/tests/test_config_validation.py` (create new)
- Review: deployment documentation for stale SameSite guidance

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `validate_for_production()` rejects SameSite=none+Secure=false; staging-appropriate check; documentation corrected

> **Architecture constraint:** `COOKIE_SAMESITE` MUST remain `none` in production/staging because the TMS frontend and Planning Workspace run on different Railway origins. Do NOT change SameSite to `lax` or `strict`. The fix is: ensure that if `COOKIE_SAMESITE=none`, then `COOKIE_SECURE` MUST also be `true`.

- [ ] **Step 1: Read current validate_for_production()**

```bash
cd backend
sed -n '110,160p' app/config.py
```

Confirm: it checks `COOKIE_SECURE` but does NOT check the SameSite+Secure combination.

- [ ] **Step 2: Read current config defaults**

```bash
grep -n "COOKIE_SAMESITE\|COOKIE_SECURE\|COOKIE_NAME" app/config.py
```

Expected defaults: `COOKIE_SECURE: bool = False`, `COOKIE_SAMESITE: str = "lax"`. The default of `lax` is correct for local development (cross-origin handoff doesn't work in dev anyway — developers use the same origin). The production/staging value MUST be `none` + `true`.

- [ ] **Step 3: Add the validation**

In `validate_for_production()` in `backend/app/config.py`, add after the existing `COOKIE_SECURE` check:

```python
# SameSite=None requires Secure=True — the railway cross-origin architecture requires
# SameSite=None, so this combination (none+insecure) is always a misconfiguration.
if self.COOKIE_SAMESITE.lower() == "none" and not self.COOKIE_SECURE:
    problems.append(
        "COOKIE_SAMESITE=none requires COOKIE_SECURE=true. "
        "The cross-origin session handoff between TMS and Planning Workspace uses "
        "SameSite=None cookies, which browsers reject unless Secure is also set."
    )
# Warn if SameSite is not 'none' in production — the cross-origin handoff will break.
if self.is_prod and self.COOKIE_SAMESITE.lower() != "none":
    problems.append(
        f"COOKIE_SAMESITE is '{self.COOKIE_SAMESITE}' in production. "
        "The Railway cross-origin TMS → Planning Workspace session handoff requires "
        "COOKIE_SAMESITE=none. Using 'lax' or 'strict' will break cross-origin auth."
    )
```

Also add a staging variant — `validate_for_production()` only runs for `ENVIRONMENT=production`. Create a `validate_for_staging()` (or extend the existing check to cover `staging`):

```python
@property
def is_staging(self) -> bool:
    return self.ENVIRONMENT.lower() == "staging"

def validate_for_staging(self) -> list[str]:
    """Subset of production checks for staging environment."""
    if not self.is_staging:
        return []
    problems = []
    if self.COOKIE_SAMESITE.lower() == "none" and not self.COOKIE_SECURE:
        problems.append(
            "COOKIE_SAMESITE=none requires COOKIE_SECURE=true (staging)."
        )
    return problems
```

In `backend/app/main.py`, find where `validate_for_production()` is called and add the staging call:

```bash
grep -n "validate_for_production" app/main.py
```

Add adjacent to the production check:
```python
staging_problems = settings.validate_for_staging()
if staging_problems:
    for p in staging_problems:
        logger.error("STAGING CONFIG ERROR: %s", p)
    raise RuntimeError(f"Staging misconfiguration: {staging_problems}")
```

- [ ] **Step 4: Correct stale documentation**

```bash
grep -rn "SameSite\|samesite\|COOKIE_SAMESITE" docs/ 2>/dev/null | head -20
# Also check deployment rules
grep -n "SameSite\|samesite" .claude/rules/deployment.md 2>/dev/null || true
```

If any document says "use lax" for production/Railway deployment, correct it to:
> `COOKIE_SAMESITE=none` (required for Railway cross-origin TMS ↔ Planning Workspace session handoff). Must be paired with `COOKIE_SECURE=true`. Do not use `lax` or `strict` in deployed environments — they break cross-origin authentication.

- [ ] **Step 5: Write configuration tests**

Create `backend/tests/test_config_validation.py`:

```python
"""Tests for Settings.validate_for_production() and validate_for_staging()."""
import pytest
from app.config import Settings


def _prod_settings(**kwargs):
    """Build a production-mode Settings with safe defaults overridden by kwargs."""
    defaults = dict(
        ENVIRONMENT="production",
        SECRET_KEY="x" * 40,
        JWT_SECRET="y" * 40,
        COOKIE_SECURE=True,
        COOKIE_SAMESITE="none",
        CORS_ALLOWED_ORIGINS="https://tms.example.com",
        DATABASE_URL="postgresql://user:pass@host/db",
    )
    defaults.update(kwargs)
    return Settings(**defaults)


def test_valid_production_config_has_no_problems():
    s = _prod_settings()
    assert s.validate_for_production() == []


def test_samesite_none_without_secure_is_rejected():
    s = _prod_settings(COOKIE_SAMESITE="none", COOKIE_SECURE=False)
    problems = s.validate_for_production()
    assert any("COOKIE_SAMESITE=none requires COOKIE_SECURE" in p for p in problems), problems


def test_samesite_lax_in_production_is_rejected():
    """lax breaks cross-origin TMS↔PW session handoff — must be caught."""
    s = _prod_settings(COOKIE_SAMESITE="lax")
    problems = s.validate_for_production()
    assert any("COOKIE_SAMESITE" in p for p in problems), (
        "Expected COOKIE_SAMESITE=lax to be flagged in production"
    )


def test_insecure_cookie_alone_is_rejected():
    s = _prod_settings(COOKIE_SECURE=False)
    problems = s.validate_for_production()
    assert any("COOKIE_SECURE" in p for p in problems), problems


def test_dev_config_skips_production_checks():
    s = Settings(ENVIRONMENT="development")
    assert s.validate_for_production() == []


def test_staging_samesite_none_without_secure_flagged():
    s = Settings(
        ENVIRONMENT="staging",
        COOKIE_SAMESITE="none",
        COOKIE_SECURE=False,
    )
    problems = s.validate_for_staging()
    assert any("COOKIE_SAMESITE=none requires COOKIE_SECURE" in p for p in problems), problems


def test_staging_valid_config_clean():
    s = Settings(
        ENVIRONMENT="staging",
        COOKIE_SAMESITE="none",
        COOKIE_SECURE=True,
    )
    assert s.validate_for_staging() == []
```

- [ ] **Step 6: Run tests**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_config_validation.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Run full suite**

```bash
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

- [ ] **Step 8: Commit**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git add backend/app/config.py backend/app/main.py backend/tests/test_config_validation.py
git add docs/  # any corrected docs
git commit -m "fix(auth): harden production/staging cookie configuration validation

SYN-H01: validate_for_production() checked COOKIE_SECURE but did not
enforce the SameSite=None+Secure pairing required by the Railway
cross-origin TMS ↔ Planning Workspace architecture.

- SameSite=none without Secure=true is now a startup-blocking error in
  production and staging.
- SameSite other than 'none' in production is now flagged (it breaks
  cross-origin session handoff).
- validate_for_staging() added for ENVIRONMENT=staging.
- Documentation corrected: 'use lax' guidance removed where present.
- Configuration tests added."
```

---

## Task 5: Dependency Remediation — react-router CVE

**Files:**
- Modify: `frontend/package.json` (react-router-dom version)
- Modify: `frontend/package-lock.json` (updated by npm install)

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: react-router-dom upgraded to 6.30.6; TypeScript clean; build passes; routing behavior verified

> **Context:** Installed: 6.30.4. Latest v6: 6.30.6. CVEs: open redirect via backslash in Link/useNavigate (GHSA-wrjc), open redirect → XSS (GHSA-jjmj), constructor injection via SSR (GHSA-337j). Assessment: `<Link>` and `useNavigate` are NOT used in this app (0 matches in `src/`); SSR hydration is NOT used. However, upgrade to 6.30.6 is low-risk (patch release) and resolves all three CVEs.

- [ ] **Step 1: Confirm CVE applicability assessment**

```bash
cd frontend
grep -r "useNavigate\|<Link\|renderToString\|hydrateRoot\|deserializeErrors" src/ 2>/dev/null | wc -l
```

Expected: 0. The CVEs are technically not exploitable in this app (no Link/useNavigate usage, no SSR), but upgrade is still correct practice.

- [ ] **Step 2: Upgrade react-router-dom to 6.30.6**

```bash
npm install react-router-dom@6.30.6
```

Note: react-router (without -dom) is a peer dependency of react-router-dom — npm will update it too.

- [ ] **Step 3: Verify TypeScript still clean**

```bash
npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Verify build**

```bash
npm run build
```

Expected: clean build output in `dist/`.

- [ ] **Step 5: Run npm audit**

```bash
npm audit --omit=dev
```

Expected: 0 vulnerabilities (or only dev-only vulnerabilities that don't ship to production).

Document any remaining dev-only vulnerabilities and why they are deferred.

- [ ] **Step 6: Run Playwright routing tests**

```bash
# Run only routing-related tests — don't run the full 423-test suite here
npx playwright test --grep "navigation|routing|redirect|login|planning" --project=chromium 2>&1 | tail -20
```

If that grep captures nothing: run a broader set of smoke tests:
```bash
npx playwright test e2e/auth.spec.ts e2e/navigation.spec.ts --project=chromium 2>&1 | tail -20
```

Report any failures — classify as PRODUCT/TEST/DEPENDENCY before proceeding.

- [ ] **Step 7: Commit**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(deps): upgrade react-router-dom 6.30.4 → 6.30.6

Resolves three moderate CVEs:
- GHSA-wrjc-x8rr-h8h6: open redirect via backslash in Link/useNavigate
- GHSA-jjmj-jmhj-qwj2: open redirect leading to XSS
- GHSA-337j-9hxr-rhxg: constructor injection via deserializeErrors (SSR)

Assessment: none of the three are exploitable in this app (no Link/
useNavigate usage; no SSR hydration), but patch-version upgrade is
low-risk and closes the advisory surface.

TypeScript clean, build passes, npm audit --omit=dev: 0 vulnerabilities."
```

---

## Task 6: CI — Backend Tests + TypeScript + Migration Gates

**Files:**
- Create: `.github/workflows/backend-tests.yml`
- Modify: `.github/workflows/e2e-tests.yml` (add TypeScript check + build step)
- Modify: `.github/workflows/dependency-audit.yml` (lower audit level for production deps)
- Review: `.github/workflows/e2e-tests.yml` for PostgreSQL migration rehearsal gap

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: CI runs backend pytest on every PR; TypeScript checked; PostgreSQL migration rehearsed; branch protection requirements documented

- [ ] **Step 1: Read existing e2e-tests.yml in full**

```bash
cat .github/workflows/e2e-tests.yml
```

- [ ] **Step 2: Create backend-tests.yml**

Create `.github/workflows/backend-tests.yml`:

```yaml
name: Backend Tests

on:
  push:
    branches: [main, "release/**", "fix/**", "next-stage/**"]
  pull_request:
    branches: [main, "release/**"]

jobs:
  pytest:
    name: pytest (Python 3.13, SQLite)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install backend dependencies
        working-directory: backend
        run: pip install -r requirements.txt

      - name: Run backend tests
        working-directory: backend
        run: python -m pytest tests/ -q --tb=short
        env:
          ENVIRONMENT: development
          JWT_SECRET: dev-only-change-me-jwt-secret-aafc-tms
          SECRET_KEY: dev-only-change-me-in-production-aafc

  typecheck:
    name: TypeScript typecheck (Planning Workspace)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci

      - name: TypeScript typecheck
        working-directory: frontend
        run: npm run typecheck

  build:
    name: Frontend build (Planning Workspace)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci

      - name: Build
        working-directory: frontend
        run: npm run build
        env:
          NODE_ENV: production

  migration-rehearsal:
    name: PostgreSQL migration rehearsal
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: aafc_test
          POSTGRES_PASSWORD: aafc_test
          POSTGRES_DB: aafc_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install backend dependencies
        working-directory: backend
        run: pip install -r requirements.txt

      - name: Run Alembic migrations against PostgreSQL
        working-directory: backend
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql://aafc_test:aafc_test@localhost:5432/aafc_test
          ENVIRONMENT: development
          JWT_SECRET: dev-only-change-me-jwt-secret-aafc-tms
          SECRET_KEY: dev-only-change-me-in-production-aafc

      - name: Seed representative data and run migration rehearsal
        working-directory: backend
        # If rehearse_data_migrations.py exists, run it. Otherwise seed + smoke check.
        run: |
          if [ -f scripts/rehearse_data_migrations.py ]; then
            python scripts/rehearse_data_migrations.py
          else
            python manage.py --seed
            echo "Seed complete; no rehearse_data_migrations.py found"
          fi
        env:
          DATABASE_URL: postgresql://aafc_test:aafc_test@localhost:5432/aafc_test
          ENVIRONMENT: development
          JWT_SECRET: dev-only-change-me-jwt-secret-aafc-tms
          SECRET_KEY: dev-only-change-me-in-production-aafc
```

- [ ] **Step 3: Verify manage.py --seed exists**

```bash
cd backend
python manage.py --help 2>&1 | head -10
# or
cat manage.py | head -20
```

If `manage.py --seed` doesn't exist, find the correct seed command:
```bash
grep -rn "seed\|seed_all" backend/app/seeds/ | head -5
# Typically: python -m app.seeds.seed_all or python -c "from app.seeds.seed_all import seed; seed()"
```

Adjust the `migration-rehearsal` step accordingly.

- [ ] **Step 4: Update dependency-audit.yml to fail on production HIGH/CRITICAL (not moderate)**

Read current audit level:
```bash
grep -n "audit-level" .github/workflows/dependency-audit.yml
```

The current comment says "Adjust to --audit-level=moderate once triage is done." Now that react-router is upgraded, the remaining moderate CVEs are dev-only. Update to `--audit-level=high` to make prod-HIGH/CRITICAL fail while allowing moderate dev-only advisories to pass:

```bash
# In .github/workflows/dependency-audit.yml, the npm audit step should be:
# run: npm audit --omit=dev --audit-level=high
# NOT: npm audit --audit-level=high (which includes dev deps)
```

Find the exact lines:
```bash
grep -n "npm audit\|audit-level" .github/workflows/dependency-audit.yml
```

Update to use `--omit=dev --audit-level=high`.

- [ ] **Step 5: Verify the security grep uses -E (extended regex)**

```bash
cat scripts/pre_alpha_check.sh | grep -n "grep\|egrep" | head -20
```

If any grep patterns use `\|` alternation without `-E` flag, they silently pass regardless of matches. Check each security grep:

```bash
# Test: does the grep actually find what it should?
grep -c -E "your unit only|Controlled access for training" connected-frontend/index.html backend 2>/dev/null || true
grep -c -E "View current code|Show access code|Reveal code" connected-frontend/index.html backend 2>/dev/null || true
```

These should return 0 (as expected). If any grep in `pre_alpha_check.sh` lacks `-E`, add it.

- [ ] **Step 6: Document branch protection requirements (MANUAL ACTION REQUIRED)**

The GitHub API can configure branch protection. Try:
```bash
gh api repos/{owner}/{repo}/branches/main/protection 2>&1 | head -5
```

If this returns 403 or 404 (insufficient permissions):

Create `docs/release/branch-protection-required.md`:

```markdown
# MANUAL ACTION REQUIRED: GitHub Branch Protection

**Status:** NOT YET CONFIGURED — requires repository admin access.

The following branch protection settings must be configured by a repository admin
at: GitHub → Settings → Branches → Add branch protection rule → Branch name: `main`

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

- **pytest**: catches backend regressions before merge
- **typecheck**: prevents broken TypeScript from reaching main
- **migration rehearsal**: the project has experienced a migration that
  passed SQLite but failed against populated PostgreSQL — this gate
  prevents that class of error
- **E2E (chromium)**: minimum browser coverage gate
- **Force push protection**: prevents history rewriting of the release branch
```

- [ ] **Step 7: Commit**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git add .github/workflows/backend-tests.yml
git add .github/workflows/dependency-audit.yml
git add scripts/pre_alpha_check.sh
git add docs/release/branch-protection-required.md
git commit -m "ci: enforce backend/typecheck/build/migration gates on every PR

CI-001: no backend pytest workflow existed — the suite was only run
during deploy-staging.sh. PRs could merge with failing tests.

Adds:
- backend-tests.yml: pytest on Python 3.13 (SQLite, per current pattern)
- typecheck job: tsc --noEmit on Planning Workspace
- build job: npm run build on Planning Workspace
- migration-rehearsal job: alembic upgrade head against real PostgreSQL,
  then representative data seed (rehearse_data_migrations.py if present)
- dependency-audit: updated to --omit=dev --audit-level=high so
  dev-only moderate advisories don't permanently block CI

Branch protection settings: documented in docs/release/branch-protection-required.md
MANUAL ACTION REQUIRED — repository admin must apply these via GitHub UI."
```

---

## Task 7: E2E Failure Recovery

**Files:**
- Modify: `frontend/e2e/` — test files with PRODUCT DEFECT or TEST DEFECT failures
- Modify: `backend/app/routers/` — any product defects found
- NOTE: Do NOT use `--update-snapshots` without inspecting diffs first

**Interfaces:**
- Consumes: branch state from Tasks 1–6 (fixes must be present before running E2E)
- Produces: all required E2E tests passing in Chromium, Firefox, WebKit; each failure classified and resolved

- [ ] **Step 1: Run the full E2E suite in Chromium**

```bash
cd frontend
# First make sure backend is running with seeded DB
cd ../backend && python manage.py --seed && uvicorn app.main:app --port 8000 &
cd ../frontend
npx playwright test --project=chromium 2>&1 | tee /tmp/e2e-chromium-results.txt
```

Wait for results. This will take several minutes.

- [ ] **Step 2: Classify every failure**

Read `/tmp/e2e-chromium-results.txt`. For each failing test:

1. Read the full error message and stack
2. Classify as: PRODUCT DEFECT / TEST DEFECT / STALE TEST / STALE SNAPSHOT / FLAKY / ENVIRONMENT / DEPENDENCY CHANGE
3. Record in a working ledger (not committed — for your own tracking)

Classification guide:
- **PRODUCT DEFECT**: the test asserts real behavior and the product is broken
- **TEST DEFECT**: wrong selector, wrong expectation, wrong setup — the product is fine
- **STALE TEST**: test assumes a UI element or route that was intentionally removed/renamed
- **STALE SNAPSHOT**: screenshot baseline predates a visual change that was intentional
- **FLAKY**: timing-sensitive, non-deterministic, passes on retry
- **ENVIRONMENT**: CI-specific (missing env var, race in startup, wrong port)
- **DEPENDENCY CHANGE**: caused by the react-router upgrade (verify by checking if failure is in routing code)

- [ ] **Step 3: Fix PRODUCT DEFECTs**

For each product defect, read the relevant source code and fix the product. Add a test-targeted commit for each cluster of related fixes.

After each product fix, re-run only the failing tests:
```bash
npx playwright test --project=chromium -g "failing test name" 2>&1 | tail -10
```

- [ ] **Step 4: Fix TEST DEFECTs**

For each test defect, fix the selector/expectation/setup WITHOUT weakening the behavioural assertion. The test must still verify the same behaviour — only the mechanical means of doing so changes.

Rules:
- Do NOT add `{ strict: false }` to resolve locator conflicts caused by duplicate UI elements — first check if the UI is genuinely ambiguous
- Do NOT add arbitrary `waitForTimeout()` sleeps — use proper `waitForResponse()` or `waitForSelector()` guards
- Do NOT add test retries to hide flakiness — diagnose the root cause

- [ ] **Step 5: Handle STALE SNAPSHOT failures**

Before accepting any new snapshot baseline:
```bash
npx playwright show-report  # view the actual diff screenshot
```

If the visual change is intentional (e.g., a UI fix from Task 1): accept the new baseline:
```bash
npx playwright test --project=chromium -g "snapshot test name" --update-snapshots
```

If the visual change is unexpected: it is a PRODUCT DEFECT — fix the product first.

- [ ] **Step 6: Run Firefox and WebKit**

```bash
npx playwright test --project=firefox 2>&1 | tee /tmp/e2e-firefox-results.txt
npx playwright test --project=webkit 2>&1 | tee /tmp/e2e-webkit-results.txt
```

Apply the same classification and fix process for each browser.

- [ ] **Step 7: Document intentional browser exclusions**

If any test genuinely cannot run on a specific browser (WebKit limitation, WebRTC, etc.): add a comment in the test file and `--exclude` it from the CI matrix with a documented reason. Do not silently fail.

- [ ] **Step 8: Commit all E2E fixes**

```bash
cd /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
git add frontend/e2e/ backend/app/
git commit -m "test(e2e): restore trustworthy browser qualification

Classified all E2E failures from CI run. Fixed:
- PRODUCT DEFECT: [list what was fixed]
- TEST DEFECT: [list selector/expectation fixes]
- STALE SNAPSHOT: [list accepted baselines with justification]

Intentional browser exclusions: [list any, or 'none']
Remaining FLAKY tests: [list any, or 'none']

Full suite passes: Chromium [N/423], Firefox [N/423], WebKit [N/423]."
```

---

## Task 8: CEA Activity Import

**Files:**
- Create: `backend/app/routers/activities_import.py` (or extend `export_import.py`)
- Modify: `backend/app/main.py` (register new router if separate file)
- Modify: `connected-frontend/index.html` (import UI in Activities section)
- Create: `backend/tests/test_activity_import.py`

**Interfaces:**
- Consumes: squadron scope validation pattern from Task 3
- Produces: `/api/activities/import` endpoint + frontend upload-preview-commit UX

> **Scope check:** Before implementing, verify that CEA Activity import is in scope for this release. If `docs/beta/` or the current gap register explicitly defers it, record as HUMAN DECISION and skip this task.

- [ ] **Step 1: Verify scope**

```bash
grep -rn "activity.*import\|import.*activity\|CEA.*import\|bulk.*activit" docs/ 2>/dev/null | head -10
grep -rn "activity.*import\|import.*activit" connected-frontend/index.html | head -10
```

If this feature is deferred in authoritative release docs: record `HUMAN DECISION: deferred` and skip this task.

- [ ] **Step 2: Read existing Activity model and router**

```bash
grep -n "class.*Activity\|class CeaActivity" backend/app/models/*.py backend/app/models/**/*.py 2>/dev/null | head -10
grep -n "@router.*activ" backend/app/routers/*.py 2>/dev/null | head -20
```

Understand: what fields does `Activity` have? What is the existing create/edit flow?

- [ ] **Step 3: Implement the backend import endpoint**

In `backend/app/routers/export_import.py` (or a new file), add:

```python
from pydantic import BaseModel
from typing import Optional
import csv, io, datetime

class ActivityImportRow(BaseModel):
    seq_nr: Optional[int] = None
    name: str
    start_date: str          # ISO format: YYYY-MM-DD
    start_time: str          # HH:MM
    end_date: str            # ISO format: YYYY-MM-DD
    end_time: str            # HH:MM
    unit: Optional[str] = None
    location: Optional[str] = None
    activity_notes: Optional[str] = None

class ActivityImportPreviewIn(BaseModel):
    rows: list[ActivityImportRow]
    squadron_id: Optional[str] = None  # required for squadron-level import

class ActivityImportResult(BaseModel):
    created: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[dict] = []

@router.post("/activities/import/preview")
def preview_activity_import(body: ActivityImportPreviewIn, db: DBSession = Depends(get_db),
                             p: Principal = Depends(get_principal)):
    """Validate rows and return per-row errors. Does NOT commit."""
    # ... validation logic (see below)

@router.post("/activities/import/commit")
def commit_activity_import(body: ActivityImportPreviewIn, db: DBSession = Depends(get_db),
                            p: Principal = Depends(get_principal)):
    """Commit validated rows. Requires prior preview approval."""
    # ... commit logic
```

Validation rules per row:
- `name` required; reject empty
- `start_date` / `end_date`: parse as `datetime.date` — reject if invalid format
- `start_time` / `end_time`: parse as `datetime.time` (HH:MM) — reject if invalid
- `end_date + end_time` must not be before `start_date + start_time`
- Duplicate: same name + start_date + squadron — return `skipped` with reason

Scope rules:
- `sqn_admin` can import into their own squadron only
- `wing_admin` can import into squadrons in their wing (via proxy)
- `national_admin`, `system_admin` can import into any squadron

```python
# Squadron validation (same pattern as Task 3):
if body.squadron_id:
    sqn = db.get(Squadron, body.squadron_id)
    if not sqn:
        raise HTTPException(404, detail={"error": "squadron_not_found"})
    if p.role == "sqn_admin" and p.squadron_id != sqn.id:
        raise HTTPException(403, detail={"error": "wrong_squadron"})
```

- [ ] **Step 4: Implement frontend upload-preview-commit UX**

In `connected-frontend/index.html`, within the Activities section, add an import button and modal following the pattern of existing imports in the file:

```bash
# Find how existing import UIs work
grep -n "importModal\|import-modal\|showImport\|uploadImport" connected-frontend/index.html | head -20
# Find the activities section
grep -n "page-activities\|loadActivities\|Activities" connected-frontend/index.html | head -10
```

Follow the existing import pattern exactly (file upload → base64 encode → POST preview → show results table → confirm → POST commit → show result accounting).

- [ ] **Step 5: Write backend tests**

Create `backend/tests/test_activity_import.py`:

```python
"""Tests for CEA Activity bulk import."""

def test_preview_valid_rows_returns_no_errors(...):
    # valid rows return 200 with errors=[]

def test_preview_invalid_date_returns_row_error(...):
    # '2026-13-01' as start_date returns errors for that row

def test_preview_end_before_start_returns_row_error(...):
    # end_date+time before start_date+time returns error

def test_preview_missing_name_returns_row_error(...):
    # name='' returns error

def test_commit_creates_activities(...):
    # after commit, activities are in DB

def test_commit_duplicate_returns_skipped(...):
    # second commit of same data returns skipped count, not error

def test_cross_squadron_import_rejected_for_sqn_admin(...):
    # sqn_admin cannot import into another squadron

def test_nonexistent_squadron_returns_404(...):
    # squadron_id for non-existent squadron returns 404

def test_malformed_squadron_uuid_returns_4xx(...):
    # 'not-a-uuid' squadron_id returns 422/400
```

- [ ] **Step 6: Run tests**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_activity_import.py -v
python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/ backend/tests/test_activity_import.py connected-frontend/index.html
git commit -m "feat(import): complete CEA activity bulk import

Implements upload → preview → validate → confirm → commit workflow
for bulk activity/CEA import via CSV rows.

Fields: SeqNr, Name, Start/End date+time, Unit, Location, Activity Notes.
Validation: required fields, date/time parsing, end-before-start check,
duplicate detection, row-level error reporting.
Scope: sqn_admin imports into own squadron only; national/system into any;
wing_admin via existing proxy mechanic.
Backend: /api/activities/import/preview + /api/activities/import/commit
Frontend: upload modal in Activities section following existing import UX.
Tests: validation, duplicates, cross-squadron rejection, existence check."
```

---

## Task 9: Documentation Reconciliation

**Files:**
- Modify: `docs/` — identify and correct stale/contradictory documents
- Modify: `CLAUDE.md` — verify test count reference is removed or marked stale

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: clear doc hierarchy; one declared current gap register; historical docs marked as such

- [ ] **Step 1: Identify stale documents**

```bash
ls docs/release/ docs/beta/ 2>/dev/null
grep -rn "92ef2b2a\|7ab602b4\|2026-08-12\|1553 passed\|2130 passed\|2144 passed" docs/ CLAUDE.md 2>/dev/null | head -20
```

- [ ] **Step 2: Update CLAUDE.md test count reference**

```bash
grep -n "baseline as of\|passed\|skipped" CLAUDE.md | head -5
```

Change stale test count references to use a dynamic check rather than a hardcoded number, per existing CLAUDE.md guidance:
> "re-run and record the real pass/fail/skip count rather than trusting any number written here; it goes stale fast."

Verify this is already in CLAUDE.md. If a hardcoded count is present, add a note: `(stale — run python -m pytest tests/ --collect-only -q to get current count)`.

- [ ] **Step 3: Establish doc hierarchy**

Create or update `docs/architecture.md` with a top-of-file note declaring it authoritative:

```markdown
<!-- AUTHORITATIVE ARCHITECTURE DOCUMENT — last updated 2026-09-02 -->
<!-- Supersedes: docs/AAFC_TMS_TRGO_Planning_Module.md (historical) -->
```

Create `docs/release/current-gap-register.md` with ONE clear declaration:

```markdown
# Current Gap Register — AAFC TMS v17.1 Remediation

**Status as of:** 2026-09-02
**Remediation branch:** fix/v17-1-pre-release-remediation

This is the SINGLE AUTHORITATIVE gap register during remediation.
All historical gap registers are in docs/beta/ and are superseded.

| ID | Finding | Severity | Status | Commit |
|---|---|---|---|---|
| F-001 | XSS u.title unescaped | P0 | FIXED LOCALLY | [task-1-commit] |
| INT-001 | Import squadron_id not validated | P2 | FIXED LOCALLY | [task-3-commit] |
| SYN-H01 | Cookie config not validated as pair | P1 | FIXED LOCALLY | [task-4-commit] |
| CI-001 | No backend pytest CI | P1 | FIXED LOCALLY | [task-6-commit] |
| NEW-DEP-01a/b | react-router CVEs | Moderate | FIXED LOCALLY | [task-5-commit] |
| CI-BRANCH | Branch protection not configured | P1 | MANUAL ACTION REQUIRED | docs/release/branch-protection-required.md |
```

Mark historical documents:
```bash
# Add a header to each doc in docs/beta/ that predates remediation
# "<!-- HISTORICAL — superseded by docs/release/current-gap-register.md -->"
```

- [ ] **Step 4: Check for contradictory deployment docs**

```bash
grep -rn "SameSite=lax\|samesite.*lax\|use lax" docs/ .claude/rules/ 2>/dev/null | head -10
```

Fix any that recommend `lax` for Railway deployment (corrected in Task 4 — verify the fix propagated here).

- [ ] **Step 5: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: reconcile architecture and release source-of-truth

- docs/release/current-gap-register.md: single authoritative gap register
- Historical docs in docs/beta/ marked as superseded
- CLAUDE.md test count reference updated (stale hardcoded counts removed)
- docs/architecture.md marked as authoritative
- Stale SameSite=lax guidance corrected throughout
- docs/release/branch-protection-required.md: manual admin action required"
```

---

## Task 10: Release Qualification — 8-Role Matrix

> This task is a RELEASE ACCEPTANCE TEST, not exploratory audit. Run against the remediated build. Record failures as release defects and fix them.

**Files:**
- Create: `backend/tests/test_release_qualification_rbac.py`

- [ ] **Step 1: Run the backend permission matrix**

Run the existing token-based matrix test (or create `test_release_qualification_rbac.py` reusing the TestClient approach from the audit):

```python
"""Release qualification: 8-role API permission matrix.

Run against the remediated build on fix/v17-1-pre-release-remediation.
Any unexpected result is a release defect — fix the product, not the expectation.
"""
```

Cover all roles against all key endpoints as documented in the audit report (§A of the frozen assurance report). The 65-test matrix already established expected results.

- [ ] **Step 2: Run Training Officer end-to-end simulation via browser automation**

Using Claude-in-Chrome (if available) or Playwright directly:

```bash
# Start backend + connected-frontend
cd backend && uvicorn app.main:app --port 8000 &
cd connected-frontend && python3 -m http.server 8080 &
# Start Planning Workspace
cd frontend && npm run dev &
```

Log in as `sqn_admin` (use a seeded code like `ADMIN703` or generate a token). Execute:

1. Navigate to Planning Year — confirm the year exists or create one
2. Navigate to Training Classes — create a class, assign curriculum
3. Navigate to Parade Nights — create a parade night, verify date is correct
4. Create a session — assign a Training Class, Facilitator, Training Area, Curriculum Item
5. Verify session fields survive save + reload (assistant_facilitator was a known bug — verify fix)
6. Navigate to Activities — verify the import button appears (Task 8)
7. Navigate to Planning Workspace (click the link) — verify cross-origin handoff works
8. In Planning Workspace: verify the planning year is visible
9. Return to TMS — verify no session state is lost

Record each step result. Any failure is a release defect.

- [ ] **Step 3: Run TMS ↔ Planning Workspace integration**

Create a session in the TMS backend. Navigate to Planning Workspace. Verify the session is visible there. Make a change in Planning Workspace. Return to TMS and confirm the change is reflected.

- [ ] **Step 4: Record results and commit**

```bash
git add backend/tests/test_release_qualification_rbac.py
git commit -m "test(release): 8-role qualification matrix pass — release qualification

All 65 permission tests pass on remediated build.
Training Officer simulation: [PASS/FAIL with details]
TMS ↔ PW integration: [PASS/FAIL with details]
Any failures recorded as release defects in docs/release/current-gap-register.md."
```

---

## Task 11: Release Gate Check

> This is a checklist task — no code unless a gap is found.

- [ ] **Step 1: Run full backend suite**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -q 2>&1 | tail -5
```

Record: N passed, N skipped, 0 failed.

- [ ] **Step 2: TypeScript clean**

```bash
cd frontend && npm run typecheck
```

Expected: exit 0, no errors.

- [ ] **Step 3: Frontend build**

```bash
npm run build
```

Expected: clean build.

- [ ] **Step 4: npm audit production**

```bash
npm audit --omit=dev
```

Expected: 0 HIGH/CRITICAL vulnerabilities.

- [ ] **Step 5: Run E2E all browsers**

```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

Record pass/fail counts.

- [ ] **Step 6: Security greps**

```bash
grep -Rc -E "your unit only|Controlled access for training" connected-frontend backend
grep -Rc -E "View current code|Show access code|Reveal code|Display existing code" connected-frontend backend
grep -Rc -E "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code|localStorage" connected-frontend
grep -Rc -E "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend
```

Expected: all return 0.

- [ ] **Step 7: Confirm F-001 closed**

```bash
python -m pytest backend/tests/test_xss_regression.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 8: Push branch and open PR**

```bash
git push -u origin fix/v17-1-pre-release-remediation
gh pr create \
  --base main \
  --title "fix: v17.1 pre-release remediation — F-001 XSS, INT-001, SYN-H01, CI gates, E2E recovery" \
  --body "$(cat <<'EOF'
## Summary

Resolves all confirmed pre-release defects from the frozen assurance audit (2026-09-02).

### Security (P0/P1)
- **F-001 FIXED**: Stored XSS — `u.title` now wrapped in `esc()` at `connected-frontend/index.html:6467`
- **SYN-H01 FIXED**: `validate_for_production()` now rejects `COOKIE_SAMESITE=none` without `COOKIE_SECURE=true`; staging validation added

### Data Integrity
- **INT-001 FIXED**: Curriculum import endpoints now validate `squadron_id` existence; nonexistent → 404, malformed → 422

### CI
- **CI-001 FIXED**: `backend-tests.yml` adds pytest on every PR
- TypeScript typecheck + build gate added
- PostgreSQL migration rehearsal added (real DB, not SQLite)
- Branch protection settings documented (manual admin action required)

### Dependencies
- react-router-dom 6.30.4 → 6.30.6 (resolves 3 moderate CVEs)

### Session Reference Integrity
- Regression tests added for all 5 session foreign-key fields
- Any missing server-side validation added (cross-squadron rejection)

### Release Qualification
- 8-role API permission matrix: 65/65 PASS
- Training Officer simulation: [outcome]
- TMS ↔ Planning Workspace integration: [outcome]
- E2E: Chromium [N/423], Firefox [N/423], WebKit [N/423]

## Branch protection
⚠️ Manual admin action required — see `docs/release/branch-protection-required.md`

## Do not deploy production automatically
Staging deployment requires explicit authorization.
EOF
)"
```

- [ ] **Step 9: Final ledger update**

Update `docs/release/current-gap-register.md` with actual commit SHAs, test counts, and final status for each finding.

---

## Remediation Ledger Template

Maintain this throughout execution. Update after each task.

```
| ID          | Finding                          | Sev | Status               | Files Changed | Tests Added | Test Result | Suite Result | Commit | Risk |
|-------------|----------------------------------|-----|----------------------|---------------|-------------|-------------|--------------|--------|------|
| F-001       | XSS u.title unescaped            | P0  | OPEN                 | -             | -           | -           | -            | -      | HIGH |
| INT-001     | Import sqn_id not validated      | P2  | OPEN                 | -             | -           | -           | -            | -      | MED  |
| SYN-H01     | Cookie SameSite+Secure not paired| P1  | OPEN                 | -             | -           | -           | -            | -      | MED  |
| CI-001      | No backend pytest CI             | P1  | OPEN                 | -             | -           | -           | -            | -      | MED  |
| NEW-DEP-01a | react-router CVE open redirect   | Mod | OPEN                 | -             | -           | -           | -            | -      | LOW  |
| NEW-DATA-01 | assistant_facilitator dropped    | P1  | ALREADY FIXED 7581823f| -            | -           | -           | -            | 7581823| NONE |
| CI-BRANCH   | Branch protection not set        | P1  | MANUAL ACTION REQ    | -             | -           | -           | -            | docs   | MED  |
```
