"""Cross-surface data-freshness and data-quality indicators."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from .database import utcnow
from .models import Activity, Facilitator, ParadeNight, Session, Squadron

_DELIVERED = {"delivered", "delivered_with_issue"}
_TERMINAL = {
    "delivered",
    "delivered_with_issue",
    "not_delivered",
    "cancelled",
    "rescheduled",
}


def data_freshness(
    db: DBSession,
    scope: str,
    sq_id: str | None,
    wing_id: str | None,
) -> dict:
    """Compute the shared dashboard/command-centre data-quality summary."""
    as_at = datetime.now(timezone.utc).isoformat()
    issues: list[str] = []
    coverage_pct: int | None = None
    today_str = date.today().isoformat()
    sixty_days_ago = (date.today() - timedelta(days=60)).isoformat()

    if scope == "squadron" and sq_id:
        past_pn_ids = select(ParadeNight.id).where(
            ParadeNight.squadron_id == sq_id,
            ParadeNight.date < today_str,
            ParadeNight.is_archived == False,  # noqa: E712
        )
        unrecorded = (
            db.query(func.count(Session.id))
            .filter(
                Session.parade_night_id.in_(past_pn_ids),
                Session.status.notin_(list(_TERMINAL)),
                Session.is_archived == False,  # noqa: E712
            )
            .scalar()
            or 0
        )
        if unrecorded > 0:
            issues.append(f"{unrecorded} session(s) with unrecorded outcomes")

        last_cea: datetime | None = (
            db.query(func.max(Activity.updated_at))
            .filter(
                Activity.squadron_id == sq_id,
                Activity.cea_seq_nr.isnot(None),
                Activity.is_archived == False,  # noqa: E712
            )
            .scalar()
        )
        if last_cea is None:
            issues.append("No CEA import on record")
        else:
            cea_days = (utcnow() - last_cea).days
            if cea_days > 30:
                issues.append(f"CEA data is {cea_days} day(s) old")

        facilitators = (
            db.query(Facilitator)
            .filter(
                Facilitator.squadron_id == sq_id,
                Facilitator.active_status == True,  # noqa: E712
                Facilitator.is_archived == False,  # noqa: E712
            )
            .all()
        )
        incomplete_fac = sum(1 for facilitator in facilitators if not facilitator.subject_areas)
        if incomplete_fac > 0:
            issues.append(f"{incomplete_fac} facilitator(s) missing subject areas")

    elif scope in ("wing", "national"):
        sq_q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
        if scope == "wing" and wing_id:
            sq_q = sq_q.filter(Squadron.wing_id == wing_id)
        active_squadrons = sq_q.all()
        if active_squadrons:
            covered = 0
            for squadron in active_squadrons:
                pn_ids_sub = select(ParadeNight.id).where(
                    ParadeNight.squadron_id == squadron.id,
                    ParadeNight.date >= sixty_days_ago,
                    ParadeNight.is_archived == False,  # noqa: E712
                )
                has_delivery = (
                    db.query(Session.id)
                    .filter(
                        Session.parade_night_id.in_(pn_ids_sub),
                        Session.status.in_(list(_DELIVERED)),
                        Session.is_archived == False,  # noqa: E712
                    )
                    .first()
                )
                if has_delivery:
                    covered += 1
            coverage_pct = round(covered / len(active_squadrons) * 100)
            if coverage_pct < 80:
                issues.append(
                    f"Only {coverage_pct}% of squadrons have recent training delivery"
                )

    return {"as_at": as_at, "coverage_pct": coverage_pct, "issues": issues}
