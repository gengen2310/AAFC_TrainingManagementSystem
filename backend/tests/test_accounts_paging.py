"""GET /api/accounts: opt-in paging and a role filter (issue #70, C8, 2026-10-11).

The Main TMS Accounts page filters, searches and batch-edits one in-memory
list, so the default response stays the full scoped list
(docs/stabilisation/bounded-responses.md: scope-bounded, acceptable until the
national list passes ~2,000). What changes:

- `limit`/`offset` page on a stable order (display_name, then id) for callers
  that can page; `X-Total-Count` always reports the filtered total.
- `role` may repeat, so the Service Desk asks for its eligible assignees
  instead of downloading every account.
- The full national list costs a constant number of queries at 1,000 accounts.
"""
import uuid
from contextlib import contextmanager

from sqlalchemy import event

from app.database import SessionLocal, engine
from app.models import Squadron, User
from tests.conftest import login

MARK = "C8 paging fixture"


@contextmanager
def _accounts(n: int):
    """n active sqn_general accounts in one seeded Squadron, all with the same
    display name so only the id tie-break can order them. Removed afterwards."""
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").one()
        ids = []
        for _ in range(n):
            u = User(id=str(uuid.uuid4()), display_name=MARK, role="sqn_general",
                     squadron_id=sqn.id, wing_id=sqn.wing_id, active_status=True)
            db.add(u)
            ids.append(u.id)
        db.commit()
        yield ids
    finally:
        db.query(User).filter(User.display_name == MARK).delete()
        db.commit()
        db.close()


def _fixture_rows(client, h, **params):
    r = client.get("/api/accounts", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r


def test_default_response_is_still_the_full_list_with_its_total(client):
    h = login(client, "ADMINNATIONAL")
    with _accounts(250):
        r = _fixture_rows(client, h)
        body = r.json()
        assert isinstance(body, list)
        assert sum(1 for a in body if a["display_name"] == MARK) == 250
        assert int(r.headers["X-Total-Count"]) == len(body)


def test_pages_cover_every_row_once_on_a_stable_order(client):
    h = login(client, "ADMINNATIONAL")
    with _accounts(130) as ids:
        full = [a["user_id"] for a in _fixture_rows(client, h).json()]
        seen, offset = [], 0
        while True:
            r = _fixture_rows(client, h, limit=50, offset=offset)
            page = r.json()
            assert int(r.headers["X-Total-Count"]) == len(full)
            if not page:
                break
            assert len(page) <= 50
            seen += [a["user_id"] for a in page]
            offset += len(page)
        assert seen == full                     # same order, no gap, no repeat
        assert set(ids) <= set(seen)


def test_limit_is_capped(client):
    h = login(client, "ADMINNATIONAL")
    r = client.get("/api/accounts", headers=h, params={"limit": 501})
    assert r.status_code == 422


def test_paging_never_widens_scope(client):
    """A Squadron Admin pages only their own Squadron, whatever the offset."""
    h = login(client, "ADMIN703")
    full = _fixture_rows(client, h).json()
    paged = _fixture_rows(client, h, limit=1, offset=0).json()
    assert int(_fixture_rows(client, h, limit=1).headers["X-Total-Count"]) == len(full)
    assert {a["squadron_code"] for a in full} <= {"703", None}
    assert paged and paged[0]["user_id"] == full[0]["user_id"]


def test_role_repeats_for_service_desk_assignees(client):
    h = login(client, "ADMINNATIONAL")
    admins = ("system_admin", "national_admin", "wing_admin")
    r = _fixture_rows(client, h, role=list(admins), active_status="true")
    body = r.json()
    assert body and {a["role"] for a in body} <= set(admins)
    full = _fixture_rows(client, h).json()
    expected = [a["user_id"] for a in full if a["role"] in admins and a["active_status"]]
    assert [a["user_id"] for a in body] == expected
    # A single role keeps working exactly as before.
    one = _fixture_rows(client, h, role="wing_admin").json()
    assert one and {a["role"] for a in one} == {"wing_admin"}


def test_full_national_list_is_constant_queries_at_1000_accounts(client):
    h = login(client, "ADMINNATIONAL")
    counts = {}
    for n in (10, 1000):
        with _accounts(n):
            statements = []

            def _count(*_a, **_k):
                statements.append(1)
            event.listen(engine, "before_cursor_execute", _count)
            try:
                r = _fixture_rows(client, h)
            finally:
                event.remove(engine, "before_cursor_execute", _count)
            assert sum(1 for a in r.json() if a["display_name"] == MARK) == n
            counts[n] = len(statements)
    assert counts[1000] == counts[10], counts
