"""Tests for POST /api/exceptions/run-checks.

The endpoint clears prior automation action items then creates new ones for:
  - sessions within 0-7 days that have no facilitator assigned
  - sessions within 0-3 days that have no room assigned

A non-Friday date 3 days from now is used for all parade-night fixtures so
tests avoid collisions with seed_all()'s Friday-based 703 squadron data.
"""
from datetime import date, timedelta

from tests.conftest import login

_ADM703 = "ADMIN703"
_ADM7WG = "ADMIN7WG"


def _imminent_date():
    """Return a non-Friday date 3 days from now (inside both 7-day and 3-day windows)."""
    d = date.today() + timedelta(days=3)
    if d.weekday() == 4:  # skip Friday — collision with seed_all() Fridays
        d += timedelta(days=1)
    return d.isoformat()


def _me(client, hdr):
    return client.get("/api/auth/me", headers=hdr).json()["session"]


def _create_pn(client, hdr, sqn_id, wing_id, on_date):
    r = client.post("/api/parade-nights", headers=hdr,
                    json={"squadron_id": sqn_id, "wing_id": wing_id,
                          "date": on_date, "parade_type": "normal"})
    assert r.status_code in (200, 201), r.text
    data = r.json()
    return data.get("parade_night_id") or data.get("id")


def _create_session(client, hdr, pn_id, period=1, facilitator_id=None):
    body = {"parade_night_id": pn_id, "period_number": period}
    if facilitator_id:
        body["facilitator_id"] = facilitator_id
    r = client.post("/api/sessions", headers=hdr, json=body)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    return data.get("session_id") or data.get("id")


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_run_checks_unauthenticated(client):
    r = client.post("/api/exceptions/run-checks")
    assert r.status_code == 401


# ── Happy path ────────────────────────────────────────────────────────────────

def test_run_checks_returns_created_count(client):
    hdr = login(client, _ADM703)
    r = client.post("/api/exceptions/run-checks", headers=hdr)
    assert r.status_code == 200
    assert "created" in r.json()
    assert isinstance(r.json()["created"], int)


def test_run_checks_no_squadron_returns_zero(client):
    # wing_admin has no active squadron — endpoint must return 0, not error
    hdr = login(client, _ADM7WG)
    r = client.post("/api/exceptions/run-checks", headers=hdr)
    assert r.status_code == 200
    assert r.json()["created"] == 0


# ── Alert creation ────────────────────────────────────────────────────────────

def test_run_checks_flags_session_without_facilitator(client):
    hdr = login(client, _ADM703)
    me = _me(client, hdr)
    sqn_id, wing_id = me["squadron_id"], me["wing_id"]
    on_date = _imminent_date()

    pn_id = _create_pn(client, hdr, sqn_id, wing_id, on_date)
    _create_session(client, hdr, pn_id)  # no facilitator

    r = client.post("/api/exceptions/run-checks", headers=hdr)
    assert r.status_code == 200
    created = r.json()["created"]
    assert created >= 1, f"expected ≥1 alert for unfacilitated session, got {created}"

    items = client.get("/api/action-items", headers=hdr).json()
    auto = [i for i in items if i["source"] == "automation" and i["status"] == "open"]
    titles = [i["title"] for i in auto]
    assert any("Facilitator" in t for t in titles), f"expected a facilitator-needed alert; got {titles}"


def test_run_checks_idempotent(client):
    # Running twice must not accumulate alerts — the endpoint clears prior
    # automation items before creating new ones so the count stays stable.
    hdr = login(client, _ADM703)
    r1 = client.post("/api/exceptions/run-checks", headers=hdr)
    r2 = client.post("/api/exceptions/run-checks", headers=hdr)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["created"] == r2.json()["created"], (
        "idempotency broken: second run produced a different count than the first"
    )
    items = client.get("/api/action-items", headers=hdr).json()
    open_auto = [i for i in items if i["source"] == "automation" and i["status"] == "open"]
    assert len(open_auto) == r2.json()["created"], (
        f"open automation alerts ({len(open_auto)}) do not match reported count ({r2.json()['created']})"
    )


def test_run_checks_audited(client):
    hdr = login(client, _ADM703)
    r = client.post("/api/exceptions/run-checks", headers=hdr)
    assert r.status_code == 200
    audit = client.get("/api/audit", headers=hdr).json()
    assert any(e.get("action") == "run_checks" and e.get("object_type") == "automation" for e in audit)
