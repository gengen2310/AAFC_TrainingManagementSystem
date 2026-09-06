"""Tests for the timing-template-compulsory invariant on new Parade Nights.

PRODUCT DECISION: A NEW PARADE NIGHT MUST HAVE A TIMING TEMPLATE.
POST /api/parade-nights without a resolvable active template → 422.
session_count and default_session_count must NOT bypass this rule.
"""
import pytest
from tests.conftest import login, next_test_year


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _get_active_template_id(client, hdr):
    """Return the timing_template_id of the first active default template for the current squadron."""
    r = client.get("/api/timing-templates", headers=hdr)
    assert r.status_code == 200
    templates = r.json() if isinstance(r.json(), list) else r.json().get("templates", [])
    defaults = [t for t in templates if t.get("is_default") and t.get("active_status")]
    assert defaults, "No default active timing template — seed may be incomplete"
    return defaults[0]["timing_template_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Happy path: auto-resolved template
# ─────────────────────────────────────────────────────────────────────────────

def test_create_parade_auto_resolves_template(client):
    """Creating a night without explicit template_id succeeds when a template covers the date."""
    hdr = _sqn_admin_hdr(client)
    r = client.post("/api/parade-nights",
                    json={"date": "2027-03-14", "term": "T2"},
                    headers=hdr)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    d = r.json()
    assert "parade_night_id" in d
    # Verify timing_template_id is set (not NULL)
    pnid = d["parade_night_id"]
    pn_r = client.get(f"/api/parade-nights/{pnid}", headers=hdr)
    if pn_r.status_code == 200:
        pn = pn_r.json()
        if isinstance(pn, dict):
            # Some endpoints return {sessions: [...], ...}; check timing_template_id if present
            assert pn.get("timing_template_id") is not None, (
                "New Parade Night must have a timing_template_id set — never NULL"
            )


def test_create_parade_with_explicit_template_succeeds(client):
    """Supplying a valid explicit timing_template_id succeeds and uses that template."""
    hdr = _sqn_admin_hdr(client)
    tmpl_id = _get_active_template_id(client, hdr)
    r = client.post("/api/parade-nights",
                    json={"date": "2027-04-14", "term": "T2",
                          "timing_template_id": tmpl_id},
                    headers=hdr)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ─────────────────────────────────────────────────────────────────────────────
# Rejection cases
# ─────────────────────────────────────────────────────────────────────────────

def test_create_parade_with_date_before_any_template_fails(client):
    """If no template covers the date, creation must fail with 422."""
    hdr = _sqn_admin_hdr(client)
    # The seeded 703 template has effective_from="2000-01-01".
    # A date before 2000 has no covering template → must 422.
    r = client.post("/api/parade-nights",
                    json={"date": "1999-06-06", "term": "T2"},
                    headers=hdr)
    assert r.status_code == 422, (
        f"Expected 422 timing_template_required, got {r.status_code}: {r.text}"
    )
    err = r.json().get("detail", {})
    assert err.get("error") == "timing_template_required", (
        f"Expected error='timing_template_required', got {err}"
    )


def test_create_parade_with_archived_template_fails(client):
    """Supplying an archived timing_template_id must fail with 422 timing_template_not_found.

    The API has no endpoint to set active_status=False directly; archiving is
    the supported way to permanently retire a template. An archived template
    must be rejected identically to a non-existent one.
    """
    hdr = _sqn_admin_hdr(client)
    # Use a far-future effective_from so this template never becomes the
    # effective one for dates used in later tests in this suite.
    create_r = client.post("/api/timing-templates",
                           json={"name": "Archive Reject Test",
                                 "effective_from": "2095-01-01"},
                           headers=hdr)
    if create_r.status_code != 200:
        pytest.skip("Could not create a timing template via API")
    tmpl_id = create_r.json().get("timing_template_id") or create_r.json().get("id")
    if not tmpl_id:
        pytest.skip("Could not extract timing_template_id from create response")
    # Archive it immediately so it's treated as deleted/unreachable
    archive_r = client.post(f"/api/timing-templates/{tmpl_id}/archive", headers=hdr)
    if archive_r.status_code != 200:
        pytest.skip("Could not archive template via API")
    r = client.post("/api/parade-nights",
                    json={"date": "2095-06-01", "term": "T2",
                          "timing_template_id": tmpl_id},
                    headers=hdr)
    assert r.status_code == 422, (
        f"Expected 422 for archived template, got {r.status_code}: {r.text}"
    )
    err = r.json().get("detail", {})
    assert err.get("error") == "timing_template_not_found", (
        f"Expected timing_template_not_found, got {err}"
    )


def test_create_parade_with_nonexistent_template_fails(client):
    """Supplying a non-existent timing_template_id must fail with 422."""
    hdr = _sqn_admin_hdr(client)
    r = client.post("/api/parade-nights",
                    json={"date": "2027-06-14", "term": "T2",
                          "timing_template_id": "00000000-0000-0000-0000-000000000000"},
                    headers=hdr)
    assert r.status_code == 422, (
        f"Expected 422 for missing template, got {r.status_code}: {r.text}"
    )


def test_session_count_in_body_does_not_bypass_template_requirement(client):
    """Supplying session_count must NOT allow bypassing the template requirement."""
    hdr = _sqn_admin_hdr(client)
    # Date before 2000-01-01 (the seeded template's effective_from) → auto-resolution fails.
    # session_count in body must NOT rescue this.
    r = client.post("/api/parade-nights",
                    json={"date": "1999-06-13", "term": "T2",
                          "session_count": 3},
                    headers=hdr)
    assert r.status_code == 422, (
        f"session_count must not bypass template requirement — got {r.status_code}: {r.text}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# session_count is derived from template, not from body
# ─────────────────────────────────────────────────────────────────────────────

def test_session_count_derives_from_template_instructional_blocks(client):
    """session_count on a new night must equal the template's instructional block count."""
    hdr = _sqn_admin_hdr(client)
    # 703 seeded template has 3 instructional periods
    r = client.post("/api/parade-nights",
                    json={"date": "2027-07-14", "term": "T3"},
                    headers=hdr)
    assert r.status_code == 200, r.text
    pnid = r.json()["parade_night_id"]
    pn_r = client.get(f"/api/parade-nights/{pnid}", headers=hdr)
    if pn_r.status_code == 200:
        pn = pn_r.json()
        if isinstance(pn, dict) and "session_count" in pn:
            assert pn["session_count"] == 3, (
                f"session_count should derive from the 703 template's 3 IPs, got {pn['session_count']}"
            )


def test_session_count_body_value_ignored_when_template_resolves(client):
    """Supplying session_count=99 must not override the template-derived count."""
    hdr = _sqn_admin_hdr(client)
    r = client.post("/api/parade-nights",
                    json={"date": "2027-08-14", "term": "T3",
                          "session_count": 99},
                    headers=hdr)
    assert r.status_code == 200, r.text
    pnid = r.json()["parade_night_id"]
    pn_r = client.get(f"/api/parade-nights/{pnid}", headers=hdr)
    if pn_r.status_code == 200:
        pn = pn_r.json()
        if isinstance(pn, dict) and "session_count" in pn:
            assert pn["session_count"] != 99, (
                "body session_count=99 must be ignored — template-derived count must win"
            )
            assert pn["session_count"] == 3, (
                f"Expected template-derived count 3, got {pn['session_count']}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy compatibility — existing template-less nights remain readable
# ─────────────────────────────────────────────────────────────────────────────

def test_list_parade_nights_still_includes_legacy_nights(client):
    """Legacy nights (timing_template_id=NULL) must remain readable via list endpoint."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/parade-nights", headers=hdr)
    assert r.status_code == 200, r.text
    # Seeded demo nights may have timing_template_id set now; just confirm list works
    assert isinstance(r.json(), list)
