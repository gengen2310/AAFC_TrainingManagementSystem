"""Query count of session serialisation must not grow with the number of sessions.

_real_session_out() issued per-session queries (training area, assistant
facilitator, assistant join rows and each assistant's facilitator, curriculum
fallback, audience count, custom-phase audiences). The term planner calls it
for every session in a year, so its query count grew linearly with the year's
size. Measured with SQL statement counting rather than wall-clock time, which
is deterministic.
"""
from contextlib import contextmanager

from sqlalchemy import event

from app.database import engine
from tests.conftest import login, next_test_year


@contextmanager
def count_queries():
    n = {"q": 0}

    def _count(*_a, **_k):
        n["q"] += 1
    event.listen(engine, "before_cursor_execute", _count)
    try:
        yield n
    finally:
        event.remove(engine, "before_cursor_execute", _count)


def _facs(client, h, k):
    out = []
    for i in range(k):
        r = client.post("/api/facilitators", headers=h, json={"first_name": f"Qc{i}", "last_name": f"Count{next_test_year()}",
                                                               "confirm_duplicate": True})
        out.append(r.json()["facilitator_id"])
    return out


def _refs(client, h):
    """A room and a curriculum item, so the room and curriculum-tier paths run."""
    rooms = client.get("/api/training-areas", headers=h).json()
    rooms = rooms if isinstance(rooms, list) else rooms.get("training_areas", rooms.get("items", []))
    room = (rooms[0].get("training_area_id") or rooms[0].get("id")) if rooms else None
    cur = client.get("/api/curriculum", headers=h).json()["items"]
    return room, (cur[0]["curriculum_id"] if cur else None)


def _year_with_sessions(client, h, nights, per_night, facs):
    room, ci = _refs(client, h)
    year = next_test_year()
    y = client.post("/api/planning/years", json={"year": year, "name": f"{year} QC"}, headers=h).json()["planning_year_id"]
    for d in range(nights):
        pn = client.post(f"/api/planning/years/{y}/parade-dates", headers=h,
                         json={"parade_date": f"{year}-03-{d + 2:02d}"}).json()["parade_night_id"]
        for period in range(1, per_night + 1):
            r = client.post("/api/sessions", headers=h, json={
                "parade_night_id": pn, "period_number": period, "custom_title": f"S{d}-{period}",
                "facilitator_id": facs[0], "assistant_facilitator_ids": facs[1:3], "override_conflict": True,
                # Alternate the room/curriculum so both the "set" and "unset" paths are serialised.
                "training_area_id": room if period % 2 else None,
                "curriculum_item_id": ci if d % 2 else None})
            assert r.status_code == 200, r.text
    return y


def test_term_planner_query_count_does_not_scale_with_sessions(client):
    h = login(client, "ADMIN703")
    facs = _facs(client, h, 3)
    small = _year_with_sessions(client, h, nights=2, per_night=2, facs=facs)    # 4 sessions
    large = _year_with_sessions(client, h, nights=6, per_night=2, facs=facs)    # 12 sessions
    counts = {}
    for name, y in (("small", small), ("large", large)):
        client.get(f"/api/planning/years/{y}/term-planner", headers=h)        # warm caches
        with count_queries() as n:
            r = client.get(f"/api/planning/years/{y}/term-planner", headers=h)
        assert r.status_code == 200, r.text
        counts[name] = n["q"]
    print("TERM_PLANNER_QUERIES", counts)
    # 3x the sessions and 3x the nights: allow a small constant slack, not growth.
    assert counts["large"] <= counts["small"] + 4, counts


def test_batched_context_serialises_every_session_identically(client):
    """The batched path must produce exactly the per-session path's output."""
    from app.database import SessionLocal
    from app.models import ParadeNight, Session as TrainingSession
    from app.routers.planning import _real_session_out, _session_out_context
    h = login(client, "ADMIN703")
    facs = _facs(client, h, 3)
    y = _year_with_sessions(client, h, nights=3, per_night=2, facs=facs)
    db = SessionLocal()
    try:
        ss = (db.query(TrainingSession).join(ParadeNight, TrainingSession.parade_night_id == ParadeNight.id)
              .filter(ParadeNight.planning_year_id == y).all())
        assert len(ss) == 6
        assert any(s.training_area_id for s in ss) and any(s.curriculum_item_id for s in ss), \
            "fixture must exercise the room and curriculum paths"
        ctx = _session_out_context(db, ss)
        for s in ss:
            assert _real_session_out(s, db, ctx=ctx) == _real_session_out(s, db), s.id
    finally:
        db.close()


def test_long_range_query_count_does_not_scale_with_sessions(client):
    h = login(client, "ADMIN703")
    facs = _facs(client, h, 3)
    counts = {}
    for name, nights in (("small", 2), ("large", 6)):
        y = _year_with_sessions(client, h, nights=nights, per_night=2, facs=facs)
        year = client.get(f"/api/planning/years/{y}", headers=h).json()["year"]
        url = f"/api/planning/years/{y}/long-range?weeks=8&from_date={year}-03-01"
        client.get(url, headers=h)
        with count_queries() as n:
            r = client.get(url, headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        served = sum(len(night["sessions"]) for night in body["parade_dates"])
        assert served == nights * 2, f"long-range must serve the sessions it is measured on ({served})"
        counts[name] = n["q"]
    print("LONG_RANGE_QUERIES", counts)
    assert counts["large"] <= counts["small"] + 4, counts
