from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_, and_

from ..database import get_db
from ..models import (
    Wing, Squadron, User, Facilitator, Activity, ParadeNight,
)
from ..models import Session as TrainingSession
from ..dependencies import get_principal
from ..permissions import (
    Principal, is_writer, level_scope_clause, squadron_scope_clause, wing_scope_clause,
)

router = APIRouter(prefix="/api", tags=["search"])

_LIMIT = 5


@router.get("/search")
def search_entities(
    q: str = "",
    p: Principal = Depends(get_principal),
    db: DBSession = Depends(get_db),
):
    q = q.strip()
    if len(q) < 2:
        return {"results": []}

    pat = f"%{q}%"
    results: list[dict] = []

    # The auditor sees national-scope Wings and Squadrons only; every other
    # result type is skipped for it below.
    is_auditor = p.is_auditor

    def scoped(q, clause):
        return q if clause is None else q.filter(clause)

    # ── Wings ─────────────────────────────────────────────────────────────
    wq = (
        db.query(Wing)
        .filter(Wing.is_archived == False, Wing.active_status == True)  # noqa: E712
        .filter(or_(Wing.name.ilike(pat), Wing.code.ilike(pat), Wing.short_name.ilike(pat)))
    )
    wq = scoped(wq, wing_scope_clause(p, Wing.id))
    for w in wq.limit(_LIMIT).all():
        results.append({
            "type": "wing", "id": w.id, "label": w.name,
            "sub": w.code, "meta": {"code": w.code},
        })

    # ── Squadrons ─────────────────────────────────────────────────────────
    sq = (
        db.query(Squadron)
        .filter(Squadron.is_archived == False, Squadron.active_status == True)  # noqa: E712
        .filter(or_(Squadron.name.ilike(pat), Squadron.short_name.ilike(pat), Squadron.code.ilike(pat)))
    )
    sq = scoped(sq, level_scope_clause(p, wing_column=Squadron.wing_id, squadron_column=Squadron.id))
    for s in sq.limit(_LIMIT).all():
        w_row = db.query(Wing).filter(Wing.id == s.wing_id).first()
        results.append({
            "type": "squadron", "id": s.id, "label": s.name,
            "sub": w_row.code if w_row else "",
            "meta": {"code": s.code, "wing_id": s.wing_id},
        })

    if not is_auditor:
        # ── Facilitators ───────────────────────────────────────────────────
        fq = (
            db.query(Facilitator)
            .filter(Facilitator.is_archived == False)  # noqa: E712
            .filter(or_(Facilitator.first_name.ilike(pat), Facilitator.last_name.ilike(pat)))
        )
        fq = scoped(fq, level_scope_clause(
            p, wing_column=Facilitator.wing_id, squadron_column=Facilitator.squadron_id))
        for f in fq.limit(_LIMIT).all():
            name = f"{f.first_name or ''} {f.last_name}".strip()
            sqn_row = (
                db.query(Squadron).filter(Squadron.id == f.squadron_id).first()
                if f.squadron_id else None
            )
            results.append({
                "type": "facilitator", "id": f.id, "label": name,
                "sub": sqn_row.code if sqn_row else "",
                "meta": {
                    "first_name": f.first_name or "",
                    "last_name": f.last_name,
                    "squadron_id": f.squadron_id or "",
                },
            })

        # ── Activities ─────────────────────────────────────────────────────
        aq = (
            db.query(Activity)
            .filter(Activity.is_archived == False)  # noqa: E712
            .filter(or_(
                Activity.activity_name.ilike(pat),
                Activity.date_start.ilike(pat),
                Activity.location.ilike(pat),
            ))
        )
        activity_scope = level_scope_clause(
            p, wing_column=Activity.wing_id, squadron_column=Activity.squadron_id)
        if activity_scope is not None and not p.is_wing:
            # A Squadron account also sees its own Wing's Wing-owned activities.
            activity_scope = or_(activity_scope, and_(
                Activity.owning_level == "wing", wing_scope_clause(p, Activity.wing_id)))
        aq = scoped(aq, activity_scope)
        for a in aq.limit(_LIMIT).all():
            owning = (a.owning_level or "squadron").capitalize() + " Activity"
            results.append({
                "type": "activity", "id": a.id, "label": a.activity_name,
                "sub": f"{owning} · {a.date_start}", "meta": {},
            })

        # ── Accounts ──────────────────────────────────────────────────────
        if is_writer(p):
            uq = (
                db.query(User)
                .filter(User.is_archived == False, User.active_status == True)  # noqa: E712
                .filter(or_(User.display_name.ilike(pat), User.role.ilike(pat)))
            )
            # By the user's own wing_id (narrower than /api/accounts' Wing scope).
            uq = scoped(uq, level_scope_clause(p, wing_column=User.wing_id, squadron_column=User.squadron_id))
            for u in uq.limit(_LIMIT).all():
                sqn_row = (
                    db.query(Squadron).filter(Squadron.id == u.squadron_id).first()
                    if u.squadron_id else None
                )
                results.append({
                    "type": "account", "id": u.id, "label": u.display_name,
                    "sub": f"{u.role} · {sqn_row.code}" if sqn_row else u.role,
                    "meta": {},
                })

        # ── Sessions ───────────────────────────────────────────────────────
        sess_q = (
            db.query(TrainingSession, ParadeNight)
            .join(ParadeNight, TrainingSession.parade_night_id == ParadeNight.id)
            .filter(
                TrainingSession.is_archived == False,  # noqa: E712
                ParadeNight.is_archived == False,       # noqa: E712
            )
            .filter(or_(
                TrainingSession.curriculum_title_at_time.ilike(pat),
                TrainingSession.curriculum_code_at_time.ilike(pat),
                TrainingSession.session_title.ilike(pat),
                TrainingSession.custom_title.ilike(pat),
            ))
        )
        sess_q = scoped(sess_q, squadron_scope_clause(
            p, db, TrainingSession.squadron_id, include_archived=False))
        for sess, pn in sess_q.limit(_LIMIT).all():
            label = (
                sess.curriculum_title_at_time
                or sess.custom_title
                or sess.session_title
                or "Session"
            )
            results.append({
                "type": "session", "id": sess.id, "label": label,
                "sub": pn.date, "meta": {"pn_date": pn.date},
            })

    return {"results": results[:30]}
