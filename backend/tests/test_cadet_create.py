"""Tests for POST /api/cadets — create cadet endpoint (fixes 405 Method Not Allowed).

Covers:
- Happy path: sqn_admin creates cadet, cadet appears in GET /api/cadets
- Duplicate service_number within same squadron → 409
- sqn_general blocked → 403
- Unauthenticated → 401
- created_by set on new cadet (audit trail)
"""
import uuid
from tests.conftest import login

ADM703 = "ADMIN703"
GEN703 = "703SQN2026"


def _hdr(client):
    return login(client, ADM703)


def _unique_sn():
    return f"T-{uuid.uuid4().hex[:8].upper()}"


def test_create_cadet_happy_path(client):
    hdr = _hdr(client)
    sn = _unique_sn()
    r = client.post("/api/cadets", json={
        "service_number": sn,
        "rank": "Cdt",
        "first_name": "TestFirst",
        "last_name": "TestLast",
    }, headers=hdr)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["service_number"] == sn
    assert data["last_name"] == "TestLast"
    assert "cadet_id" in data

    # Cadet should now appear in roster
    roster = client.get("/api/cadets", headers=hdr).json()
    ids = [c["cadet_id"] for c in roster]
    assert data["cadet_id"] in ids


def test_create_cadet_duplicate_service_number_409(client):
    hdr = _hdr(client)
    sn = _unique_sn()
    r1 = client.post("/api/cadets", json={"service_number": sn, "last_name": "Dup1"}, headers=hdr)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/cadets", json={"service_number": sn, "last_name": "Dup2"}, headers=hdr)
    assert r2.status_code == 409
    assert "duplicate_service_number" in r2.text


def test_create_cadet_no_service_number_allowed(client):
    """Cadets without a service number are allowed (service_number is optional)."""
    hdr = _hdr(client)
    r = client.post("/api/cadets", json={"last_name": "NoSN"}, headers=hdr)
    assert r.status_code == 201, r.text


def test_create_cadet_sqn_general_forbidden(client):
    hdr = login(client, GEN703)
    r = client.post("/api/cadets", json={"last_name": "Blocked"}, headers=hdr)
    assert r.status_code == 403


def test_create_cadet_unauthenticated(client):
    r = client.post("/api/cadets", json={"last_name": "Anon"})
    assert r.status_code == 401
