"""Router-local allow/deny gates moved into permissions.py (C3, 2026-10-09).

Each predicate is checked against the inline expression it replaced, over
every role plus an unrecognised one, so the move is provably an exact
replacement. Endpoint-level proof: tests/test_scope_parity.py (status and
body of every gate, every principal, identical before and after).
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import permissions as P

ROLES = sorted(P.ROLES) + ["retired_role"]


def _p(role, wing_id="w", squadron_id="s", acting_squadron_id=None):
    return P.Principal(user_id="u", role=role, wing_id=wing_id, squadron_id=squadron_id,
                       national_id="n", acting_squadron_id=acting_squadron_id)


def _detail(fn):
    try:
        fn()
    except HTTPException as e:
        return e.status_code, e.detail
    return None


@pytest.mark.parametrize("role", ROLES)
def test_may_move_account_to_another_squadron(role):          # accounts.change_scope
    assert P.may_move_account_to_another_squadron(_p(role)) == (role != "sqn_admin")


@pytest.mark.parametrize("role", ROLES)
def test_is_oversight_role(role):                              # jobs.get_job
    old = role in ("wing_admin", "wing_viewer", "national_admin", "national_viewer",
                   "system_admin", "auditor")
    assert P.is_oversight_role(_p(role)) == old


@pytest.mark.parametrize("role", ROLES)
def test_may_change_unit_type(role):                           # organisations.update_squadron
    assert P.may_change_unit_type(_p(role)) == (role != "sqn_admin")


@pytest.mark.parametrize("role", ROLES)
def test_may_list_service_tickets(role):                       # service_desk.list_tickets
    assert P.may_list_service_tickets(_p(role)) == (role not in ("auditor", "sqn_general"))


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("a_role,a_wing", [("wing_admin", "w"), ("wing_admin", "x"),
                                           ("national_admin", None), ("system_admin", None)])
def test_assignee_outside_wing_admin_authority(role, a_role, a_wing):   # service_desk.update_ticket x2
    p, a = _p(role), SimpleNamespace(role=a_role, wing_id=a_wing)
    old = p.role == "wing_admin" and (a.role != "wing_admin" or a.wing_id != p.wing_id)
    assert P.assignee_outside_wing_admin_authority(p, a) == old


@pytest.mark.parametrize("role", ["system_admin", "national_admin", "wing_admin"])
@pytest.mark.parametrize("scope,wing_id", [("system", None), ("national", None), ("wing", "w"),
                                           ("wing", "x"), ("wing", None)])
def test_may_write_email_config(role, scope, wing_id):        # service_desk.upsert_email_config
    p = _p(role)
    # The old inline checks, run after require_role(system/national/wing admin).
    refused = False
    if p.role == "wing_admin":
        refused = scope != "wing" or wing_id != p.wing_id
    elif p.role == "national_admin":
        refused = scope not in ("national", "system") or scope == "system"
    assert P.may_write_email_config(p, scope, wing_id) == (not refused)


@pytest.mark.parametrize("role", [r for r in ROLES if r not in ("system_admin", "national_admin", "wing_admin")])
def test_may_write_email_config_refuses_every_other_role(role):
    assert not P.may_write_email_config(_p(role), "wing", "w")


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("unit_id,wing_id", [("s", "w"), ("x", "w"), ("s", "x"), (None, "w"), (None, None)])
def test_planning_year_outside_scope(role, unit_id, wing_id):  # planning._require_year_access
    p = _p(role)
    old = False
    if p.role in ("sqn_admin", "sqn_general"):
        old = unit_id != p.squadron_id
    elif p.role == "wing_admin":
        old = wing_id != p.wing_id
    elif p.role in ("wing_viewer", "national_viewer", "auditor"):
        old = p.role == "wing_viewer" and wing_id != p.wing_id
    assert P.planning_year_outside_scope(p, unit_id, wing_id) == old


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("sqn_wing", ["w", "x"])
def test_proxy_mode_for(role, sqn_wing):                       # organisations.enter_proxy
    p = _p(role)
    if p.role == "wing_admin":
        expected = (403, {"error": "out_of_scope"}) if sqn_wing != p.wing_id else "proxy"
    elif p.role in ("national_admin", "system_admin"):
        expected = "delegated_intervention"
    else:
        expected = (403, {"error": "forbidden"})
    got = _detail(lambda: P.proxy_mode_for(p, sqn_wing))
    assert (got if got else P.proxy_mode_for(p, sqn_wing)) == expected


class _DB:
    def __init__(self, sqn):
        self.sqn = sqn

    def get(self, _model, _id):
        return self.sqn


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("target", ["s", "other-in-w", "other-in-x", "missing"])
def test_require_can_write_flight(role, target):               # accounts._can_write_flight
    sqn = None if target == "missing" else SimpleNamespace(
        id=target, wing_id="x" if target == "other-in-x" else "w")
    p = _p(role)
    if p.role in ("national_admin", "system_admin"):
        expected = None
    elif p.role == "wing_admin":
        expected = None if sqn and sqn.wing_id == p.wing_id else (403, {"error": "out_of_scope"})
    elif p.role == "sqn_admin":
        expected = None if target == p.squadron_id else (403, {"error": "out_of_scope"})
    else:
        expected = (403, {"error": "forbidden"})
    assert _detail(lambda: P.require_can_write_flight(p, target, _DB(sqn))) == expected


def _old_squadron_reference_gate(p, squadron_id, noun):
    """Verbatim from training._can_create_phase / _can_create_tag (squadron scope)."""
    if p.role == "sqn_admin":
        if squadron_id and squadron_id != p.squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                             "message": f"Squadron admin can only create {noun}s for their own squadron."})
    elif p.role == "wing_admin":
        if not p.acting_squadron_id:
            raise HTTPException(403, detail={"error": "proxy_required",
                                             "message": f"Wing Admin must enter Proxy Mode to create a squadron-scope {noun}."})
        if squadron_id and squadron_id != p.acting_squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                             "message": f"Can only create a squadron-scope {noun} for the squadron currently in Proxy Mode."})
    elif p.role in ("national_admin", "system_admin"):
        if not p.acting_squadron_id:
            raise HTTPException(403, detail={"error": "intervention_required",
                                             "message": f"National Admin must enter Delegated Intervention Mode to create a squadron-scope {noun}."})
        if squadron_id and squadron_id != p.acting_squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                             "message": f"Can only create a squadron-scope {noun} for the squadron currently in Delegated Intervention Mode."})
    else:
        raise HTTPException(403, detail={"error": "forbidden"})


@pytest.mark.parametrize("noun", ["phase", "tag"])
@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("acting", [None, "s", "a"])
@pytest.mark.parametrize("target", [None, "s", "a", "z"])
def test_require_can_create_squadron_reference(noun, role, acting, target):  # training phase/tag
    p = _p(role, acting_squadron_id=acting)
    assert _detail(lambda: P.require_can_create_squadron_reference(p, target, noun)) == \
        _detail(lambda: _old_squadron_reference_gate(p, target, noun))
