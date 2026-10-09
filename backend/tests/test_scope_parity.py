"""Scope-boundary parity harness (C3/C4, 2026-10-09).

Router-local view-scope derivations ("which Squadrons / Wing may this
principal see?") and router-local role gates were moved into
``app/permissions.py``. This file is the proof that the move changed no
response, and keeps protecting the boundary afterwards.

Two layers:

1. ``test_scope_snapshot`` captures status code + canonical JSON body for every
   probe in ``_get_probes`` / ``_write_probes`` across every principal in
   ``PRINCIPALS`` (the eight seeded roles in 7WG, four accounts in a second
   Wing, a Wing Admin in Proxy Mode and a National Admin in Delegated
   Intervention). UUIDs are replaced by first-appearance placeholders and
   timestamps are scrubbed, so two runs over a fresh database are comparable.

   - ``SCOPE_PARITY_OUT=<file>`` writes the snapshot.
   - ``SCOPE_PARITY_IN=<file>`` compares against a stored snapshot and fails
     on any difference.

   Run it alone, in a fresh process, so the database is exactly the seed plus
   this file's world:

       SCOPE_PARITY_OUT=/tmp/before.json python -m pytest tests/test_scope_parity.py -q -p no:cacheprovider
       # ... change code ...
       SCOPE_PARITY_IN=/tmp/before.json  python -m pytest tests/test_scope_parity.py -q -p no:cacheprovider

   In the normal suite (neither variable set) it still executes every probe
   and asserts none of them returns a 5xx.

2. The ``test_oracle_*`` tests compare scoped list endpoints against an
   independent derivation written here from the database, so the boundary
   stays pinned without a stored snapshot.
"""
from __future__ import annotations

import json
import os
import re

import pytest

from app.database import SessionLocal
from app.models import (
    AccessCode, Activity, AuditLog, Facilitator, Flight, JobStatus, PlanningYear,
    ProxySession, ServiceDeskEmailConfig, ServiceTicket, Squadron, TrainingArea, User, Wing,
)
from app.models.custom_phases import CustomTrainingPhase
from app.security import hash_code
from tests.conftest import login

# A fixed tag keeps the world identical between the before and after runs.
TAG = "SPX"
# Snapshot mode runs alone over a fresh database, so it may also add 7WG-side
# rows and run the state-changing probes. In the shared suite database the
# world only adds a second Wing (plus two acting-scope accounts in 7WG) and
# never writes to seeded 7WG rows other tests rely on.
PARITY_MODE = bool(os.environ.get("SCOPE_PARITY_OUT") or os.environ.get("SCOPE_PARITY_IN"))
W2_CODE = f"{TAG}WG"

PRINCIPALS = {
    "sqn_general": "703SQN2026",
    "sqn_admin": "ADMIN703",
    "wing_viewer": "7WG2026",
    "wing_admin": "ADMIN7WG",
    "national_viewer": "NATIONAL2026",
    "national_admin": "ADMINNATIONAL",
    "system_admin": "SYSADMIN2026",
    "auditor": "AUDITOR2026",
    # second Wing
    "w2_wing_admin": f"{TAG}WADM2026",
    "w2_wing_viewer": f"{TAG}WVIEW2026",
    "w2_sqn_admin": f"{TAG}SADM2026",
    "w2_sqn_general": f"{TAG}SGEN2026",
    # acting scope
    "wing_admin_proxy": f"{TAG}WPROXY2026",
    "national_admin_di": f"{TAG}NDI2026",
}


def _user(db, code, **kw):
    u = User(**kw)
    db.add(u)
    db.flush()
    db.add(AccessCode(user_id=u.id, code_hash=hash_code(code)))
    return u


def _build_world() -> dict:
    """Second Wing + acting-scope principals + one row of each scoped resource
    on both sides of the Wing boundary. Idempotent within one test session."""
    db = SessionLocal()
    try:
        w7 = db.query(Wing).filter(Wing.code == "7WG").one()
        s703 = db.query(Squadron).filter(Squadron.code == "703").one()
        s704 = db.query(Squadron).filter(Squadron.code == "704").one()
        w2 = db.query(Wing).filter(Wing.code == W2_CODE).first()
        if w2 is None:
            w2 = Wing(national_id=w7.national_id, code=W2_CODE, name=f"{TAG} Parity Wing",
                      short_name=W2_CODE, timezone="Australia/Perth")
            db.add(w2)
            db.flush()
            s2a = Squadron(wing_id=w2.id, code=f"{TAG}1", unit_number=f"{TAG}1",
                           name=f"{TAG}1 Squadron", short_name=f"{TAG}1SQN")
            s2b = Squadron(wing_id=w2.id, code=f"{TAG}2", unit_number=f"{TAG}2",
                           name=f"{TAG}2 Squadron", short_name=f"{TAG}2SQN", is_archived=True)
            db.add_all([s2a, s2b])
            db.flush()
            nat = w7.national_id
            _user(db, PRINCIPALS["w2_wing_admin"], display_name=f"{TAG} Wing Admin",
                  role="wing_admin", wing_id=w2.id, national_id=nat)
            _user(db, PRINCIPALS["w2_wing_viewer"], display_name=f"{TAG} Wing Viewer",
                  role="wing_viewer", wing_id=w2.id, national_id=nat)
            w2_sadm = _user(db, PRINCIPALS["w2_sqn_admin"], display_name=f"{TAG} Sqn Admin",
                            role="sqn_admin", wing_id=w2.id, squadron_id=s2a.id)
            _user(db, PRINCIPALS["w2_sqn_general"], display_name=f"{TAG} Sqn General",
                  role="sqn_general", wing_id=w2.id, squadron_id=s2a.id)
            # A Squadron account with no wing_id of its own: the Wing-level
            # account lists disagree on whether a Wing sees it (see the report).
            _user(db, f"{TAG}ORPHAN2026", display_name=f"{TAG} Orphan General",
                  role="sqn_general", wing_id=None, squadron_id=s2a.id)
            # A user in the archived Squadron.
            _user(db, f"{TAG}ARCH2026", display_name=f"{TAG} Archived-Sqn General",
                  role="sqn_general", wing_id=w2.id, squadron_id=s2b.id)
            wa_proxy = _user(db, PRINCIPALS["wing_admin_proxy"], display_name=f"{TAG} 7WG Proxy Admin",
                             role="wing_admin", wing_id=w7.id, national_id=nat)
            na_di = _user(db, PRINCIPALS["national_admin_di"], display_name=f"{TAG} National DI Admin",
                          role="national_admin", national_id=nat)
            db.add_all([
                ProxySession(actor_user_id=wa_proxy.id, actor_role="wing_admin", mode="proxy",
                             acting_wing_id=w7.id, acting_squadron_id=s704.id,
                             reason="parity", active=True),
                ProxySession(actor_user_id=na_di.id, actor_role="national_admin",
                             mode="delegated_intervention", acting_wing_id=w2.id,
                             acting_squadron_id=s2a.id, reason="parity", active=True),
            ])
            if PARITY_MODE:
                _user(db, f"{TAG}MOVE2026", display_name=f"{TAG} 703 Mover",
                      role="sqn_general", wing_id=w7.id, squadron_id=s703.id)
            own_side = (s703, s2a, s2b) if PARITY_MODE else (s2a, s2b)
            for sq in own_side:
                db.add(Flight(squadron_id=sq.id, name=f"{TAG} Flight {sq.code}"))
                db.add(TrainingArea(squadron_id=sq.id, name=f"{TAG} Area {sq.code}"))
                db.add(Facilitator(squadron_id=sq.id, wing_id=sq.wing_id, first_name=TAG,
                                   last_name=f"Facil {sq.code}"))
                db.add(Activity(owning_level="squadron", wing_id=sq.wing_id, squadron_id=sq.id,
                                activity_name=f"{TAG} Activity {sq.code}", date_start="2026-11-01"))
            db.add(Activity(owning_level="wing", wing_id=w2.id, activity_name=f"{TAG} Wing Activity",
                            date_start="2026-11-02"))
            if PARITY_MODE:
                db.add(Activity(owning_level="wing", wing_id=w7.id, activity_name=f"{TAG} 7WG Wing Activity",
                                date_start="2026-11-03"))
            db.add_all([
                PlanningYear(unit_id=s2a.id, wing_id=w2.id, year=2026, name=f"{TAG} 2026"),
                PlanningYear(unit_id=None, wing_id=w2.id, year=2026, name=f"{TAG} Wing 2026"),
            ])
            ticket_rows = [(s2a.id, None, "w2 legacy"), (None, w2.id, "w2 wing"), (s2a.id, w2.id, "w2 sqn")]
            if PARITY_MODE:
                ticket_rows += [(s703.id, None, "703 legacy"), (s704.id, w7.id, "704")]
            for sq_id, wing_id, unit in ticket_rows:
                db.add(ServiceTicket(rank="CDT", first_name=TAG, last_name=unit, email="x@example.org",
                                     squadron_id=sq_id, wing_id=wing_id, unit_name=unit,
                                     description=f"{TAG} {unit}"))
            db.add(ServiceDeskEmailConfig(scope="wing", wing_id=w2.id, notification_email="w2@example.org"))
            db.add_all([
                CustomTrainingPhase(name=f"{TAG} W2 phase", scope_type="wing", scope_id=w2.id,
                                    applies_from="2026-01-01"),
                CustomTrainingPhase(name=f"{TAG} W2 sqn phase", scope_type="squadron", scope_id=s2a.id,
                                    applies_from="2026-01-01"),
            ])
            db.add(AuditLog(user_id=w2_sadm.id, role="sqn_admin", scope="squadron", wing_id=w2.id,
                            squadron_id=s2a.id, object_type="parity", action=f"{TAG}_w2"))
            if PARITY_MODE:
                db.add(ServiceDeskEmailConfig(scope="wing", wing_id=w7.id, notification_email="w7@example.org"))
                db.add_all([
                    CustomTrainingPhase(name=f"{TAG} 7WG phase", scope_type="wing", scope_id=w7.id,
                                        applies_from="2026-01-01"),
                    CustomTrainingPhase(name=f"{TAG} 703 sqn phase", scope_type="squadron", scope_id=s703.id,
                                        applies_from="2026-01-01"),
                ])
                db.add(AuditLog(user_id=None, role="sqn_admin", scope="squadron", wing_id=w7.id,
                                squadron_id=s703.id, object_type="parity", action=f"{TAG}_703"))
            for code in ("ADMIN703", f"{TAG}SADM2026", "ADMIN7WG"):
                owner = (db.query(User).join(AccessCode, AccessCode.user_id == User.id)
                         .filter(AccessCode.code_hash == hash_code(code)).first())
                db.add(JobStatus(job_type=f"{TAG}_{code}", requested_by=owner.id if owner else None,
                                 scope="squadron", status="succeeded"))
            db.commit()
        s2a = db.query(Squadron).filter(Squadron.code == f"{TAG}1").one()
        s2b = db.query(Squadron).filter(Squadron.code == f"{TAG}2").one()

        def uid(name):
            u = db.query(User).filter(User.display_name == name).first()
            return u.id if u else None

        jobs = {j.job_type: j.id for j in db.query(JobStatus).filter(JobStatus.job_type.like(f"{TAG}_%"))}
        years = {py.name: py.id for py in db.query(PlanningYear).filter(PlanningYear.name.like(f"{TAG}%"))}
        y703 = (db.query(PlanningYear).filter(PlanningYear.unit_id == s703.id)
                .order_by(PlanningYear.year).first())
        phases = {ph.name: ph.id for ph in db.query(CustomTrainingPhase)
                  .filter(CustomTrainingPhase.name.like(f"{TAG}%"))}
        tickets = {t.unit_name: t.id for t in db.query(ServiceTicket).filter(ServiceTicket.first_name == TAG)}
        return dict(
            w7=w7.id, w2=w2.id, s703=s703.id, s704=s704.id, s2a=s2a.id, s2b=s2b.id,
            u703_general=uid("703 General"), u703_admin=uid("703 Admin"),
            u704_general=uid("704 General"),
            uw2_general=uid(f"{TAG} Sqn General"), uw2_admin=uid(f"{TAG} Sqn Admin"),
            uw2_wing_viewer=uid(f"{TAG} Wing Viewer"), uw2_orphan=uid(f"{TAG} Orphan General"),
            uw2_arch=uid(f"{TAG} Archived-Sqn General"), u7_wing_admin=uid("7 Wing Admin"),
            u_nat_admin=uid("National Admin"),
            job_703=jobs["SPX_ADMIN703"], job_w2=jobs[f"{TAG}_{TAG}SADM2026"], job_7wg=jobs["SPX_ADMIN7WG"],
            year_w2=years[f"{TAG} 2026"], year_w2_wing=years[f"{TAG} Wing 2026"],
            year_703=y703.id if y703 else None,
            u703_mover=uid(f"{TAG} 703 Mover"),
            phase_w2=phases[f"{TAG} W2 phase"], phase_7wg=phases.get(f"{TAG} 7WG phase"),
            phase_w2_sqn=phases[f"{TAG} W2 sqn phase"], phase_703_sqn=phases.get(f"{TAG} 703 sqn phase"),
            ticket_w2=tickets["w2 sqn"], ticket_704=tickets.get("704"), ticket_w2_wing=tickets["w2 wing"],
        )
    finally:
        db.close()


def _get_probes(w: dict) -> list[str]:
    paths = [
        # accounts.py
        "/api/accounts", "/api/accounts?include_archived=true",
        f"/api/accounts?wing_id={w['w2']}", f"/api/accounts?squadron_id={w['s703']}",
        f"/api/accounts?squadron_id={w['s2a']}",
        f"/api/accounts/{w['u703_general']}", f"/api/accounts/{w['u704_general']}",
        f"/api/accounts/{w['uw2_general']}", f"/api/accounts/{w['uw2_wing_viewer']}",
        f"/api/accounts/{w['uw2_orphan']}", f"/api/accounts/{w['uw2_arch']}",
        f"/api/accounts/{w['u7_wing_admin']}",
        "/api/flights", "/api/flights?include_archived=true",
        f"/api/flights?squadron_id={w['s703']}", f"/api/flights?squadron_id={w['s2a']}",
        f"/api/flights?squadron_id={w['s2b']}",
        # organisations.py / system.py
        "/api/wings", "/api/wings?include_archived=true",
        "/api/squadrons", "/api/squadrons?include_archived=true", f"/api/squadrons?wing_id={w['w2']}",
        "/api/users", "/api/audit?object_type=parity", "/api/system/audit-summary?action=SPX_w2",
        "/api/system/audit-summary?action=SPX_703",
        # planning.py
        "/api/planning/years", f"/api/planning/years?wing_id={w['w2']}",
        "/api/planning/locations", f"/api/planning/locations?unit_id={w['s2a']}",
        "/api/planning/command-centre",
        f"/api/planning/years/{w['year_w2']}", f"/api/planning/years/{w['year_w2_wing']}",
        f"/api/planning/years/{w['year_w2']}/holidays",
        f"/api/planning/years/{w['year_w2']}/missions",
        # search.py
        "/api/search?q=SPX", "/api/search?q=70", "/api/search?q=Admin", "/api/search?q=Wing",
        "/api/search?q=Facil", "/api/search?q=Activity", "/api/search?q=General",
        # service_desk.py
        "/api/service-desk/tickets", "/api/service-desk/tickets?status=open",
        "/api/service-desk/email-config",
        # jobs.py
        f"/api/jobs/{w['job_703']}", f"/api/jobs/{w['job_w2']}", f"/api/jobs/{w['job_7wg']}",
        # setup.py
        "/api/setup/status", f"/api/setup/status?squadron_id={w['s703']}",
        f"/api/setup/status?squadron_id={w['s2a']}",
        # wing_calendar.py
        "/api/wing-calendar/events", f"/api/wing-calendar/events?wing_id={w['w2']}",
        f"/api/wing-calendar/events?wing_id={w['w7']}",
        # custom_phases.py
        "/api/custom-training-phases",
        # training.py
        "/api/curriculum/elements", "/api/curriculum/phases", "/api/activities/faq",
        "/api/subject-area-tags",
        # dashboard.py (_view_squadron_id_for_dashboard)
        f"/api/dashboard/charts?window=week&squadron_id={w['s703']}",
        f"/api/dashboard/charts?window=week&squadron_id={w['s2a']}",
        f"/api/dashboard/charts?window=week&wing_id={w['w2']}&squadron_id={w['s2a']}",
        f"/api/dashboard/charts?window=week&wing_id={w['w7']}&squadron_id={w['s2a']}",
        "/api/dashboard/charts?window=week&squadron_id=00000000-0000-0000-0000-000000000000",
    ]
    if w["year_703"]:
        paths += [f"/api/planning/years/{w['year_703']}", f"/api/planning/years/{w['year_703']}/holidays"]
    return paths


def _write_probes(w: dict) -> list[tuple[str, str, dict | None]]:
    """State-changing probes for the moved gates. Run after every GET, in a
    fixed order, so each run sees the same state."""
    return [
        ("POST", "/api/flights", {"name": "SPX probe own", "squadron_id": w["s703"]}),
        ("POST", "/api/flights", {"name": "SPX probe w2", "squadron_id": w["s2a"]}),
        # change-scope targets are never probe principals (a move revokes the
        # moved account's token).
        ("POST", f"/api/accounts/{w['u703_mover']}/change-scope", {"new_squadron_id": w["s704"]}),
        ("POST", f"/api/accounts/{w['uw2_orphan']}/change-scope", {"new_squadron_id": w["s703"]}),
        ("PATCH", f"/api/squadrons/{w['s703']}", {"unit_type": "standard_squadron"}),
        ("PATCH", f"/api/squadrons/{w['s703']}", {"unit_type": "specialist_squadron"}),
        ("PATCH", f"/api/squadrons/{w['s2a']}", {"unit_type": "support_unit"}),
        ("POST", "/api/custom-training-phases",
         {"name": "SPX probe wing", "scope_type": "wing", "scope_id": w["w2"], "applies_from": "2026-01-01"}),
        ("POST", "/api/custom-training-phases",
         {"name": "SPX probe national", "scope_type": "national", "applies_from": "2026-01-01"}),
        ("PATCH", f"/api/custom-training-phases/{w['phase_w2']}", {"name": "SPX W2 phase"}),
        ("PATCH", f"/api/custom-training-phases/{w['phase_7wg']}", {"name": "SPX 7WG phase"}),
        ("PATCH", f"/api/custom-training-phases/{w['phase_703_sqn']}", {"name": "SPX 703 sqn phase"}),
        ("PATCH", f"/api/custom-training-phases/{w['phase_w2_sqn']}", {"name": "SPX W2 sqn phase"}),
        ("PATCH", f"/api/service-desk/tickets/{w['ticket_704']}", {"assigned_to_user_id": w["u7_wing_admin"]}),
        ("PATCH", f"/api/service-desk/tickets/{w['ticket_w2']}", {"assigned_to_user_id": w["u7_wing_admin"]}),
        ("PATCH", f"/api/service-desk/tickets/{w['ticket_704']}", {"assigned_to_name": "7 Wing Admin"}),
        # A Wing Admin may assign only to a Wing Admin of their own Wing.
        ("PATCH", f"/api/service-desk/tickets/{w['ticket_704']}", {"assigned_to_user_id": w["u_nat_admin"]}),
        ("PUT", "/api/service-desk/email-config",
         {"scope": "wing", "wing_id": w["w7"], "notification_email": "w7@example.org"}),
        ("PUT", "/api/service-desk/email-config",
         {"scope": "wing", "wing_id": w["w2"], "notification_email": "w2@example.org"}),
        ("PUT", "/api/service-desk/email-config", {"scope": "national", "notification_email": "n@example.org"}),
        ("PUT", "/api/service-desk/email-config", {"scope": "system", "notification_email": "s@example.org"}),
        ("POST", "/api/curriculum/elements",
         {"name": "SPX_el", "display_name": "SPX el", "scope_level": "squadron", "squadron_id": w["s2a"]}),
        ("POST", "/api/curriculum/elements",
         {"name": "SPX_sys_el", "display_name": "SPX sys el", "scope_level": "system"}),
        ("POST", "/api/curriculum/phases",
         {"name": "SPX_ph", "display_name": "SPX ph", "scope_level": "squadron", "squadron_id": w["s2a"]}),
        ("POST", "/api/curriculum/phases",
         {"name": "SPX_ph2", "display_name": "SPX ph2", "scope_level": "squadron", "squadron_id": w["s704"]}),
        ("POST", "/api/curriculum/phases",
         {"name": "SPX_sys_ph", "display_name": "SPX sys ph", "scope_level": "system"}),
        ("POST", "/api/subject-area-tags",
         {"display_name": "SPX tag", "scope": "squadron", "squadron_id": w["s2a"]}),
        ("POST", "/api/subject-area-tags",
         {"display_name": "SPX tag2", "scope": "squadron", "squadron_id": w["s704"]}),
        # Proxy entry changes the caller's acting scope: last.
        ("POST", f"/api/proxy/enter/{w['s2a']}", {"reason": "parity"}),
        ("POST", f"/api/proxy/enter/{w['s703']}", {"reason": "parity"}),
    ]


_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_TS = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?")


class _Canon:
    def __init__(self):
        self.ids: dict[str, str] = {}

    def __call__(self, text: str) -> str:
        def sub(m):
            return self.ids.setdefault(m.group(0), f"<id{len(self.ids)}>")
        return _UUID.sub(sub, _TS.sub("<ts>", text))


def _body(r) -> object:
    try:
        return r.json()
    except ValueError:
        return {"_non_json_bytes": len(r.content)}


def _capture(client, world) -> dict[str, dict]:
    canon = _Canon()
    # Seed the placeholder map in a fixed order so placeholders do not depend
    # on which response mentions an id first.
    for key in sorted(world):
        if world[key]:
            canon(world[key])
    headers = {name: login(client, code) for name, code in PRINCIPALS.items()}
    out: dict[str, dict] = {}
    for path in _get_probes(world):
        for name in PRINCIPALS:
            r = client.get(path, headers=headers[name])
            out[f"GET {canon(path)} :: {name}"] = {
                "status": r.status_code,
                "body": canon(json.dumps(_body(r), sort_keys=True)),
            }
    for i, (method, path, body) in enumerate(_write_probes(world) if PARITY_MODE else []):
        for name in PRINCIPALS:
            r = client.request(method, path, json=body, headers=headers[name])
            out[f"{i:02d} {method} {canon(path)} {canon(json.dumps(body, sort_keys=True))} :: {name}"] = {
                "status": r.status_code,
                "body": canon(json.dumps(_body(r), sort_keys=True)),
            }
    return out


@pytest.fixture(scope="module")
def world():
    return _build_world()


def test_scope_snapshot(client, world):
    snap = _capture(client, world)
    writes = len(_write_probes(world)) if PARITY_MODE else 0
    assert len(snap) == len(PRINCIPALS) * (len(_get_probes(world)) + writes)
    server_errors = [k for k, v in snap.items() if v["status"] >= 500]
    assert not server_errors, server_errors

    out_path = os.environ.get("SCOPE_PARITY_OUT")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=1, sort_keys=True)
    in_path = os.environ.get("SCOPE_PARITY_IN")
    if in_path:
        with open(in_path, encoding="utf-8") as fh:
            before = json.load(fh)
        assert set(before) == set(snap), "probe set changed"
        diffs = [k for k in sorted(snap) if snap[k] != before[k]]
        assert not diffs, f"{len(diffs)} of {len(snap)} responses differ: {diffs[:20]}"


# ── Oracles: an independent derivation of each scoped list, from the database ──
#
# The level rule, written once here and nowhere near permissions.py:
# national-level roles (including auditor) see every Squadron, Wing-level roles
# the Squadrons of their own Wing, Squadron-level roles their own Squadron.

_NATIONAL = {"national_viewer", "national_admin", "system_admin", "auditor"}
_WING = {"wing_viewer", "wing_admin"}


def _me(client, hdr) -> dict:
    return client.get("/api/auth/me", headers=hdr).json()["session"]


def _oracle_sqn_ids(db, me, *, include_archived: bool) -> set[str]:
    q = db.query(Squadron)
    if not include_archived:
        q = q.filter(Squadron.is_archived == False)  # noqa: E712
    rows = q.all()
    if me["role"] in _NATIONAL:
        return {s.id for s in rows}
    if me["role"] in _WING:
        return {s.id for s in rows if s.wing_id == me["wing_id"]}
    return {s.id for s in rows if s.id == me["squadron_id"]}


@pytest.fixture
def principals(client, world):
    return {name: login(client, code) for name, code in PRINCIPALS.items()}


def test_oracle_squadron_list(client, principals):
    db = SessionLocal()
    try:
        for name, hdr in principals.items():
            me = _me(client, hdr)
            got = {s["squadron_id"] for s in client.get("/api/squadrons", headers=hdr).json()}
            assert got == _oracle_sqn_ids(db, me, include_archived=False), name
    finally:
        db.close()


def test_oracle_flights_follow_squadron_scope_including_archived_squadrons(client, principals):
    db = SessionLocal()
    try:
        for name, hdr in principals.items():
            me = _me(client, hdr)
            sqns = _oracle_sqn_ids(db, me, include_archived=True)
            expected = {f.id for f in db.query(Flight).filter(Flight.is_archived == False).all()  # noqa: E712
                        if f.squadron_id in sqns}
            got = {f["flight_id"] for f in client.get("/api/flights", headers=hdr).json()}
            assert got == expected, name
    finally:
        db.close()


def test_oracle_training_areas_exclude_archived_squadrons_for_wing(client, principals):
    db = SessionLocal()
    try:
        for name, hdr in principals.items():
            me = _me(client, hdr)
            if me["role"] in _NATIONAL:
                sqns = {s.id for s in db.query(Squadron).all()}
            else:
                sqns = _oracle_sqn_ids(db, me, include_archived=me["role"] not in _WING)
            expected = {a.id for a in db.query(TrainingArea).filter(
                TrainingArea.is_archived == False, TrainingArea.active_status == True).all()  # noqa: E712
                if a.squadron_id in sqns}
            got = {a["location_id"] for a in client.get("/api/planning/locations", headers=hdr).json()}
            assert got == expected, name
    finally:
        db.close()


def test_oracle_account_list(client, principals):
    """Wing accounts see users whose own wing_id is theirs OR whose Squadron is
    in their Wing (archived Squadrons included)."""
    db = SessionLocal()
    try:
        for name, hdr in principals.items():
            me = _me(client, hdr)
            users = db.query(User).filter(User.is_archived == False).all()  # noqa: E712
            if me["role"] in _NATIONAL:
                expected = {u.id for u in users}
            elif me["role"] in _WING:
                sqns = _oracle_sqn_ids(db, me, include_archived=True)
                expected = {u.id for u in users if u.wing_id == me["wing_id"] or u.squadron_id in sqns}
            else:
                expected = {u.id for u in users if u.squadron_id == me["squadron_id"]}
            got = {u["user_id"] for u in client.get("/api/accounts", headers=hdr).json()}
            assert got == expected, name
    finally:
        db.close()


def test_oracle_audit_rows_by_level(client, principals):
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.object_type == "parity").all()
        for name, hdr in principals.items():
            me = _me(client, hdr)
            r = client.get("/api/audit?object_type=parity", headers=hdr)
            if r.status_code == 403:
                assert me["role"] == "wing_viewer", name   # AUDIT_READ_ROLES omits wing_viewer
                continue
            if me["role"] in _NATIONAL:
                expected = {a.id for a in rows}
            elif me["role"] in _WING:
                expected = {a.id for a in rows if a.wing_id == me["wing_id"]}
            else:
                expected = {a.id for a in rows if a.squadron_id == me["squadron_id"]}
            assert {a["audit_id"] for a in r.json()} == expected, name
    finally:
        db.close()


def test_oracle_service_tickets(client, principals):
    db = SessionLocal()
    try:
        tickets = db.query(ServiceTicket).all()
        for name, hdr in principals.items():
            me = _me(client, hdr)
            r = client.get("/api/service-desk/tickets", headers=hdr)
            if me["role"] in ("auditor", "sqn_general"):
                assert r.status_code == 403, name
                continue
            if me["role"] in _NATIONAL:
                expected = {t.id for t in tickets}
            elif me["role"] in _WING:
                sqns = _oracle_sqn_ids(db, me, include_archived=True)
                expected = {t.id for t in tickets if t.wing_id == me["wing_id"] or t.squadron_id in sqns}
            else:
                expected = {t.id for t in tickets if t.squadron_id == me["squadron_id"]}
            assert {t["ticket_id"] for t in r.json()} == expected, name
    finally:
        db.close()


def test_oracle_search_never_crosses_the_wing_boundary(client, principals, world):
    db = SessionLocal()
    try:
        for name, hdr in principals.items():
            me = _me(client, hdr)
            res = client.get("/api/search?q=SPX", headers=hdr).json()["results"]
            facs = {r["meta"]["squadron_id"] for r in res if r["type"] == "facilitator"}
            if me["role"] == "auditor":
                assert not [r for r in res if r["type"] not in ("wing", "squadron")], name
                continue
            if me["role"] in _NATIONAL:
                continue
            visible = _oracle_sqn_ids(db, me, include_archived=True)
            assert facs <= visible, name
            if me["role"] in _WING and me["wing_id"] == world["w2"]:
                assert world["s2a"] in facs, name
    finally:
        db.close()
