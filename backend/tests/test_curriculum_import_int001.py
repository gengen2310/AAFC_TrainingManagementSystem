"""Regression: INT-001 — curriculum import endpoints validate squadron existence.

POST /api/curriculum/import and POST /api/curriculum/import-xlsm accepted any
squadron_id string, including nonexistent UUIDs, without confirming the
referenced squadron exists. This caused silent orphan creation rather than a
useful error.

Coverage:
- valid squadron_id → 200 (import proceeds)
- nonexistent squadron_id → 404 with error=squadron_not_found
- missing squadron_id → 200 (national import, no squad check needed)
- malformed UUID → well-formed 4xx, not 500
"""
import uuid
from tests.conftest import login


def _nat_admin_hdr(client):
    return login(client, "ADMINNATIONAL")


def _minimal_import_body(squadron_id=None, owning_level="national"):
    return {
        "owning_level": owning_level,
        "squadron_id": squadron_id,
        "items": [
            {
                "code": "INT001-TEST",
                "title": "INT-001 Regression Item",
                "phase": "E. Senior",
                "element": "Fitness",
                "duration_minutes": 60,
                "part_number": 1,
            }
        ],
    }


# ─── POST /api/curriculum/import ─────────────────────────────────────────────

def test_import_rejects_nonexistent_squadron_id(client):
    hdr = _nat_admin_hdr(client)
    nonexistent = str(uuid.uuid4())
    r = client.post("/api/curriculum/import",
                    json=_minimal_import_body(squadron_id=nonexistent),
                    headers=hdr)
    assert r.status_code == 404, (
        f"Expected 404 for nonexistent squadron_id, got {r.status_code}: {r.text}"
    )
    body = r.json()
    assert body.get("detail", {}).get("error") == "squadron_not_found", (
        f"Expected error=squadron_not_found, got: {body}"
    )


def test_import_accepts_no_squadron_id(client):
    """National import with no squadron_id must succeed without squadron check."""
    hdr = _nat_admin_hdr(client)
    r = client.post("/api/curriculum/import",
                    json=_minimal_import_body(squadron_id=None),
                    headers=hdr)
    assert r.status_code == 200, r.text


def test_import_accepts_valid_squadron_id(client):
    """A squadron that exists must be accepted and the import must proceed."""
    hdr = _nat_admin_hdr(client)
    squadrons = client.get("/api/squadrons", headers=hdr)
    assert squadrons.status_code == 200, squadrons.text
    sqns = squadrons.json()
    if not sqns:
        import pytest; pytest.skip("no squadrons in seed data")
    sqn_id = sqns[0]["squadron_id"]

    r = client.post("/api/curriculum/import",
                    json=_minimal_import_body(squadron_id=sqn_id, owning_level="squadron"),
                    headers=hdr)
    assert r.status_code == 200, r.text


def test_import_malformed_uuid_does_not_500(client):
    """A garbage string for squadron_id must return a clean 4xx, not 500."""
    hdr = _nat_admin_hdr(client)
    r = client.post("/api/curriculum/import",
                    json=_minimal_import_body(squadron_id="not-a-uuid"),
                    headers=hdr)
    assert r.status_code in (400, 404, 422), (
        f"Malformed squadron_id returned {r.status_code} instead of a clean 4xx"
    )
    assert r.status_code != 500, "500 returned for malformed squadron_id — must return clean error"
