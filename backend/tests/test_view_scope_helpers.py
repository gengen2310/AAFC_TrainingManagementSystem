"""One backend source of truth for "which Squadrons / Wing may this principal
view?" (permissions.py, view-scope section).

Each helper replaced inline derivations in several routers. These tests pin
the helper to the exact expression the routers used to build, over every
role, so a router routed through it selects exactly what it selected before.
The endpoint-level proof is tests/test_scope_parity.py.
"""
import pytest
from sqlalchemy import or_

from app import permissions as P
from app.database import SessionLocal
from app.models import AuditLog, Flight, Squadron, User, Wing

ROLES = sorted(P.ROLES)
NATIONAL = {"national_viewer", "national_admin", "system_admin", "auditor"}
WING = {"wing_viewer", "wing_admin"}


def _p(role, wing_id="w", squadron_id="s"):
    return P.Principal(user_id="u", role=role, wing_id=wing_id, squadron_id=squadron_id, national_id="n")


def _sql(clause) -> str | None:
    if clause is None:
        return None
    return str(clause.compile(compile_kwargs={"literal_binds": True}))


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def seven_wing(db):
    w = db.query(Wing).filter(Wing.code == "7WG").one()
    return w.id


# ── level_scope_clause: rows that carry their own wing and squadron columns ──

@pytest.mark.parametrize("role", ROLES + ["retired_role"])
def test_level_scope_clause_is_the_old_inline_filter(role):
    p = _p(role)
    got = _sql(P.level_scope_clause(p, wing_column=AuditLog.wing_id, squadron_column=AuditLog.squadron_id))
    if role in NATIONAL:
        assert got is None
    elif role in WING:
        assert got == _sql(AuditLog.wing_id == "w")
    else:  # Squadron level; an unrecognised role gets the narrowest scope
        assert got == _sql(AuditLog.squadron_id == "s")


@pytest.mark.parametrize("role", ROLES)
def test_level_scope_clause_on_squadrons_matches_can_view_squadron(db, role, seven_wing):
    """The SQL form and the per-row Principal.can_view_squadron agree."""
    s703 = db.query(Squadron).filter(Squadron.code == "703").one()
    p = _p(role, wing_id=seven_wing, squadron_id=s703.id)
    q = db.query(Squadron)
    clause = P.level_scope_clause(p, wing_column=Squadron.wing_id, squadron_column=Squadron.id)
    if clause is not None:
        q = q.filter(clause)
    assert {s.id for s in q} == {s.id for s in db.query(Squadron) if p.can_view_squadron(s.id, s.wing_id)}


# ── wing_scope_clause / wing_in_view: the Wing itself ──

@pytest.mark.parametrize("role", ROLES)
def test_wing_scope_clause_and_wing_in_view(role):
    p = _p(role)
    got = _sql(P.wing_scope_clause(p, Wing.id))
    if role in NATIONAL:
        assert got is None
        assert P.wing_in_view(p, "other")
    else:  # Wing AND Squadron accounts see their own Wing
        assert got == _sql(Wing.id == "w")
        assert P.wing_in_view(p, "w") and not P.wing_in_view(p, "other")


def test_wing_in_view_differs_from_can_view_wing_for_squadron_accounts():
    """Deliberately not unified: GET /api/wings lists a Squadron account's own
    Wing, while can_view_wing refuses Squadron accounts any Wing-level record."""
    p = _p("sqn_admin")
    assert P.wing_in_view(p, "w")
    assert not p.can_view_wing("w")


# ── visible_squadron_ids / squadron_scope_clause: rows scoped by Squadron only ──

@pytest.mark.parametrize("include_archived", [True, False])
def test_visible_squadron_ids_by_level(db, seven_wing, include_archived):
    q = db.query(Squadron).filter(Squadron.wing_id == seven_wing)
    if not include_archived:
        q = q.filter(Squadron.is_archived == False)  # noqa: E712
    wing_ids = [s.id for s in q.all()]
    for role in ROLES:
        p = _p(role, wing_id=seven_wing, squadron_id="s")
        got = P.visible_squadron_ids(p, db, include_archived=include_archived)
        if role in NATIONAL:
            assert got is None, role
        elif role in WING:
            assert got == wing_ids, role
        else:
            assert got == ["s"], role


def test_visible_squadron_ids_include_archived_squadrons_only_when_asked(db, seven_wing):
    sq = Squadron(wing_id=seven_wing, code="VSHARCH", name="Archived probe", short_name="VSH",
                  is_archived=True)
    db.add(sq)
    db.commit()
    try:
        p = _p("wing_viewer", wing_id=seven_wing)
        assert sq.id in P.visible_squadron_ids(p, db)
        assert sq.id not in P.visible_squadron_ids(p, db, include_archived=False)
    finally:
        db.delete(sq)
        db.commit()


@pytest.mark.parametrize("role", ROLES)
def test_squadron_scope_clause_is_the_old_inline_filter(db, seven_wing, role):
    p = _p(role, wing_id=seven_wing, squadron_id="s")
    got = _sql(P.squadron_scope_clause(p, db, Flight.squadron_id, include_archived=False))
    if role in NATIONAL:
        assert got is None
    elif role in WING:
        ids = [s.id for s in db.query(Squadron).filter(
            Squadron.wing_id == seven_wing, Squadron.is_archived == False).all()]  # noqa: E712
        assert got == _sql(Flight.squadron_id.in_(ids))
    else:
        assert got == _sql(Flight.squadron_id == "s")


# ── accounts: a user's own wing_id OR their Squadron's Wing ──

@pytest.mark.parametrize("role", ROLES)
def test_wing_or_squadron_scope_clause_is_the_old_accounts_filter(db, seven_wing, role):
    p = _p(role, wing_id=seven_wing, squadron_id="s")
    got = _sql(P.wing_or_squadron_scope_clause(p, db, wing_column=User.wing_id, squadron_column=User.squadron_id))
    if role in NATIONAL:
        assert got is None
    elif role in WING:
        ids = [s.id for s in db.query(Squadron).filter(Squadron.wing_id == seven_wing)]
        assert got == _sql(or_(User.wing_id == seven_wing, User.squadron_id.in_(ids)))
    else:
        assert got == _sql(User.squadron_id == "s")


def test_may_view_account_is_the_row_form_of_the_accounts_filter(db, seven_wing):
    s703 = db.query(Squadron).filter(Squadron.code == "703").one()
    users = db.query(User).filter(User.is_archived == False).all()  # noqa: E712
    for role in ROLES:
        p = _p(role, wing_id=seven_wing, squadron_id=s703.id)
        clause = P.wing_or_squadron_scope_clause(p, db, wing_column=User.wing_id, squadron_column=User.squadron_id)
        q = db.query(User).filter(User.is_archived == False)  # noqa: E712
        if clause is not None:
            q = q.filter(clause)
        assert {u.id for u in q} == {u.id for u in users if P.may_view_account(p, u, db)}, role
    assert not P.may_view_account(_p("retired_role"), users[0], db)


# ── resolve_view_squadron_id(..., out_of_scope_as_none=True): the dashboard form ──

def test_resolve_view_squadron_id_can_return_none_instead_of_403(db, seven_wing):
    from fastapi import HTTPException
    s703 = db.query(Squadron).filter(Squadron.code == "703").one()
    s704 = db.query(Squadron).filter(Squadron.code == "704").one()
    p = _p("sqn_general", wing_id=seven_wing, squadron_id=s703.id)
    assert P.resolve_view_squadron_id(p, s703.id, db, out_of_scope_as_none=True) == s703.id
    assert P.resolve_view_squadron_id(p, s704.id, db, out_of_scope_as_none=True) is None
    with pytest.raises(HTTPException) as e:
        P.resolve_view_squadron_id(p, s704.id, db)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        P.resolve_view_squadron_id(p, "missing", db, out_of_scope_as_none=True)
    assert e.value.status_code == 404
