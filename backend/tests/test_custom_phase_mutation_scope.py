"""Who may rename or delete a custom training phase (D10, 2026-10-11).

`custom_phases._require_can_mutate` constrained each admin role only on its
own scope type and let every other scope type through, so a Squadron Admin
could rename or delete another Wing's Wing phase and any national or system
phase, and a Wing Admin any national or system phase (seen in the 2026-10-09
scope-parity snapshot; docs/stabilisation/role-check-classification.md).

The rule, as the guard's own docstring and create_custom_phase already state:

| phase scope | may mutate                                                         |
|-------------|--------------------------------------------------------------------|
| squadron    | that Squadron's Squadron Admin; System Admin                       |
| wing        | that Wing's Wing Admin; a National Admin of the Wing's national; System Admin |
| national    | that national's National Admin (never a NULL-scope pre-v61 row); System Admin |
| system      | National Admin; System Admin                                       |

Everything else is 403 `insufficient_scope`, and a refusal writes no audit row.
Phases are inserted directly so each scope pair is exact.
"""
import uuid

import pytest

from app.database import SessionLocal
from app.models import AuditLog, Squadron, User, Wing
from app.models.custom_phases import CustomTrainingPhase
from tests.conftest import login

SQN_ADMIN_703, SQN_ADMIN_704 = "ADMIN703", "ADMIN704"
WING_ADMIN_7WG, NAT_ADMIN, SYS_ADMIN = "ADMIN7WG", "ADMINNATIONAL", "SYSADMIN2026"
SQN_GENERAL, AUDITOR = "703SQN2026", "AUDITOR2026"


def _org(db):
    def user_of(code_role, sqn_code=None):
        q = db.query(User).filter(User.role == code_role)
        if sqn_code:
            q = q.join(Squadron, User.squadron_id == Squadron.id).filter(Squadron.code == sqn_code)
        return q.first()
    sqn703 = db.query(Squadron).filter(Squadron.code == "703").one()
    sqn704 = db.query(Squadron).filter(Squadron.code == "704").one()
    wing = db.get(Wing, sqn703.wing_id)
    return sqn703, sqn704, wing


@pytest.fixture
def phases(client):
    """One phase per scope pair; another Wing is created for the cross-Wing case."""
    db = SessionLocal()
    sqn703, sqn704, wing = _org(db)
    tag = uuid.uuid4().hex[:6]
    other_wing = Wing(code=f"Z{tag[:4].upper()}", name=f"D10 Wing {tag}", short_name=f"D10{tag[:3]}",
                      national_id=wing.national_id, timezone="Australia/Perth")
    db.add(other_wing)
    db.commit()
    other_wing_id = other_wing.id
    spec = {
        "sqn703": ("squadron", sqn703.id),
        "sqn704": ("squadron", sqn704.id),
        "wing_own": ("wing", wing.id),
        "wing_other": ("wing", other_wing_id),
        "national_own": ("national", wing.national_id),
        "national_other": ("national", str(uuid.uuid4())),
        "national_null": ("national", None),
        "system": ("system", None),
    }
    ids = {}
    for key, (stype, sid) in spec.items():
        ph = CustomTrainingPhase(name=f"D10 {key} {tag}", scope_type=stype, scope_id=sid,
                                 applies_from="2093-01-01")
        db.add(ph)
        db.flush()
        ids[key] = ph.id
    db.commit()
    db.close()
    yield ids
    db = SessionLocal()
    db.query(CustomTrainingPhase).filter(CustomTrainingPhase.id.in_(list(ids.values()))).delete(
        synchronize_session=False)
    db.query(Wing).filter(Wing.id == other_wing_id).delete()
    db.commit()
    db.close()


ALLOWED = {
    SQN_ADMIN_703: {"sqn703"},
    SQN_ADMIN_704: {"sqn704"},
    WING_ADMIN_7WG: {"wing_own"},
    NAT_ADMIN: {"wing_own", "wing_other", "national_own", "system"},
    SYS_ADMIN: {"sqn703", "sqn704", "wing_own", "wing_other", "national_own",
                "national_other", "national_null", "system"},
    SQN_GENERAL: set(),
    AUDITOR: set(),
}
CASES = [(code, key) for code in ALLOWED for key in
         ("sqn703", "sqn704", "wing_own", "wing_other", "national_own",
          "national_other", "national_null", "system")]


def _audit_rows(phase_id, action):
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.object_id == phase_id,
                                         AuditLog.action == action).count()
    finally:
        db.close()


@pytest.mark.parametrize("code,key", CASES)
def test_rename_follows_phase_ownership(client, phases, code, key):
    pid = phases[key]
    r = client.patch(f"/api/custom-training-phases/{pid}", json={"name": f"renamed {key}"},
                     headers=login(client, code))
    if key in ALLOWED[code]:
        assert r.status_code == 200, r.text
        assert r.json()["name"] == f"renamed {key}"
        assert _audit_rows(pid, "update") == 1
    else:
        assert r.status_code == 403, f"{code} renamed {key}: {r.status_code} {r.text}"
        assert _audit_rows(pid, "update") == 0
        db = SessionLocal()
        try:
            assert not db.get(CustomTrainingPhase, pid).name.startswith("renamed")
        finally:
            db.close()


@pytest.mark.parametrize("code,key", CASES)
def test_delete_follows_phase_ownership(client, phases, code, key):
    pid = phases[key]
    r = client.delete(f"/api/custom-training-phases/{pid}", headers=login(client, code))
    db = SessionLocal()
    try:
        deleted = db.get(CustomTrainingPhase, pid).is_deleted
    finally:
        db.close()
    if key in ALLOWED[code]:
        assert r.status_code == 200, r.text
        assert deleted
        assert _audit_rows(pid, "delete") == 1
    else:
        assert r.status_code == 403, f"{code} deleted {key}: {r.status_code} {r.text}"
        assert not deleted
        assert _audit_rows(pid, "delete") == 0
