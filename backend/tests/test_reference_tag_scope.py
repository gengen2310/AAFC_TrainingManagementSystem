"""Scope isolation for all five user-creatable reference-data tag tables.

These five endpoints share one copy-pasted create path, and therefore shared
one defect: the duplicate check ORed the scope columns independently, so
``wing_id == <my wing>`` matched every tag anywhere in the wing. Two
consequences, both proven by the tests below:

  * a squadron could not create a tag whose name a sibling squadron had used;
  * the resulting 409 body returned the sibling's tag id (Part 82: no
    cross-squadron IDOR).

A tag must conflict only with its own scope or an ancestor scope that already
covers it -- never with a sibling.
"""
import pytest
from conftest import login

# (endpoint, human name) -- all five share one shape.
TAG_ENDPOINTS = [
    ("subject-area-tags", "subject area"),
    ("facilitator-type-tags", "facilitator type"),
    ("session-status-reason-tags", "session status reason"),
    ("activity-type-tags", "activity type"),
    ("training-area-capability-tags", "training area capability"),
]


@pytest.mark.parametrize("endpoint,label", TAG_ENDPOINTS)
def test_sibling_squadron_may_reuse_a_tag_name(client, endpoint, label):
    """703 naming a tag must not stop 704 naming its own tag the same."""
    name = f"Sibling Reuse {label}"
    h703 = login(client, "ADMIN703")
    r = client.post(f"/api/{endpoint}", headers=h703,
                    json={"display_name": name, "scope": "squadron"})
    assert r.status_code == 201, r.text
    tag_703 = r.json()["tag_id"]

    h704 = login(client, "ADMIN704")
    r2 = client.post(f"/api/{endpoint}", headers=h704,
                     json={"display_name": name, "scope": "squadron"})
    assert r2.status_code == 201, (
        f"704 was blocked by 703's {label} tag: {r2.status_code} {r2.text}"
    )
    assert r2.json()["tag_id"] != tag_703


@pytest.mark.parametrize("endpoint,label", TAG_ENDPOINTS)
def test_conflict_body_never_leaks_a_sibling_tag_id(client, endpoint, label):
    """A 409 must never name a tag the caller cannot see."""
    name = f"Leak Check {label}"
    h703 = login(client, "ADMIN703")
    r = client.post(f"/api/{endpoint}", headers=h703,
                    json={"display_name": name, "scope": "squadron"})
    assert r.status_code == 201, r.text
    tag_703 = r.json()["tag_id"]

    h704 = login(client, "ADMIN704")
    r2 = client.post(f"/api/{endpoint}", headers=h704,
                     json={"display_name": name, "scope": "squadron"})
    if r2.status_code == 409:
        assert r2.json()["detail"].get("existing_id") != tag_703, (
            f"409 body leaked 703's {label} tag id to 704"
        )


@pytest.mark.parametrize("endpoint,label", TAG_ENDPOINTS)
def test_squadron_tag_not_visible_to_sibling_squadron(client, endpoint, label):
    """703's squadron-scoped tag must not appear in 704's list."""
    name = f"Visibility {label}"
    h703 = login(client, "ADMIN703")
    r = client.post(f"/api/{endpoint}", headers=h703,
                    json={"display_name": name, "scope": "squadron"})
    assert r.status_code == 201, r.text
    tag_703 = r.json()["tag_id"]

    h704 = login(client, "ADMIN704")
    listing = client.get(f"/api/{endpoint}", headers=h704)
    assert listing.status_code == 200, listing.text
    assert tag_703 not in [t["tag_id"] for t in listing.json()]


@pytest.mark.parametrize("endpoint,label", TAG_ENDPOINTS)
def test_same_squadron_duplicate_still_rejected(client, endpoint, label):
    """The genuine conflict must survive the fix: 703 twice is still a 409."""
    name = f"Genuine Dup {label}"
    h703 = login(client, "ADMIN703")
    r = client.post(f"/api/{endpoint}", headers=h703,
                    json={"display_name": name, "scope": "squadron"})
    assert r.status_code == 201, r.text
    r2 = client.post(f"/api/{endpoint}", headers=h703,
                     json={"display_name": name, "scope": "squadron"})
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["existing_id"] == r.json()["tag_id"]


@pytest.mark.parametrize("endpoint,label", TAG_ENDPOINTS)
def test_global_tag_still_blocks_a_squadron_duplicate(client, endpoint, label):
    """Ancestor scopes must still conflict: a global tag covers the squadron."""
    name = f"Ancestor {label}"
    hsys = login(client, "SYSADMIN2026")
    r = client.post(f"/api/{endpoint}", headers=hsys,
                    json={"display_name": name, "scope": "global"})
    assert r.status_code == 201, r.text
    global_id = r.json()["tag_id"]

    h703 = login(client, "ADMIN703")
    r2 = client.post(f"/api/{endpoint}", headers=h703,
                     json={"display_name": name, "scope": "squadron"})
    assert r2.status_code == 409, (
        f"global {label} tag failed to block a squadron duplicate: {r2.text}"
    )
    assert r2.json()["detail"]["existing_id"] == global_id

    # The suite seeds once per session and never resets, and
    # test_session_status_reason_tags asserts an exact global count. Archive the
    # tag so this test leaves the global set exactly as it found it.
    cleanup = client.delete(f"/api/{endpoint}/{global_id}", headers=hsys)
    assert cleanup.status_code == 200, cleanup.text


@pytest.mark.parametrize("endpoint,label", TAG_ENDPOINTS)
def test_national_id_recorded_on_created_tag(client, endpoint, label):
    """Every tag records the national entity it belongs to (v60)."""
    h703 = login(client, "ADMIN703")
    r = client.post(f"/api/{endpoint}", headers=h703,
                    json={"display_name": f"National Stamp {label}", "scope": "squadron"})
    assert r.status_code == 201, r.text
    assert "national_id" in r.json(), f"{label} tag does not expose national_id"
