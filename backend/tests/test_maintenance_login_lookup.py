"""Maintenance audit (brief §43-45): the sign-in flow must stay usable.

Production sign-in is two calls: POST /api/auth/lookup (unit + role -> user_id)
then POST /api/auth/login. Only /login was exempt from the maintenance gate;
/lookup is a POST, so the gate treated it as a WRITE and returned 503 in every
locked window -- even with block_logins=False -- meaning nobody, including a
system_admin whose session had expired, could start a sign-in through the UI.
"""
from tests.test_maintenance_enforcement import (
    _disable_maintenance, _enable_maintenance_opts, _sysadmin)

_SA_LOOKUP = {"unit_type": "national", "role": "system_admin"}


def _signed_out(client):
    """A browser starting a fresh sign-in carries no session cookie. Without
    this the TestClient replays the system_admin cookie set by _sysadmin(),
    and the gate's system_admin bypass hides the defect."""
    client.cookies.clear()
    return client
_SQN_LOOKUP = {"unit_type": "squadron", "identifier": "703", "role": "sqn_admin"}


def test_lookup_is_not_blocked_by_default_maintenance(client):
    sa = _sysadmin(client)
    sqn = client.post("/api/auth/login", json={"code": "ADMIN703"}).json()["token"]
    _enable_maintenance_opts(client, sa)                 # writes blocked; logins allowed
    try:
        # Control: the gate really is locked (an ordinary write is refused).
        w = client.post("/api/facilitators", json={"first_name": "M", "last_name": "Gate"},
                        headers={"Authorization": f"Bearer {sqn}"})
        assert w.status_code == 503, w.status_code
        for body in (_SA_LOOKUP, _SQN_LOOKUP):
            r = _signed_out(client).post("/api/auth/lookup", json=body)
            assert r.status_code == 200, (body["role"], r.status_code, r.text)
        uid = _signed_out(client).post("/api/auth/lookup", json=_SQN_LOOKUP).json()["user_id"]
        assert client.post("/api/auth/login", json={"user_id": uid, "code": "ADMIN703"}).status_code == 200
    finally:
        _signed_out(client)
        _disable_maintenance(client, sa)


def test_system_admin_can_sign_in_via_lookup_when_logins_are_blocked(client):
    sa = _sysadmin(client)
    _enable_maintenance_opts(client, sa, block_logins=True)
    try:
        r = _signed_out(client).post("/api/auth/lookup", json=_SA_LOOKUP)
        assert r.status_code == 200, r.text
        r = client.post("/api/auth/login", json={"user_id": r.json()["user_id"], "code": "SYSADMIN2026"})
        assert r.status_code == 200, "system_admin must be able to sign back in to end maintenance"
        # Everyone else still stopped at login (the handler's role-aware gate).
        uid = _signed_out(client).post("/api/auth/lookup", json=_SQN_LOOKUP).json()["user_id"]
        assert client.post("/api/auth/login", json={"user_id": uid, "code": "ADMIN703"}).status_code == 503
    finally:
        _signed_out(client)
        _disable_maintenance(client, sa)
