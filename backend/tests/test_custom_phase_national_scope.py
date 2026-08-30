"""National isolation for custom training phases.

CustomTrainingPhase carries a polymorphic scope pair: scope_type in
{squadron, wing, national, system} and scope_id holding that scope entity's id.
For squadron and wing scope the router populated scope_id correctly. For
national scope it forced scope_id to None, so _visible_phases could only match
on scope_type -- and every national role saw every national's phases.

"system" is deliberately different: it means installation-wide, above any one
national, so it keeps scope_id NULL and stays visible to everyone.

A national-scoped row whose scope_id is NULL is a pre-v61 row. It stays visible
to all nationals, because that is exactly what it did before and there is no
way to tell from the row itself which national created it.
"""
import pytest
from conftest import login

SECOND_NATIONAL_CODE = "ADMINNATB"


@pytest.fixture()
def second_national(client):
    """A second NationalEntity with its own national_admin.

    The installation seeds one national and exposes no route to create
    another, so the cross-national case can only be built directly.
    """
    from app.database import SessionLocal
    from app.models import NationalEntity, User, AccessCode
    from app.security import hash_code

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.display_name == "B National Admin").first()
        if existing:
            return existing.national_id
        nat_b = NationalEntity(name="National B", short_name="NATB")
        db.add(nat_b)
        db.commit()
        adm = User(display_name="B National Admin", role="national_admin",
                   national_id=nat_b.id)
        db.add(adm)
        db.commit()
        db.add(AccessCode(user_id=adm.id, code_hash=hash_code(SECOND_NATIONAL_CODE)))
        db.commit()
        return nat_b.id
    finally:
        db.close()


def _create_phase(client, headers, name, scope_type, **extra):
    body = {"name": name, "scope_type": scope_type, "applies_from": "2026-01-01"}
    body.update(extra)
    r = client.post("/api/custom-training-phases", headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _phase_ids(client, headers):
    r = client.get("/api/custom-training-phases", headers=headers)
    assert r.status_code == 200, r.text
    return [p["custom_phase_id"] for p in r.json()]


# ── the leak ──────────────────────────────────────────────────────────────────

def test_national_phase_records_its_national(client):
    """scope_id must name the national entity, not be discarded."""
    h = login(client, "ADMINNATIONAL")
    phase = _create_phase(client, h, "Records Its National", "national")
    assert phase["scope_id"], "national-scoped phase left scope_id empty"


def test_national_admin_cannot_see_another_nationals_phase(client, second_national):
    hA = login(client, "ADMINNATIONAL")
    phase = _create_phase(client, hA, "National A Only", "national")

    hB = login(client, SECOND_NATIONAL_CODE)
    assert phase["custom_phase_id"] not in _phase_ids(client, hB), (
        "national B sees national A's national-scoped phase"
    )


def test_squadron_user_cannot_see_another_nationals_phase(client, second_national):
    """Inheritance must stop at the national boundary, not flow to every unit."""
    hB = login(client, SECOND_NATIONAL_CODE)
    phase = _create_phase(client, hB, "National B Only", "national")

    h703 = login(client, "ADMIN703")   # squadron in national A
    assert phase["custom_phase_id"] not in _phase_ids(client, h703), (
        "a squadron in national A sees national B's phase"
    )


def test_national_admin_still_sees_own_national_phase(client, second_national):
    """The fix must not over-filter: your own national's phase stays visible."""
    hA = login(client, "ADMINNATIONAL")
    phase = _create_phase(client, hA, "National A Visible To A", "national")
    assert phase["custom_phase_id"] in _phase_ids(client, hA)


def test_squadron_still_sees_own_nationals_phase(client):
    """Downward inheritance within one national must keep working."""
    hA = login(client, "ADMINNATIONAL")
    phase = _create_phase(client, hA, "National A Inherited Down", "national")
    h703 = login(client, "ADMIN703")
    assert phase["custom_phase_id"] in _phase_ids(client, h703)


# ── system scope is deliberately above national ───────────────────────────────

def test_system_phase_is_visible_to_every_national(client, second_national):
    """"system" means installation-wide and keeps scope_id NULL."""
    hsys = login(client, "SYSADMIN2026")
    phase = _create_phase(client, hsys, "Installation Wide", "system")
    assert phase["scope_id"] is None, "system scope must not be pinned to a national"

    hB = login(client, SECOND_NATIONAL_CODE)
    assert phase["custom_phase_id"] in _phase_ids(client, hB)
    h703 = login(client, "ADMIN703")
    assert phase["custom_phase_id"] in _phase_ids(client, h703)


# ── mutation guards ───────────────────────────────────────────────────────────

def test_national_admin_cannot_edit_another_nationals_phase(client, second_national):
    hA = login(client, "ADMINNATIONAL")
    phase = _create_phase(client, hA, "A Owns This", "national")

    hB = login(client, SECOND_NATIONAL_CODE)
    r = client.patch(f"/api/custom-training-phases/{phase['custom_phase_id']}",
                     headers=hB, json={"name": "B Renamed It"})
    assert r.status_code in (403, 404), (
        f"national B edited national A's phase: {r.status_code} {r.text}"
    )


def test_national_admin_cannot_delete_another_nationals_phase(client, second_national):
    hA = login(client, "ADMINNATIONAL")
    phase = _create_phase(client, hA, "A Owns This Too", "national")

    hB = login(client, SECOND_NATIONAL_CODE)
    r = client.delete(f"/api/custom-training-phases/{phase['custom_phase_id']}",
                      headers=hB)
    assert r.status_code in (403, 404), (
        f"national B deleted national A's phase: {r.status_code} {r.text}"
    )


# ── legacy rows ───────────────────────────────────────────────────────────────

def test_pre_v61_national_row_stays_visible_to_all(client, second_national):
    """A national row with no scope_id predates the fix and stays visible.

    Narrowing it would hide phases squadrons are scheduling against today.
    """
    from app.database import SessionLocal
    from app.models.custom_phases import CustomTrainingPhase

    db = SessionLocal()
    try:
        legacy = CustomTrainingPhase(
            name="Legacy National Phase", scope_type="national", scope_id=None,
            applies_from="2026-01-01", is_deleted=False,
        )
        db.add(legacy)
        db.commit()
        legacy_id = legacy.id
    finally:
        db.close()

    for code in ("ADMINNATIONAL", SECOND_NATIONAL_CODE, "ADMIN703"):
        assert legacy_id in _phase_ids(client, login(client, code)), (
            f"{code} lost sight of a pre-v61 national phase"
        )
