"""Shared building blocks for dashboard metrics: date windows, ISO weeks,
unit/session filters, and the delivery-status constants every chart uses.

Moved verbatim from routers/dashboard.py (stabilisation, service extraction). Pure
read-side computation: no HTTP, no authorization -- callers resolve scope first.
"""
from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy.orm import Session as DBSession

from .models import ParadeNight, Session, Squadron, Wing


_DELIVERED = {"delivered", "delivered_with_issue"}


_TERMINAL = {"delivered", "delivered_with_issue", "not_delivered", "cancelled", "rescheduled"}


_STATUS_COLORS = {
    "delivered": "#2e7d32",
    "delivered_with_issue": "#558b2f",
    "not_delivered": "#455560",
    "cancelled": "#e51937",
    "rescheduled": "#f57c00",
    "planned": "#51b0e3",
}


def _sqn_ids_for_wing(db: DBSession, wing_id: str) -> list[str]:
    """All active squadron IDs in the given wing."""
    return [
        r.id for r in db.query(Squadron.id)
        .filter(Squadron.wing_id == wing_id, Squadron.is_archived == False)  # noqa: E712
        .all()
    ]


def _wing_ids_for_national(db: DBSession) -> list[dict]:
    """All active wings with id + code."""
    rows = db.query(Wing.id, Wing.code, Wing.name).filter(Wing.is_archived == False).all()  # noqa: E712
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


def _date_window(window: str) -> tuple[str, str]:
    """Return (start_date_iso, end_date_iso) for the given window label."""
    today = date.today()
    if window == "week":
        return (today - timedelta(days=7)).isoformat(), (today + timedelta(days=7)).isoformat()
    if window == "semester":
        return (today - timedelta(days=182)).isoformat(), (today + timedelta(days=30)).isoformat()
    if window == "year":
        return f"{today.year}-01-01", f"{today.year}-12-31"
    # default: term ≈ last 90 days + next 30 days
    return (today - timedelta(days=90)).isoformat(), (today + timedelta(days=30)).isoformat()


def _iso_week(d: str) -> str:
    """Return YYYY-Www label for an ISO date string."""
    dt = date.fromisoformat(d)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def _command_child_units(db: DBSession, scope: str, wing_id: str | None) -> list[dict]:
    """Rows for the command dashboard: Squadrons for a Wing view, Wings for a
    National view. Archived units excluded, matching every other list
    endpoint in this codebase."""
    if scope == "wing":
        rows = db.query(Squadron).filter(
            Squadron.wing_id == wing_id, Squadron.is_archived == False,  # noqa: E712
        ).order_by(Squadron.code).all()
        return [{"id": r.id, "code": r.code, "name": r.short_name or r.name, "kind": "squadron"} for r in rows]
    rows = db.query(Wing).filter(Wing.is_archived == False).order_by(Wing.code).all()  # noqa: E712
    return [{"id": r.id, "code": r.code, "name": r.name, "kind": "wing"} for r in rows]


def _unit_session_filter(kind: str, unit_id: str):
    """SQLAlchemy filter clause selecting ParadeNight rows owned by one child unit."""
    if kind == "squadron":
        return ParadeNight.squadron_id == unit_id
    return ParadeNight.wing_id == unit_id


def _unit_pns_and_sessions(db: DBSession, kind: str, unit_id: str, window_start: str, window_end: str):
    pns = db.query(ParadeNight).filter(
        _unit_session_filter(kind, unit_id),
        ParadeNight.date >= window_start, ParadeNight.date <= window_end,
        ParadeNight.is_archived == False,  # noqa: E712
    ).all()
    pn_ids = [pn.id for pn in pns]
    sessions = db.query(Session).filter(
        Session.parade_night_id.in_(pn_ids), Session.is_archived == False,  # noqa: E712
    ).all() if pn_ids else []
    return pns, sessions
