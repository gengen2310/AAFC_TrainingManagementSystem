"""Service Desk ticket list is bounded (issue #70, C8, 2026-10-10).

GET /api/service-desk/tickets returned every ticket ever raised to national
roles (docs/stabilisation/bounded-responses.md: "grows forever"). It now always
pages: `limit` (default 100, max 200) and `offset`, newest first with a stable
tie-break, and the filtered total in `X-Total-Count` (exposed to the
cross-origin Main TMS through CORS). The body keeps its list shape.
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.database import SessionLocal, engine
from app.models import ServiceTicket
from tests.conftest import login

MARK = "c8-paging-fixture"


@contextmanager
def _tickets(n: int, *, same_instant: bool = False, status: str = "open"):
    """n national-visible tickets; with same_instant all share one created_at,
    so only the tie-break can order them. Removed afterwards."""
    db = SessionLocal()
    base = datetime.now(timezone.utc) + timedelta(days=3650)   # newest in the table
    ids = []
    try:
        for i in range(n):
            t = ServiceTicket(
                id=str(uuid.uuid4()), rank="Cdt", first_name="Page", last_name=f"T{i:04d}",
                email="page@example.org", category="other", description=MARK, status=status,
                created_at=base if same_instant else base + timedelta(seconds=i),
            )
            db.add(t)
            ids.append(t.id)
        db.commit()
        yield ids
    finally:
        db.query(ServiceTicket).filter(ServiceTicket.description == MARK).delete()
        db.commit()
        db.close()


def _all_ids(client, h, **params):
    seen, offset = [], 0
    for _ in range(100):            # a page loop that never ends is a failure, not a hang
        r = client.get("/api/service-desk/tickets", headers=h, params={**params, "offset": offset})
        assert r.status_code == 200, r.text
        page = r.json()
        if not page:
            return seen, int(r.headers["X-Total-Count"])
        seen += [t["ticket_id"] for t in page]
        offset += len(page)
    raise AssertionError(f"paging did not terminate after 100 pages ({len(seen)} rows)")


def test_default_page_is_bounded_and_reports_the_total(client):
    h = login(client, "ADMINNATIONAL")
    with _tickets(250):
        r = client.get("/api/service-desk/tickets", headers=h)
        assert r.status_code == 200
        assert len(r.json()) == 100
        db = SessionLocal()
        try:
            total = db.query(ServiceTicket).count()
        finally:
            db.close()
        assert int(r.headers["X-Total-Count"]) == total


def test_pages_are_disjoint_and_cover_every_ticket_newest_first(client):
    h = login(client, "ADMINNATIONAL")
    with _tickets(250) as ids:
        seen, total = _all_ids(client, h, limit=73)
        assert len(seen) == len(set(seen)) == total
        mine = [i for i in seen if i in set(ids)]
        assert mine == list(reversed(ids))            # created_at desc


def test_equal_timestamps_still_page_without_gaps_or_repeats(client):
    h = login(client, "ADMINNATIONAL")
    with _tickets(30, same_instant=True) as ids:
        seen, _ = _all_ids(client, h, limit=7)
        assert sorted(i for i in seen if i in set(ids)) == sorted(ids)
        assert len(seen) == len(set(seen))


def test_limit_is_capped_and_validated(client):
    h = login(client, "ADMINNATIONAL")
    assert client.get("/api/service-desk/tickets", headers=h, params={"limit": 201}).status_code == 422
    assert client.get("/api/service-desk/tickets", headers=h, params={"limit": 0}).status_code == 422
    assert client.get("/api/service-desk/tickets", headers=h, params={"offset": -1}).status_code == 422


def test_status_filter_is_applied_before_paging(client):
    # The Main TMS used to filter by status client-side over the full list;
    # over a page that would silently hide matches, so the filter is server-side
    # and the total counts filtered rows.
    h = login(client, "ADMINNATIONAL")
    with _tickets(5, status="resolved"):
        seen, total = _all_ids(client, h, status="resolved", limit=2)
        assert total == len(seen) >= 5
        r = client.get("/api/service-desk/tickets", headers=h, params={"status": "resolved", "limit": 200})
        assert all(t["status"] == "resolved" for t in r.json())


def test_total_header_is_readable_cross_origin(client):
    h = login(client, "ADMINNATIONAL")
    from app.config import settings
    origin = settings.cors_origins[0]
    r = client.get("/api/service-desk/tickets", headers={**h, "Origin": origin})
    exposed = r.headers.get("access-control-expose-headers", "")
    assert "x-total-count" in exposed.lower()


def test_a_page_costs_a_constant_number_of_queries(client):
    h = login(client, "ADMINNATIONAL")
    with _tickets(150):
        counts = []
        for limit in (10, 150):
            n = [0]
            def _c(*_a, **_k):
                n[0] += 1
            event.listen(engine, "before_cursor_execute", _c)
            try:
                assert client.get("/api/service-desk/tickets", headers=h, params={"limit": limit}).status_code == 200
            finally:
                event.remove(engine, "before_cursor_execute", _c)
            counts.append(n[0])
        assert counts[0] == counts[1], counts
