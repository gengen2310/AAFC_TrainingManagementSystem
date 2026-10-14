"""Query-count regressions for stabilisation scaling seams.

These tests do not benchmark wall-clock time. They pin the important property:
adding more entities must not add one SQL round-trip per entity.
"""
from datetime import date, timedelta
import uuid

from sqlalchemy import event

from app.database import SessionLocal
from app.models import Facilitator, Squadron
from app.models.planning import PlanningFacilitatorLeave
from app.permissions import Principal
from app.routers.training import list_facs
from app.services_data_quality import data_freshness
from tests.conftest import login, next_test_year


def _count_selects(db, action):
    statements: list[str] = []

    def before_cursor_execute(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        result = action()
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)
    return result, statements


def test_facilitator_list_batches_upcoming_leave_queries():
    db = SessionLocal()
    marker = uuid.uuid4().hex[:10]
    facilitator_ids: list[str] = []
    try:
        squadron = db.query(Squadron).filter(
            Squadron.short_name == "703SQN",
            Squadron.is_archived == False,  # noqa: E712
        ).first()
        assert squadron is not None

        today = date.today()
        for idx in range(4):
            facilitator = Facilitator(
                squadron_id=squadron.id,
                wing_id=squadron.wing_id,
                first_name=f"Scale{marker}{idx}",
                last_name="QueryBound",
                type="Staff",
                subject_areas=[],
            )
            db.add(facilitator)
            db.flush()
            facilitator_ids.append(facilitator.id)
            db.add(PlanningFacilitatorLeave(
                facilitator_id=facilitator.id,
                start_date=(today + timedelta(days=idx + 1)).isoformat(),
                end_date=(today + timedelta(days=idx + 2)).isoformat(),
                reason=f"leave-{idx}",
            ))
        db.commit()

        principal = Principal(
            user_id="query-bound-test",
            role="sqn_admin",
            wing_id=squadron.wing_id,
            squadron_id=squadron.id,
            national_id=None,
        )
        rows, selects = _count_selects(
            db,
            lambda: list_facs(
                squadron_id=None,
                include_archived=False,
                db=db,
                p=principal,
            ),
        )

        mine = [row for row in rows if row["facilitator_id"] in facilitator_ids]
        assert len(mine) == 4
        assert all(len(row["upcoming_leave"]) == 1 for row in mine)
        # Facilitators + all leave rows. This must stay constant as the number
        # of facilitators grows.
        assert len(selects) <= 2, "\n\n".join(selects)
    finally:
        db.query(PlanningFacilitatorLeave).filter(
            PlanningFacilitatorLeave.facilitator_id.in_(facilitator_ids)
        ).delete(synchronize_session=False)
        db.query(Facilitator).filter(
            Facilitator.id.in_(facilitator_ids)
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_national_data_freshness_uses_constant_query_count():
    db = SessionLocal()
    try:
        result, selects = _count_selects(
            db,
            lambda: data_freshness(
                db=db,
                scope="national",
                sq_id=None,
                wing_id=None,
            ),
        )
        assert set(result) == {"as_at", "coverage_pct", "issues"}
        # Active Squadrons + distinct Squadrons with recent delivered sessions.
        # The old implementation was 1 + N SELECTs.
        assert len(selects) <= 2, "\n\n".join(selects)
    finally:
        db.close()


def test_long_range_batches_conflicts_across_parade_nights(client):
    headers = login(client, "ADMIN703")
    year = next_test_year()
    created = client.post(
        "/api/planning/years",
        json={"year": year, "name": f"{year} Query Bound Year"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    year_id = created.json()["planning_year_id"]

    dates = [f"{year}-08-{day:02d}" for day in (1, 8, 15, 22)]
    for parade_date in dates:
        response = client.post(
            f"/api/planning/years/{year_id}/parade-dates",
            json={"parade_date": parade_date},
            headers=headers,
        )
        assert response.status_code == 200, response.text

    db = SessionLocal()
    statements: list[str] = []

    def before_cursor_execute(_conn, _cursor, statement, _params, _context, _many):
        if "planning_conflicts" in statement.lower() and statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        response = client.get(
            f"/api/planning/years/{year_id}/long-range"
            f"?from_date={year}-08-01&end_date={year}-08-31",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["parade_dates"]) == 4
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)
        db.close()

    assert len(statements) == 1, "\n\n".join(statements)
