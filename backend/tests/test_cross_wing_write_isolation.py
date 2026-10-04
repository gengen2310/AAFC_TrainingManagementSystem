"""Cross-Wing write isolation for Wing Admins.

The rule "a Wing Admin acts only inside their own Wing" is checked at 14
places (permissions.wing_admin_outside_own_wing). Disabling it entirely
failed only 4 existing tests (2026-10-04): ten of the sites had no test that a
Wing Admin is refused another Wing's object. One test per uncovered site.

Each test creates the other Wing's objects as System Admin in a fresh Wing,
asserts 403 for 7WG's Wing Admin, and -- where cheap -- that the same action in
the admin's own Wing is not refused, so the 403 is the scope rule and not a
blanket denial.
"""
import uuid

import pytest

from tests.conftest import login


@pytest.fixture
def ctx(client):
    sys_hdr = login(client, "SYSADMIN2026")
    wing_hdr = login(client, "ADMIN7WG")
    me = client.get("/api/auth/me", headers=wing_hdr).json()["session"]
    tag = uuid.uuid4().hex[:5].upper()
    w = client.post("/api/wings", json={"code": f"Y{tag}", "name": f"Isolation Wing {tag}",
                                        "timezone": "Australia/Perth"}, headers=sys_hdr)
    assert w.status_code in (200, 201), w.text
    other_wing = w.json()["wing_id"]
    s = client.post("/api/squadrons", json={"wing_id": other_wing, "code": f"6{tag[:3]}",
                                            "name": f"Isolation Sqn {tag}"}, headers=sys_hdr)
    assert s.status_code == 200, s.text
    return dict(client=client, sys=sys_hdr, wing=wing_hdr, own_wing=me["wing_id"],
                other_wing=other_wing, other_sqn=s.json()["squadron_id"], tag=tag)


def _forbidden(r):
    assert r.status_code == 403, r.text


def _not_scope_refusal(r):
    assert r.status_code != 403, r.text


def test_create_wing_account_in_another_wing(ctx):          # accounts.py _validate_create_scope (wing)
    c = ctx["client"]
    _forbidden(c.post("/api/accounts", json={"display_name": "X", "role": "wing_viewer",
                                             "wing_id": ctx["other_wing"]}, headers=ctx["wing"]))


def test_create_squadron_account_in_another_wing(ctx):      # accounts.py _validate_create_scope (squadron)
    c = ctx["client"]
    _forbidden(c.post("/api/accounts", json={"display_name": "X", "role": "sqn_general",
                                             "squadron_id": ctx["other_sqn"]}, headers=ctx["wing"]))


def _archived_other_sqn(ctx):
    c = ctx["client"]
    assert c.post(f"/api/squadrons/{ctx['other_sqn']}/archive", headers=ctx["sys"]).status_code == 200
    return ctx["other_sqn"]


def test_restore_squadron_in_another_wing(ctx):             # organisations.py restore_squadron
    sid = _archived_other_sqn(ctx)
    _forbidden(ctx["client"].post(f"/api/squadrons/{sid}/restore", headers=ctx["wing"]))


def test_delete_squadron_in_another_wing(ctx):              # organisations.py delete_squadron
    sid = _archived_other_sqn(ctx)
    _forbidden(ctx["client"].delete(f"/api/squadrons/{sid}", headers=ctx["wing"]))


@pytest.mark.parametrize("path", ["/api/curriculum/elements", "/api/curriculum/phases"])
def test_create_wing_curriculum_reference_data_for_another_wing(ctx, path):   # training.py _can_create_element/_phase
    c, t = ctx["client"], ctx["tag"]
    body = {"name": f"Iso_{t}", "display_name": f"Iso {t}", "scope_level": "wing"}
    _forbidden(c.post(path, json=body | {"wing_id": ctx["other_wing"]}, headers=ctx["wing"]))
    _not_scope_refusal(c.post(path, json=body | {"name": f"Own_{t}", "display_name": f"Own {t}",
                                                 "wing_id": ctx["own_wing"]}, headers=ctx["wing"]))


def test_create_wing_tag_for_another_wing(ctx):              # training.py _can_create_tag
    c, t = ctx["client"], ctx["tag"]
    _forbidden(c.post("/api/subject-area-tags", json={"display_name": f"Iso {t}", "scope": "wing",
                                                       "wing_id": ctx["other_wing"]}, headers=ctx["wing"]))
    _not_scope_refusal(c.post("/api/subject-area-tags", json={"display_name": f"Own {t}", "scope": "wing",
                                                               "wing_id": ctx["own_wing"]}, headers=ctx["wing"]))


def test_create_event_on_another_wings_calendar(ctx):        # wing_calendar.py _require_write
    c = ctx["client"]
    body = {"title": "Iso event", "start_date": "2092-05-01"}
    _forbidden(c.post(f"/api/wing-calendar/events?wing_id={ctx['other_wing']}", json=body, headers=ctx["wing"]))
    _not_scope_refusal(c.post(f"/api/wing-calendar/events?wing_id={ctx['own_wing']}", json=body, headers=ctx["wing"]))


def test_update_service_ticket_from_another_wing(ctx):       # service_desk.py update_ticket
    c = ctx["client"]
    t = c.post("/api/service-desk/tickets", json={
        "rank": "CDT", "first_name": "Iso", "last_name": "Lation", "email": "iso@example.com",
        "squadron_id": ctx["other_sqn"], "wing_id": ctx["other_wing"], "description": "cross-wing isolation test",
    })
    assert t.status_code == 201, t.text
    tid = t.json().get("ticket_id") or t.json().get("id")
    _forbidden(c.patch(f"/api/service-desk/tickets/{tid}", json={"admin_notes": "x"}, headers=ctx["wing"]))


def test_edit_custom_phase_owned_by_another_wing(ctx):       # custom_phases.py _require_can_mutate
    c = ctx["client"]
    ph = c.post("/api/custom-training-phases", json={"name": f"Iso {ctx['tag']}", "scope_type": "wing",
                                                       "scope_id": ctx["other_wing"], "applies_from": "2092-01-01"},
                headers=ctx["sys"])
    assert ph.status_code in (200, 201), ph.text
    pid = ph.json().get("custom_phase_id") or ph.json().get("id")
    _forbidden(c.patch(f"/api/custom-training-phases/{pid}", json={"name": "renamed"}, headers=ctx["wing"]))
    _forbidden(c.delete(f"/api/custom-training-phases/{pid}", headers=ctx["wing"]))
