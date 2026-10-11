"""Parity proof for the training.py / planning.py helper extraction (C5).

Every GET route on routers/training.py and routers/planning.py is requested as
eight seeded principals, and each response (status, content type, body) must
equal the snapshot in fixtures/training_planning_get_parity.json. That
snapshot was generated on the BASE commit 6ec3935, before any helper moved, so
a passing test means the extraction changed no GET response.

Deliberate snapshot changes since (each a reviewed defect fix, regenerated
with PARITY_REGEN=1 and diffed so only the named entries moved):
- D15 (2026-10-11): GET /planning/years/{year_id}/export.xlsx, all 8
  principals, 500 -> 200 xlsx (the export read AnchorEvent.name).

The harness runs in a SUBPROCESS against its own freshly seeded SQLite file.
The suite's shared DB is mutated by hundreds of other tests (and by test order),
so it cannot give a stable baseline; a fresh seed can, provided the three
sources of run-to-run variance are pinned. They are pinned rather than
normalised away, so the comparison stays byte-exact on everything else:

1. Random ids. uuid.uuid4 is replaced by a seeded generator before the app is
   imported, so every id the seed (and any GET that writes, e.g. an audit or
   login row) creates is the same on every run. Each request also sends a
   fixed X-Request-ID so the middleware never draws an id.
2. "Now". datetime.datetime / datetime.date are replaced, before anything else
   is imported, by subclasses whose now()/utcnow()/today() return the fixed
   instant FROZEN_AT, so seeded created_at values, "upcoming"/"overdue" windows
   and JWT iat/exp are the same on every day the test runs. isinstance against
   either class still accepts real date/datetime objects.
3. xlsx bodies. A zip records each member's write time from time.localtime(),
   which the clock above does not cover; an .xlsx body is therefore recorded as
   the sha256 of each member's decompressed content (names sorted), not of the
   zip bytes. This is the only normalisation of a response body.

The snapshot stores, per (principal, route), the status, content type and the
sha256 + length of the canonical body (JSON re-serialised with sorted keys; any
other body as text), which keeps the fixture small. To see WHAT changed after a
failure, set PARITY_FULL_DUMP=/tmp/x.json on this commit and on the base commit
and diff the two files.

Response headers are not compared. Routes or principals that answer 4xx are
still recorded -- the error contract is part of the parity.

Regenerate (only on a commit whose behaviour is the intended baseline):
    PARITY_REGEN=1 python -m pytest tests/test_training_planning_extraction_parity.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parent
SNAPSHOT = HERE / "fixtures" / "training_planning_get_parity.json"

FROZEN_AT = (2026, 10, 11, 9, 30, 0)  # UTC; the day the baseline was captured
PRINCIPALS = ["ADMIN703", "703SQN2026", "ADMIN7WG", "7WG2026",
              "ADMINNATIONAL", "NATIONAL2026", "AUDITOR2026", "SYSADMIN2026"]


# --------------------------------------------------------------------------
# Subprocess side
# --------------------------------------------------------------------------

def _install_frozen_clock():
    import datetime as _dt

    real_date, real_datetime = _dt.date, _dt.datetime
    frozen = real_datetime(*FROZEN_AT, tzinfo=_dt.timezone.utc)

    class _DateMeta(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, real_date)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, real_date)

    class _DatetimeMeta(_DateMeta):
        def __instancecheck__(cls, obj):
            return isinstance(obj, real_datetime)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, real_datetime)

    class FrozenDate(real_date, metaclass=_DateMeta):
        @classmethod
        def today(cls):
            return frozen.date()

    class FrozenDatetime(real_datetime, metaclass=_DatetimeMeta):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen.replace(tzinfo=None)
            return frozen.astimezone(tz)

        @classmethod
        def utcnow(cls):
            return frozen.replace(tzinfo=None)

        @classmethod
        def today(cls):
            return frozen.replace(tzinfo=None)

    _dt.date = FrozenDate
    _dt.datetime = FrozenDatetime
    return FrozenDatetime


def _install_seeded_uuid():
    import random
    import uuid as _uuid

    rng = random.Random(20261011)

    def uuid4():
        return _uuid.UUID(int=rng.getrandbits(128), version=4)

    _uuid.uuid4 = uuid4


def _body(resp):
    import hashlib
    import io
    import zipfile

    ctype = resp.headers.get("content-type", "")
    if "json" in ctype:
        return resp.json()
    if "spreadsheetml" in ctype or resp.content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            return {"xlsx_members": {n: hashlib.sha256(z.read(n)).hexdigest()
                                     for n in sorted(z.namelist())}}
    return resp.text


def _ids(db):
    import sqlalchemy as sa

    one = lambda q, **kw: db.execute(sa.text(q), kw).scalar()  # noqa: E731
    sq = one("SELECT id FROM squadrons WHERE code='703'")
    ids = {"sq": sq}
    ids["year"] = one("SELECT id FROM planning_years WHERE unit_id=:s AND year=2026", s=sq)
    ids["pn"] = one("SELECT pn.id FROM parade_nights pn WHERE pn.squadron_id=:s AND pn.is_archived=0 "
                    "AND EXISTS (SELECT 1 FROM sessions x WHERE x.parade_night_id=pn.id AND x.is_archived=0) "
                    "ORDER BY pn.date, pn.id LIMIT 1", s=sq)
    ids["pn_date"] = one("SELECT date FROM parade_nights WHERE id=:i", i=ids["pn"])
    ids["session"] = one("SELECT id FROM sessions WHERE parade_night_id=:p AND is_archived=0 "
                         "ORDER BY period_number, id LIMIT 1", p=ids["pn"])
    ids["period"] = one("SELECT period_number FROM sessions WHERE id=:i", i=ids["session"])
    ids["citem"] = one("SELECT curriculum_item_id FROM sessions WHERE id=:i", i=ids["session"]) or \
        one("SELECT id FROM curriculum_items ORDER BY code, id LIMIT 1")
    ids["class"] = one("SELECT id FROM training_classes WHERE squadron_id=:s AND is_archived=0 "
                       "ORDER BY display_name, id LIMIT 1", s=sq)
    ids["cadet"] = one("SELECT id FROM cadets WHERE squadron_id=:s ORDER BY last_name, first_name, id LIMIT 1", s=sq)
    ids["fac"] = one("SELECT id FROM facilitators WHERE squadron_id=:s ORDER BY last_name, first_name, id LIMIT 1",
                     s=sq)
    ids["anchor"] = one("SELECT id FROM anchor_events WHERE planning_year_id=:y ORDER BY start_date, event_name, id "
                        "LIMIT 1", y=ids["year"])
    ids["activity"] = one("SELECT id FROM activities ORDER BY date_start, activity_name, id LIMIT 1")
    ids["stage"] = one("SELECT id FROM curriculum_phases ORDER BY sort_order, name, id LIMIT 1")
    ids["pnt"] = one("SELECT id FROM parade_night_templates ORDER BY name, id LIMIT 1")
    ids["timing"] = one("SELECT id FROM timing_templates WHERE squadron_id=:s ORDER BY name, id LIMIT 1", s=sq)
    return ids


def _routes(i):
    """(label, url). One entry per GET route, in router declaration order. The
    ids are the first seeded 703 SQN rows; None when the seed has no such row."""
    t, pl = "/api", "/api/planning"
    return [
        # routers/training.py
        ("GET /curriculum", f"{t}/curriculum"),
        ("GET /curriculum/learning-hub/validation", f"{t}/curriculum/learning-hub/validation"),
        ("GET /curriculum/export.xlsx", f"{t}/curriculum/export.xlsx"),
        ("GET /curriculum/{cid}/sessions", f"{t}/curriculum/{i['citem']}/sessions"),
        ("GET /parade-nights", f"{t}/parade-nights?squadron_id={i['sq']}"),
        ("GET /parade-nights/{pnid}", f"{t}/parade-nights/{i['pn']}"),
        ("GET /parade-nights/{night_id}/template-impact",
         f"{t}/parade-nights/{i['pn']}/template-impact?new_template_id={i['timing']}"),
        ("GET /parade-nights/{pnid}/notices", f"{t}/parade-nights/{i['pn']}/notices"),
        ("GET /training/sessions/{session_id}", f"{t}/training/sessions/{i['session']}"),
        ("GET /sessions/{sid}/status-history", f"{t}/sessions/{i['session']}/status-history"),
        ("GET /facilitators/ranks", f"{t}/facilitators/ranks"),
        ("GET /facilitators", f"{t}/facilitators?squadron_id={i['sq']}"),
        ("GET /facilitators/import/template.csv", f"{t}/facilitators/import/template.csv"),
        ("GET /facilitators/{fid}/stats", f"{t}/facilitators/{i['fac']}/stats"),
        ("GET /training-areas", f"{t}/training-areas?squadron_id={i['sq']}"),
        ("GET /equipment", f"{t}/equipment?squadron_id={i['sq']}"),
        ("GET /resources/clashes", f"{t}/resources/clashes?date={i['pn_date']}"),
        ("GET /cadets", f"{t}/cadets"),
        ("GET /cadets/risk", f"{t}/cadets/risk"),
        ("GET /cadets/{cadet_id}/class-memberships", f"{t}/cadets/{i['cadet']}/class-memberships"),
        ("GET /training-classes/{cid}/members", f"{t}/training-classes/{i['class']}/members"),
        ("GET /parade-nights/{pnid}/builder", f"{t}/parade-nights/{i['pn']}/builder"),
        ("GET /parade-nights/{pnid}/planner", f"{t}/parade-nights/{i['pn']}/planner"),
        ("GET /training-classes", f"{t}/training-classes?squadron_id={i['sq']}"),
        ("GET /training-classes/{cid}/curriculum-progress", f"{t}/training-classes/{i['class']}/curriculum-progress"),
        ("GET /curriculum/class-matrix", f"{t}/curriculum/class-matrix?year_id={i['year']}"),
        ("GET /curriculum/phases/{stage_id}/class-progress",
         f"{t}/curriculum/phases/{i['stage']}/class-progress?squadron_id={i['sq']}"),
        ("GET /sessions/{sid}/facilitator-suggestions",
         f"{t}/sessions/{i['session']}/facilitator-suggestions?parade_date={i['pn_date']}&period={i['period']}"),
        ("GET /sessions/{sid}/audience", f"{t}/sessions/{i['session']}/audience"),
        ("GET /activities/getting-help", f"{t}/activities/getting-help"),
        ("GET /activities/faq", f"{t}/activities/faq"),
        ("GET /activities", f"{t}/activities?squadron_id={i['sq']}"),
        ("GET /activities/{aid}", f"{t}/activities/{i['activity']}"),
        ("GET /curriculum/elements", f"{t}/curriculum/elements"),
        ("GET /curriculum/phases", f"{t}/curriculum/phases"),
        ("GET /subject-area-tags", f"{t}/subject-area-tags"),
        ("GET /facilitator-type-tags", f"{t}/facilitator-type-tags"),
        ("GET /session-status-reason-tags", f"{t}/session-status-reason-tags"),
        ("GET /activity-type-tags", f"{t}/activity-type-tags"),
        ("GET /training-area-capability-tags", f"{t}/training-area-capability-tags"),
        ("GET /parade-night-templates", f"{t}/parade-night-templates"),
        ("GET /parade-night-templates/{tid}", f"{t}/parade-night-templates/{i['pnt']}"),
        ("GET /sessions/needs-attention", f"{t}/sessions/needs-attention?squadron_id={i['sq']}"),
        ("GET /sessions/{session_id}/history", f"{t}/sessions/{i['session']}/history"),
        ("GET /curriculum-items/{item_id}/previous-deliveries",
         f"{t}/curriculum-items/{i['citem']}/previous-deliveries?squadron_id={i['sq']}"),
        ("GET /training-classes/{class_id}/roster", f"{t}/training-classes/{i['class']}/roster"),
        ("GET /training-records", f"{t}/training-records?class_id={i['class']}&squadron_id={i['sq']}"),
        ("GET /training-records/export", f"{t}/training-records/export?class_id={i['class']}"),
        ("GET /cadets/{cadet_id}/training-record", f"{t}/cadets/{i['cadet']}/training-record"),
        # routers/planning.py
        ("GET /planning/years", f"{pl}/years"),
        ("GET /planning/year-context", f"{pl}/year-context?squadron_id={i['sq']}&year=2026"),
        ("GET /planning/years/{year_id}", f"{pl}/years/{i['year']}"),
        ("GET /planning/years/{year_id}/parade-dates", f"{pl}/years/{i['year']}/parade-dates"),
        ("GET /planning/years/{year_id}/holidays", f"{pl}/years/{i['year']}/holidays"),
        ("GET /planning/years/{year_id}/anchors", f"{pl}/years/{i['year']}/anchors"),
        ("GET /planning/anchors/{anchor_id}/prep-suggestions", f"{pl}/anchors/{i['anchor']}/prep-suggestions"),
        ("GET /planning/years/{year_id}/term-planner", f"{pl}/years/{i['year']}/term-planner"),
        ("GET /planning/parade-dates/{date_id}/builder", f"{pl}/parade-dates/{i['pn']}/builder"),
        ("GET /planning/sessions/{session_id}", f"{pl}/sessions/{i['session']}"),
        ("GET /planning/parade-dates/{date_id}/archived-sessions", f"{pl}/parade-dates/{i['pn']}/archived-sessions"),
        ("GET /planning/parade-dates/{date_id}/weekly-program", f"{pl}/parade-dates/{i['pn']}/weekly-program"),
        ("GET /planning/years/{year_id}/long-range", f"{pl}/years/{i['year']}/long-range"),
        ("GET /planning/locations", f"{pl}/locations"),
        ("GET /planning/facilitators", f"{pl}/facilitators"),
        ("GET /planning/years/{year_id}/conflicts", f"{pl}/years/{i['year']}/conflicts"),
        ("GET /planning/years/{year_id}/plan-review", f"{pl}/years/{i['year']}/plan-review"),
        ("GET /planning/years/{year_id}/decision-guide", f"{pl}/years/{i['year']}/decision-guide"),
        ("GET /planning/command-centre", f"{pl}/command-centre?year_id={i['year']}"),
        ("GET /planning/class-forecasts", f"{pl}/class-forecasts?year_id={i['year']}"),
        ("GET /planning/prep-rules", f"{pl}/prep-rules"),
        ("GET /planning/years/{year_id}/missions", f"{pl}/years/{i['year']}/missions"),
        ("GET /planning/years/{year_id}/annual-program", f"{pl}/years/{i['year']}/annual-program"),
        ("GET /planning/years/{year_id}/export.xlsx", f"{pl}/years/{i['year']}/export.xlsx"),
        ("GET /planning/years/{year_id}/export", f"{pl}/years/{i['year']}/export"),
        ("GET /planning/years/{year_id}/schedule/export.xlsx", f"{pl}/years/{i['year']}/schedule/export.xlsx"),
        ("GET /planning/facilitators/{fac_id}/leave", f"{pl}/facilitators/{i['fac']}/leave"),
        ("GET /planning/years/{year_id}/facilitators/{fac_id}/workload",
         f"{pl}/years/{i['year']}/facilitators/{i['fac']}/workload"),
        ("GET /planning/years/{year_id}/night-summaries", f"{pl}/years/{i['year']}/night-summaries"),
        ("GET /planning/parade-nights/{night_id}/notices", f"{pl}/parade-nights/{i['pn']}/notices"),
        ("GET /planning/parade-dates/{night_id}/notices", f"{pl}/parade-dates/{i['pn']}/notices"),
        ("GET /planning/years/{year_id}/cea/activities", f"{pl}/years/{i['year']}/cea/activities"),
        ("GET /planning/years/{year_id}/cea/batches", f"{pl}/years/{i['year']}/cea/batches"),
    ]


def _dump(out_path: str) -> None:
    import hashlib

    tmp = tempfile.mkdtemp()
    os.environ.update({"DATABASE_URL": f"sqlite:///{tmp}/parity.db", "ENVIRONMENT": "test",
                       "JWT_SECRET": "test-secret", "SECRET_KEY": "test-secret", "API_RATE_LIMIT": "100000"})
    # Third-party libraries are imported BEFORE the clock is swapped, so their
    # own date/datetime subclasses (pydantic.v1's ConstrainedDate, ...) keep the
    # real base classes; only app code, imported afterwards, sees the frozen
    # ones. PyJWT checks exp with its module-level datetime, so it is pointed at
    # the frozen clock explicitly (tokens are minted by app code with it).
    import fastapi, fastapi.testclient, pydantic, pydantic.v1, sqlalchemy, jwt.api_jwt  # noqa: E401,F401
    import openpyxl, passlib.context  # noqa: E401,F401
    jwt.api_jwt.datetime = _install_frozen_clock()
    _install_seeded_uuid()
    sys.path.insert(0, str(BACKEND))

    import uuid
    import sqlalchemy as sa
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import SessionLocal
    from app.seeds.seed_all import seed_all

    seed_all()
    db = SessionLocal()
    try:  # same v64 SAF backfill conftest._seed applies to the suite's DB
        for sid, uid in db.execute(sa.text(
                "SELECT id, assistant_facilitator_id FROM sessions "
                "WHERE assistant_facilitator_id IS NOT NULL AND is_archived = 0 ORDER BY id")).fetchall():
            db.execute(sa.text("INSERT OR IGNORE INTO session_assistant_facilitators "
                               "(id, session_id, user_id, created_at) VALUES (:id, :sid, :uid, CURRENT_TIMESTAMP)"),
                       {"id": str(uuid.uuid4()), "sid": sid, "uid": uid})
        db.commit()
        ids = _ids(db)
    finally:
        db.close()

    # A route that raises is recorded as its 500 (the error contract is part of
    # the parity) instead of aborting the harness.
    client = TestClient(app, raise_server_exceptions=False)

    # The seed has no Activity and no ParadeNightTemplate, so /activities/{aid}
    # and /parade-night-templates/{tid} would only ever 404. Create one of each
    # through the public API (as ADMIN703) so those routes are exercised too.
    r = client.post("/api/auth/login", json={"code": "ADMIN703"}, headers={"X-Request-ID": "parity"})
    h = {"Authorization": f"Bearer {r.json()['token']}", "X-Request-ID": "parity"}
    made = [client.post("/api/activities", headers=h, json={
                "activity_name": "Parity activity", "date_start": str(ids["pn_date"]), "location": "Bravo"}),
            client.post(f"/api/parade-nights/{ids['pn']}/save-as-template", headers=h,
                        json={"name": "Parity template", "description": "C5 parity fixture"})]
    assert all(m.status_code == 200 for m in made), [m.text for m in made]
    db = SessionLocal()
    try:
        ids = _ids(db)
    finally:
        db.close()

    full_path = os.environ.get("PARITY_FULL_DUMP")
    full = {} if full_path else None
    out = {"ids_resolved": {k: v is not None for k, v in ids.items()}, "responses": {}}
    n = 0
    for code in PRINCIPALS:
        r = client.post("/api/auth/login", json={"code": code}, headers={"X-Request-ID": "parity"})
        assert r.status_code == 200, (code, r.text)
        headers = {"Authorization": f"Bearer {r.json()['token']}", "X-Request-ID": "parity"}
        for label, url in _routes(ids):
            n += 1
            resp = client.get(url, headers=headers)
            body = json.dumps(_body(resp), sort_keys=True, separators=(",", ":"), default=str)
            out["responses"][f"{code} {label}"] = {
                "status": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "body_len": len(body),
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }
            if full is not None:
                full[f"{code} {label}"] = json.loads(body)
    pathlib.Path(out_path).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    if full is not None:  # PARITY_FULL_DUMP=<path>: the bodies themselves, for diffing a failure
        pathlib.Path(full_path).write_text(json.dumps(full, indent=1, sort_keys=True) + "\n")


# --------------------------------------------------------------------------
# pytest side
# --------------------------------------------------------------------------

def _run_harness() -> dict:
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out.json")
        env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL",)}
        proc = subprocess.run([sys.executable, str(pathlib.Path(__file__)), "--dump", out],
                              cwd=str(BACKEND), env=env, capture_output=True, text=True, timeout=900)
        assert proc.returncode == 0, proc.stderr[-4000:]
        return json.loads(pathlib.Path(out).read_text())


def test_every_get_response_matches_the_base_snapshot():
    current = _run_harness()
    if os.environ.get("PARITY_REGEN") == "1":
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
    expected = json.loads(SNAPSHOT.read_text())
    assert current["ids_resolved"] == expected["ids_resolved"]
    assert sorted(current["responses"]) == sorted(expected["responses"])
    diffs = [k for k in sorted(expected["responses"]) if current["responses"][k] != expected["responses"][k]]
    assert not diffs, f"{len(diffs)} GET responses changed, e.g. {diffs[:10]}"


def test_snapshot_covers_every_get_route_on_both_routers():
    """A GET route added to either router must be added to the harness too."""
    import ast
    declared = []
    for name in ("training", "planning"):
        tree = ast.parse((BACKEND / "app" / "routers" / f"{name}.py").read_text())
        for node in tree.body:
            for dec in getattr(node, "decorator_list", []):
                if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "get" and isinstance(dec.args[0], ast.Constant)):
                    declared.append(("/planning" if name == "planning" else "") + dec.args[0].value)
    expected = json.loads(SNAPSHOT.read_text())
    labels = {k.split(" ", 1)[1] for k in expected["responses"]}
    assert {f"GET {p}" for p in declared} == labels


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--dump":
    _dump(sys.argv[2])
