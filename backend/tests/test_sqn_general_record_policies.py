"""sqn_general and cadet records / session outcomes: one named policy each.

Twelve training endpoints each carried an inline `if p.role == "sqn_general":
raise 403` check. They now call two named policies in permissions.py. This
pins the observable contract the inline checks had -- 403 with exactly
{"error": "forbidden"} for sqn_general, raised before any lookup -- and that
the gate does not block the roles it never blocked.
"""
import pytest

from app.permissions import Principal, may_record_session_outcomes, may_view_cadet_records
from tests.conftest import login

MISSING = "00000000-0000-0000-0000-000000000000"

CADET_RECORD_READS = [
    ("GET", "/api/cadets", None),
    ("GET", "/api/cadets/risk", None),
    ("GET", f"/api/cadets/{MISSING}/class-memberships", None),
    ("GET", f"/api/training-classes/{MISSING}/members", None),
    ("GET", "/api/sessions/needs-attention", None),
    ("GET", f"/api/training-classes/{MISSING}/roster", None),
    ("GET", f"/api/training-records?class_id={MISSING}", None),
    ("GET", f"/api/training-records/export?class_id={MISSING}", None),
    ("GET", f"/api/cadets/{MISSING}/training-record", None),
]
SESSION_OUTCOME_WRITES = [
    ("POST", f"/api/sessions/{MISSING}/deliver", {"delivery_note": "note"}),
    ("POST", f"/api/sessions/{MISSING}/cancel", {"cancellation_reason": "reason"}),
    ("POST", f"/api/sessions/{MISSING}/reschedule", {"parade_night_id": MISSING}),
]
ALL = CADET_RECORD_READS + SESSION_OUTCOME_WRITES


def _call(client, method, url, body, hdr):
    return client.request(method, url, json=body, headers=hdr)


@pytest.mark.parametrize("method,url,body", ALL)
def test_sqn_general_gets_exactly_the_forbidden_contract(client, method, url, body):
    r = _call(client, method, url, body, login(client, "703SQN2026"))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == {"error": "forbidden"}


@pytest.mark.parametrize("method,url,body", ALL)
def test_sqn_admin_is_not_stopped_by_this_gate(client, method, url, body):
    r = _call(client, method, url, body, login(client, "ADMIN703"))
    assert r.status_code != 403 or r.json().get("detail") != {"error": "forbidden"}, r.text


def _p(role):
    return Principal(user_id="u", role=role, squadron_id="s", wing_id="w", national_id="n")


@pytest.mark.parametrize("role", ["sqn_admin", "wing_viewer", "wing_admin", "national_viewer",
                                  "national_admin", "auditor", "system_admin"])
def test_only_sqn_general_is_excluded_by_the_named_policies(role):
    assert may_view_cadet_records(_p(role)) and may_record_session_outcomes(_p(role))


def test_sqn_general_is_excluded_by_both_named_policies():
    assert not may_view_cadet_records(_p("sqn_general"))
    assert not may_record_session_outcomes(_p("sqn_general"))
