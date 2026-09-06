"""Tests for Parade Night workflow fixes.

Covers:
1. POST /api/parade-nights preserves notes separately from parade_type.
2. GET /api/parade-nights/{id}/template-impact correctly reflects session-based
   current_periods for legacy nights (no timing snapshot).
"""
import pytest
from datetime import date, timedelta

from tests.conftest import login


_BASE = date(2043, 7, 1)  # far-future; no effective template seeded for this range


def _admin(client):
    return login(client, "ADMIN703")


def _pn(client, hdr, days_ahead=0, **extra):
    """Create a parade night for 703's squadron and return its full _pn_dict."""
    base = _BASE + timedelta(days=days_ahead)
    if base.weekday() == 4:          # skip Fridays
        base += timedelta(days=1)
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    r = client.post("/api/parade-nights", json={
        "squadron_id": me["squadron_id"],
        "wing_id": me["wing_id"],
        "date": base.isoformat(),
        "parade_type": "normal",
        **extra,
    }, headers=hdr)
    assert r.status_code in (200, 201), r.text
    pn_id = r.json()["parade_night_id"]
    # POST returns only {ok, parade_night_id}; fetch full dict via planner
    p = client.get(f"/api/parade-nights/{pn_id}/planner", headers=hdr)
    assert p.status_code == 200, p.text
    return p.json()["parade_night"]


def _any_template(client, hdr):
    """Return the id of the first active timing template, or None."""
    r = client.get("/api/timing-templates", headers=hdr)
    assert r.status_code == 200, r.text
    active = [t for t in r.json() if not t.get("is_archived")]
    return active[0]["id"] if active else None


# ── notes preservation ────────────────────────────────────────────────────────

def test_create_pn_notes_saved_separately(client):
    """Backend saves notes in the notes field, not in parade_type."""
    hdr = _admin(client)
    data = _pn(client, hdr, days_ahead=0, notes="Officer cadet review")
    assert data["notes"] == "Officer cadet review"
    assert data["parade_type"] == "normal"


def test_create_pn_parade_type_unchanged_by_notes(client):
    """notes value must not end up as parade_type — they are separate fields."""
    hdr = _admin(client)
    data = _pn(client, hdr, days_ahead=5, notes="Homecoming parade")
    assert data["parade_type"] == "normal", (
        f"parade_type is '{data['parade_type']}', expected 'normal'. "
        "Likely cause: frontend addPN() sends notes value as parade_type."
    )
    assert data["parade_type"] != "Homecoming parade"


# ── template-impact for legacy nights ─────────────────────────────────────────

def test_template_impact_legacy_night_shows_session_periods(client):
    """For a legacy night (no snapshot), template-impact derives current_periods
    from session rows, not from the empty snapshot table.

    BUG: current_periods = {} → retained_periods = [], added_periods = all N new
    FIX: current_periods = {1,2} → retained_periods includes 1 and 2, added_periods
         excludes them.
    """
    hdr = _admin(client)
    pn = _pn(client, hdr, days_ahead=10)
    pn_id = pn["parade_night_id"]

    # If the squadron has an auto-resolved template for this date, the night
    # is not legacy — skip rather than testing wrong precondition.
    if pn.get("timing_template_id"):
        pytest.skip("Squadron has effective template for this date — not a legacy night")

    new_tmpl_id = _any_template(client, hdr)
    if not new_tmpl_id:
        pytest.skip("No timing templates in test DB")

    # First call — no sessions: everything is "added" (no current_periods)
    r0 = client.get(f"/api/parade-nights/{pn_id}/template-impact",
                    params={"new_template_id": new_tmpl_id}, headers=hdr)
    assert r0.status_code == 200, r0.text
    d0 = r0.json()
    new_period_count = len(d0["added_periods"])
    if new_period_count < 2:
        pytest.skip("Test template has < 2 periods; cannot create sessions at period 2")

    # Create sessions at periods 1 and 2
    for period in [1, 2]:
        s = client.post("/api/sessions", json={
            "parade_night_id": pn_id,
            "period_number": period,
            "cadet_group": "senior",
        }, headers=hdr)
        assert s.status_code in (200, 201), s.text

    # Second call — sessions now exist at periods 1 and 2
    r1 = client.get(f"/api/parade-nights/{pn_id}/template-impact",
                    params={"new_template_id": new_tmpl_id}, headers=hdr)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()

    # With the fix: retained ∪ removed must include 1 and 2 (they are current)
    current_seen = set(d1["retained_periods"]) | set(d1["removed_periods"])
    assert 1 in current_seen, (
        f"Period 1 not in retained/removed {d1} — "
        "template-impact not reading session period_numbers for legacy nights"
    )
    assert 2 in current_seen, (
        f"Period 2 not in retained/removed {d1} — "
        "template-impact not reading session period_numbers for legacy nights"
    )
    # Critically: added_periods must NOT include 1 or 2 (those sessions exist)
    assert 1 not in d1["added_periods"], f"Period 1 wrongly in added_periods: {d1}"
    assert 2 not in d1["added_periods"], f"Period 2 wrongly in added_periods: {d1}"
