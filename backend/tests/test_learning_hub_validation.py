"""REM-19 (original_instruction.md Section 20): Learning Hub link validation report.

Covers GET /api/curriculum/learning-hub/validation -- a read-only report
flagging curriculum items whose learning_hub_url doesn't match their own
identifier, or that are missing a link entirely. Never invents or corrects
a URL; only flags for human review against the real Learning Hub site.
"""
from tests.conftest import login


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _general(client):
    return login(client, "703SQN2026")


def _create_item(client, hdr, *, identifier, learning_hub_url, code="TEST-CODE"):
    r = client.post("/api/curriculum", json={
        "code": code, "title": "Test item", "identifier": identifier,
        "learning_hub_url": learning_hub_url,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["curriculum_id"]


def test_requires_auth(client):
    r = client.get("/api/curriculum/learning-hub/validation")
    assert r.status_code == 401


def test_forbidden_for_read_only_role(client):
    hdr = _general(client)
    r = client.get("/api/curriculum/learning-hub/validation", headers=hdr)
    assert r.status_code == 403


def test_matching_url_not_flagged(client):
    sqn_hdr = _sqn_admin(client)
    wing_hdr = _wing_admin(client)
    _create_item(client, sqn_hdr, identifier="LHV-M01-01",
                 learning_hub_url="https://airforcecadets.net.au/lh/LHV-M01-01")
    r = client.get("/api/curriculum/learning-hub/validation", headers=wing_hdr)
    assert r.status_code == 200
    flagged_ids = {f["identifier"] for f in r.json()["flagged"]}
    assert "LHV-M01-01" not in flagged_ids


def test_truncated_url_flagged_as_identifier_mismatch(client):
    """Regression for the exact real-world defect the audit found: a URL
    slug missing the identifier's phase prefix (e.g. "M00-01" instead of
    "INL-M00-01")."""
    sqn_hdr = _sqn_admin(client)
    wing_hdr = _wing_admin(client)
    _create_item(client, sqn_hdr, identifier="LHV-M02-01",
                 learning_hub_url="https://airforcecadets.net.au/lh/M02-01")
    r = client.get("/api/curriculum/learning-hub/validation", headers=wing_hdr)
    assert r.status_code == 200
    flagged = {f["identifier"]: f for f in r.json()["flagged"]}
    assert "LHV-M02-01" in flagged
    assert flagged["LHV-M02-01"]["issue"] == "identifier_mismatch"
    # The report must never correct or invent a URL -- only surface the
    # existing one for human review.
    assert flagged["LHV-M02-01"]["learning_hub_url"] == "https://airforcecadets.net.au/lh/M02-01"


def test_missing_link_flagged(client):
    sqn_hdr = _sqn_admin(client)
    wing_hdr = _wing_admin(client)
    _create_item(client, sqn_hdr, identifier="LHV-M03-01", learning_hub_url=None)
    r = client.get("/api/curriculum/learning-hub/validation", headers=wing_hdr)
    assert r.status_code == 200
    flagged = {f["identifier"]: f for f in r.json()["flagged"]}
    assert "LHV-M03-01" in flagged
    assert flagged["LHV-M03-01"]["issue"] == "missing_link"


def test_ambiguous_non_slug_url_still_flagged_for_review(client):
    """A completion-page-style URL (e.g. an opaque node ID) unrelated to the
    identifier is exactly the "cannot be resolved without checking Learning
    Hub itself" case (Section 20 point 6) -- it must be surfaced, not
    silently accepted as correct."""
    sqn_hdr = _sqn_admin(client)
    wing_hdr = _wing_admin(client)
    _create_item(client, sqn_hdr, identifier="LHV-M04-99",
                 learning_hub_url="https://airforcecadets.net.au/lh/node/375")
    r = client.get("/api/curriculum/learning-hub/validation", headers=wing_hdr)
    assert r.status_code == 200
    flagged_ids = {f["identifier"] for f in r.json()["flagged"]}
    assert "LHV-M04-99" in flagged_ids


def test_trailing_slash_and_case_do_not_cause_false_positive(client):
    sqn_hdr = _sqn_admin(client)
    wing_hdr = _wing_admin(client)
    _create_item(client, sqn_hdr, identifier="LHV-M05-01",
                 learning_hub_url="https://airforcecadets.net.au/lh/lhv-m05-01/")
    r = client.get("/api/curriculum/learning-hub/validation", headers=wing_hdr)
    assert r.status_code == 200
    flagged_ids = {f["identifier"] for f in r.json()["flagged"]}
    assert "LHV-M05-01" not in flagged_ids
