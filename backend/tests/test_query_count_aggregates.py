"""Query counts of Wing/National aggregate endpoints must not grow with the org.

Measured on the national qualification dataset (60 squadrons, ~140 accounts):
/api/accounts 419 queries per request, /api/reports/wing-overview 325,
/api/reports/national-overview 149 -- per-row lookups that grow with every
account and squadron added. Statement counting, not wall-clock time.
"""
import uuid
from contextlib import contextmanager

from sqlalchemy import event

from app.database import engine
from tests.conftest import login


@contextmanager
def count_queries():
    n = {"q": 0}

    def _c(*_a, **_k):
        n["q"] += 1
    event.listen(engine, "before_cursor_execute", _c)
    try:
        yield n
    finally:
        event.remove(engine, "before_cursor_execute", _c)


def _add_squadrons_with_accounts(client, h, k):
    wings = client.get("/api/wings", headers=h).json()
    wid = wings[0]["wing_id"]
    for _ in range(k):
        code = uuid.uuid4().hex[:4].upper()
        s = client.post("/api/squadrons", headers=h, json={"wing_id": wid, "code": f"Z{code}", "name": f"QC {code}"})
        assert s.status_code == 200, s.text
        for role in ("sqn_admin", "sqn_general"):
            r = client.post("/api/accounts", headers=h, json={"display_name": f"QC {code} {role}", "role": role,
                                                             "squadron_id": s.json()["squadron_id"]})
            assert r.status_code == 200, r.text


def _measure(client, h, path):
    client.get(path, headers=h)
    with count_queries() as n:
        r = client.get(path, headers=h)
    assert r.status_code == 200, r.text
    return n["q"], r.json()


def test_accounts_list_query_count_is_flat_and_output_unchanged(client):
    h = login(client, "SYSADMIN2026")
    before, rows_before = _measure(client, h, "/api/accounts")
    _add_squadrons_with_accounts(client, h, 6)               # +6 squadrons, +12 accounts
    after, rows_after = _measure(client, h, "/api/accounts")
    print("ACCOUNTS_QUERIES", before, "->", after, "| accounts", len(rows_before), "->", len(rows_after))
    assert len(rows_after) >= len(rows_before) + 12
    assert after <= before + 3, (before, after)


def test_national_and_wing_overview_query_counts_are_flat(client):
    h = login(client, "ADMINNATIONAL")
    sa = login(client, "SYSADMIN2026")
    counts = {}
    for path in ("/api/reports/national-overview", "/api/reports/wing-overview"):
        counts[path] = [_measure(client, h, path)[0]]
    _add_squadrons_with_accounts(client, sa, 6)
    for path in counts:
        counts[path].append(_measure(client, h, path)[0])
    print("OVERVIEW_QUERIES", counts)
    for path, (b, a) in counts.items():
        assert a <= b + 3, (path, b, a)


def test_accounts_batched_and_per_account_serialisation_are_identical(client):
    from app.database import SessionLocal
    from app.models import User
    from app.routers.accounts import _account_out, _accounts_context
    db = SessionLocal()
    try:
        users = db.query(User).all()
        ctx = _accounts_context(db, users)
        for u in users:
            assert _account_out(u, db, ctx) == _account_out(u, db), u.id
    finally:
        db.close()


def test_coverage_for_many_equals_coverage_for_every_squadron(client):
    from app.database import SessionLocal
    from app.models import Squadron
    from app.routers.ops import _coverage_for, _coverage_for_many
    db = SessionLocal()
    try:
        ids = [s.id for s in db.query(Squadron).all()]
        many = _coverage_for_many(db, ids)
        for sq in ids:
            assert many[sq] == _coverage_for(db, sq), sq
    finally:
        db.close()
