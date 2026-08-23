import io, csv, json, logging
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow, iso_z
from ..models import (Session, ParadeNight, CurriculumItem, ActionItem, Exception as Exc,
                      Squadron, Wing, ImportLog, AuditLog)
from ..dependencies import get_principal
from ..permissions import Principal, require_role, require_can_view_squadron, require_can_view_wing
from ..services import audit, score_parade
from ..services_readiness import parade_night_readiness
from .training import _view_squadron_id

router = APIRouter(prefix="/api", tags=["ops"])


def _active_squadron(p: Principal) -> str:
    return p.acting_squadron_id or p.squadron_id


def _all_sessions(db, sq_id):
    return (db.query(Session).join(ParadeNight, ParadeNight.id == Session.parade_night_id)
            .filter(Session.squadron_id == sq_id, Session.is_archived == False).all())  # noqa: E712


def _coverage_for(db, sq_id):
    """Curriculum coverage for one squadron: overall pct, not-delivered count, and per-phase pct.

    Coverage = curriculum items that have at least one session / total applicable items.
    Phase pct is the same ratio computed within each phase, for the Wing heatmap.
    """
    items = db.query(CurriculumItem).filter(
        (CurriculumItem.owning_level == "national") | (CurriculumItem.squadron_id == sq_id),
        CurriculumItem.is_archived == False).all()  # noqa: E712
    sessions = _all_sessions(db, sq_id)
    scheduled = {s.curriculum_item_id for s in sessions if s.curriculum_item_id}
    not_delivered = sum(1 for s in sessions if s.status == "not_delivered")
    total = len(items)
    sched = len([i for i in items if i.id in scheduled])
    overall = round(sched / total * 100) if total else 0
    by_phase: dict[str, dict[str, int]] = {}
    for i in items:
        ph = i.phase or "Unspecified"
        b = by_phase.setdefault(ph, {"total": 0, "sched": 0})
        b["total"] += 1
        if i.id in scheduled:
            b["sched"] += 1
    phase_pct = {ph: (round(b["sched"] / b["total"] * 100) if b["total"] else 0) for ph, b in by_phase.items()}
    return {"coverage_pct": overall, "not_delivered": not_delivered, "phase_pct": phase_pct}


# ── REPORTS ──
@router.get("/reports/summary")
def rep_summary(squadron_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _view_squadron_id(p, squadron_id, db)
    sess = _all_sessions(db, sq)
    counts = {}
    for s in sess:
        counts[s.status] = counts.get(s.status, 0) + 1
    return {"title": "Training summary", "generated_at": utcnow().isoformat(), "counts": counts,
            "total": len(sess), "decision": "monitor" if counts.get("not_delivered") else "no_action"}


@router.get("/reports/readiness")
def rep_readiness(squadron_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _view_squadron_id(p, squadron_id, db) if squadron_id else _active_squadron(p)
    today = date.today().isoformat()
    pns = db.query(ParadeNight).filter(ParadeNight.squadron_id == sq, ParadeNight.date >= today).order_by(ParadeNight.date).all()
    out = []
    for pn in pns[:8]:
        sess = [{c.name: getattr(s, c.name) for c in s.__table__.columns}
                for s in db.query(Session).filter(Session.parade_night_id == pn.id).all()]
        # Same authoritative computation as the Dashboard/training.py — a zero-session
        # night reports planning_status "not_planned" (never a 100/"Ready" legacy_score).
        readiness = parade_night_readiness(sess)
        r = score_parade(sess)  # legacy shape (score/band/deductions), derived from the same computation
        out.append({"parade_night_id": pn.id, "date": pn.date, "score": r["score"], "band": r["band"],
                    "deductions": r["deductions"], "planning_status": readiness["planning_status"],
                    "data_quality": readiness["data_quality"]})
    worst = min((o["score"] for o in out), default=100)
    decision = "no_action" if worst >= 85 else "action_required" if worst >= 50 else "command_decision_required"
    return {"title": "Next parade readiness", "parade_nights": out, "decision": decision}


@router.get("/reports/curriculum-coverage")
def rep_coverage(squadron_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _view_squadron_id(p, squadron_id, db) if squadron_id else _active_squadron(p)
    items = db.query(CurriculumItem).filter(
        (CurriculumItem.owning_level == "national") | (CurriculumItem.squadron_id == sq),
        CurriculumItem.is_archived == False).all()  # noqa: E712
    all_sess = _all_sessions(db, sq)
    scheduled = {s.curriculum_item_id for s in all_sess if s.curriculum_item_id}
    delivered = {s.curriculum_item_id for s in all_sess
                 if s.curriculum_item_id and s.status in ("delivered", "delivered_with_issue")}
    total = len(items)
    sched = len([i for i in items if i.id in scheduled])
    pct = round(sched / total * 100) if total else 0
    unscheduled = [{"code": i.code, "title": i.title, "phase": i.phase} for i in items if i.id not in scheduled]
    decision = "no_action" if pct == 100 else "action_required" if pct >= 70 else "command_decision_required"
    return {"title": "Curriculum coverage", "total": total, "scheduled": sched,
            "delivered": len([i for i in items if i.id in delivered]), "coverage_pct": pct,
            "unscheduled": unscheduled, "decision": decision}


@router.get("/reports/facilitator-load")
def rep_load(squadron_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _view_squadron_id(p, squadron_id, db)
    load = {}
    for s in _all_sessions(db, sq):
        name = s.facilitator_display_name_at_time
        if not name:
            continue
        load.setdefault(name, {"name": name, "facilitator_id": s.facilitator_id, "sessions": 0, "delivered": 0})
        load[name]["sessions"] += 1
        if s.status == "delivered":
            load[name]["delivered"] += 1
    rows = sorted(load.values(), key=lambda x: -x["sessions"])
    for r in rows:
        r["risk"] = "overloaded" if r["sessions"] > 10 else "high" if r["sessions"] > 6 else "ok"
    return {"title": "Facilitator load", "facilitators": rows,
            "decision": "action_required" if any(r["risk"] != "ok" for r in rows) else "no_action"}


@router.get("/reports/not-delivered")
def rep_nd(squadron_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _view_squadron_id(p, squadron_id, db)
    rows = [s for s in _all_sessions(db, sq) if s.status == "not_delivered"]
    return {"title": "Not delivered", "sessions": [{"id": s.id, "curriculum_code_at_time": s.curriculum_code_at_time,
            "not_delivered_reason": s.not_delivered_reason, "status": s.status} for s in rows],
            "decision": "action_required" if rows else "no_action"}


@router.get("/reports/wing-overview")
def wing_overview(wing_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "wing_viewer", "wing_admin", "national_viewer", "national_admin", "system_admin", "auditor")
    # wing_admin/wing_viewer are always pinned to their own wing; a national-scope
    # principal may optionally pass wing_id to filter to one Wing (view-only,
    # no proxy/DI required — mirrors the dashboard's wing_id param).
    if p.is_wing:
        w_id = p.wing_id
    elif wing_id:
        if not db.get(Wing, wing_id):
            raise HTTPException(404, detail={"error": "wing_not_found"})
        require_can_view_wing(p, wing_id)
        w_id = wing_id
    else:
        w_id = None
    q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
    if w_id:
        q = q.filter(Squadron.wing_id == w_id)
    out = []
    today = date.today().isoformat()
    for s in q.all():
        pns = db.query(ParadeNight).filter(ParadeNight.squadron_id == s.id).all()
        sess = db.query(Session).filter(Session.squadron_id == s.id).all()
        delivered = sum(1 for x in sess if x.status == "delivered")
        published = sum(1 for x in pns if x.published_status)
        future = [x for x in pns if x.date >= today]
        score = None
        planning_status = None
        if future:
            nxt = sorted(future, key=lambda x: x.date)[0]
            ns = [{c.name: getattr(z, c.name) for c in z.__table__.columns}
                  for z in db.query(Session).filter(Session.parade_night_id == nxt.id).all()]
            # Same authoritative computation as the Dashboard and /reports/readiness —
            # a squadron whose next parade night has zero sessions reports
            # planning_status "not_planned", never a numeric "readiness" that reads
            # as fully staffed/ready.
            readiness = parade_night_readiness(ns)
            score = readiness["legacy_score"]
            planning_status = readiness["planning_status"]
        cov = _coverage_for(db, s.id)
        out.append({"squadron_id": s.id, "code": s.code, "short_name": s.short_name,
                    "parade_day": s.default_parade_day, "nights": len(pns), "published": published,
                    "sessions": len(sess), "delivered": delivered,
                    "pct": round(delivered / len(sess) * 100) if sess else 0, "readiness": score,
                    "planning_status": planning_status,
                    "coverage_pct": cov["coverage_pct"], "not_delivered": cov["not_delivered"],
                    "no_future_plan": len(future) == 0, "no_published_plan": published == 0})
    return {"squadrons": out}


@router.get("/reports/wing-cancellation-trend")
def wing_cancellation_trend(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Per-squadron cancelled session and parade-night counts for Wing command review.

    Cancelled sessions are those with Session.status == 'cancelled'.
    Cancelled nights are ParadeNights with parade_type == 'cancelled' (stand-down / wash-out).
    Reasons are aggregated from Session.cancelled_reason (free text, grouped by value).
    """
    require_role(p, "wing_viewer", "wing_admin", "national_viewer", "national_admin", "system_admin", "auditor")
    wing_id = p.wing_id if p.is_wing else None
    q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
    if wing_id:
        q = q.filter(Squadron.wing_id == wing_id)
    out = []
    for s in q.all():
        cancelled_sess = [x for x in _all_sessions(db, s.id) if x.status == "cancelled"]
        cancelled_nights = db.query(ParadeNight).filter(
            ParadeNight.squadron_id == s.id,
            ParadeNight.parade_type == "cancelled").count()
        reason_counts: dict[str, int] = {}
        for x in cancelled_sess:
            key = (x.cancelled_reason or "unspecified").strip()[:80]
            reason_counts[key] = reason_counts.get(key, 0) + 1
        out.append({
            "squadron_id": s.id, "code": s.code, "short_name": s.short_name,
            "cancelled_sessions": len(cancelled_sess),
            "cancelled_nights": cancelled_nights,
            "reasons": sorted([{"reason": k, "count": v} for k, v in reason_counts.items()],
                               key=lambda x: -x["count"]),
        })
    out.sort(key=lambda x: -(x["cancelled_sessions"] + x["cancelled_nights"]))
    total_sess = sum(x["cancelled_sessions"] for x in out)
    total_nights = sum(x["cancelled_nights"] for x in out)
    return {"title": "Cancelled / rescheduled trend", "squadrons": out,
            "total_cancelled_sessions": total_sess, "total_cancelled_nights": total_nights,
            "decision": "action_required" if total_sess + total_nights > 0 else "no_action"}


@router.get("/reports/wing-not-delivered")
def wing_not_delivered(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Wing-wide aggregation of not-delivered sessions, ranked by squadron count."""
    require_role(p, "wing_viewer", "wing_admin", "national_viewer", "national_admin", "system_admin", "auditor")
    wing_id = p.wing_id if p.is_wing else None
    q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
    if wing_id:
        q = q.filter(Squadron.wing_id == wing_id)
    out = []
    for s in q.all():
        rows = [x for x in _all_sessions(db, s.id) if x.status == "not_delivered"]
        if rows:
            out.append({
                "squadron_id": s.id, "code": s.code, "short_name": s.short_name,
                "not_delivered_count": len(rows),
                "sessions": [{"id": x.id, "curriculum_code_at_time": x.curriculum_code_at_time,
                              "not_delivered_reason": x.not_delivered_reason} for x in rows],
            })
    out.sort(key=lambda x: -x["not_delivered_count"])
    return {"title": "Cross-squadron not-delivered", "squadrons": out,
            "total_not_delivered": sum(x["not_delivered_count"] for x in out),
            "decision": "action_required" if out else "no_action"}


@router.get("/reports/wing-phase-coverage")
def wing_phase_coverage(wing_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Squadron x phase coverage matrix for the Wing heatmap.

    Returns the ordered list of phases seen across the Wing, and for each squadron the coverage
    percentage in each phase (missing phase = 0). Real data only — no fabricated cells.
    """
    require_role(p, "wing_viewer", "wing_admin", "national_viewer", "national_admin", "system_admin", "auditor")
    if p.is_wing:
        w_id = p.wing_id
    elif wing_id:
        if not db.get(Wing, wing_id):
            raise HTTPException(404, detail={"error": "wing_not_found"})
        require_can_view_wing(p, wing_id)
        w_id = wing_id
    else:
        w_id = None
    q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
    if w_id:
        q = q.filter(Squadron.wing_id == w_id)
    # Canonical phase order; any extra phases are appended alphabetically.
    order = ["A. Orientation", "B. Initial", "C. Junior", "I. Bronze", "D. Intermediate",
             "J. Silver", "E. Senior", "K. Gold"]
    rows, seen = [], set()
    for s in q.all():
        cov = _coverage_for(db, s.id)
        seen.update(cov["phase_pct"].keys())
        rows.append({"squadron_id": s.id, "short_name": s.short_name, "phase_pct": cov["phase_pct"]})
    phases = [ph for ph in order if ph in seen] + sorted(seen - set(order))
    return {"phases": phases, "squadrons": rows}


# ── WING / NATIONAL CAPABILITY (facilitator load + subject balance, real per-SQN data) ──
SUBJECT_KEYS = ["service", "drill", "field", "lead", "comm", "stem"]
_SUBJECT_MAP = {
    "service": ["service", "sqn_affairs", "affairs"],
    "drill":   ["drill", "ceremonial", "discipline"],
    "field":   ["field", "survival", "fieldcraft", "bushcraft"],
    "lead":    ["pdl", "leadership", "personal_dev", "teamwork", "personal dev"],
    "comm":    ["community", "sfa", "service_community", "engagement"],
    "stem":    ["air", "space", "aviation", "cyber", "rpas", "stem", "air_space"],
}
def _subject_of(tag):
    if not tag:
        return None
    t = str(tag).lower()
    for k, keys in _SUBJECT_MAP.items():
        if any(part.split("_")[0] in t for part in keys):
            return k
    return None

def _capability_for_squadron(db, s):
    from ..models import Facilitator
    facs = db.query(Facilitator).filter(Facilitator.squadron_id == s.id,
                                        Facilitator.is_archived == False).all()  # noqa: E712
    subj_facs = {k: set() for k in SUBJECT_KEYS}
    for f_ in facs:
        tags = f_.subject_areas or []
        for tg in tags:
            k = _subject_of(tg)
            if k:
                subj_facs[k].add(f_.id)
    subject_facilitators = {k: len(v) for k, v in subj_facs.items()}
    sess = _all_sessions(db, s.id)
    delivered = sum(1 for x in sess if x.status == "delivered")
    subj_sessions = {k: 0 for k in SUBJECT_KEYS}
    for x in sess:
        k = _subject_of(getattr(x, "element_at_time", None))
        if k:
            subj_sessions[k] += 1
    pns = db.query(ParadeNight).filter(ParadeNight.squadron_id == s.id).all()
    today = date.today().isoformat()
    future = sorted([x for x in pns if x.date >= today], key=lambda x: x.date)
    sched_ids, unfilled = set(), 0
    if future:
        nsess = db.query(Session).filter(Session.parade_night_id == future[0].id).all()
        for z in nsess:
            if z.facilitator_id:
                sched_ids.add(z.facilitator_id)
            else:
                unfilled += 1
    fc = len(facs)
    return {
        "squadron_id": s.id, "code": s.code, "short_name": s.short_name,
        "facilitator_count": fc,
        "subject_facilitators": subject_facilitators,
        "sessions_total": len(sess), "delivered": delivered,
        "subject_sessions": subj_sessions,
        "next_night_scheduled": len(sched_ids),
        "next_night_available": max(0, fc - len(sched_ids)),
        "next_night_unfilled": unfilled,
        "avg_lessons_per_fac": round(delivered / fc, 1) if fc else 0,
        "nights": len(pns),
    }

@router.get("/reports/wing-capability")
def wing_capability(wing_id: str | None = None, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "wing_viewer", "wing_admin", "national_viewer", "national_admin", "system_admin", "auditor")
    if p.is_wing:
        w_id = p.wing_id
    elif wing_id:
        if not db.get(Wing, wing_id):
            raise HTTPException(404, detail={"error": "wing_not_found"})
        require_can_view_wing(p, wing_id)
        w_id = wing_id
    else:
        w_id = None
    q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
    if w_id:
        q = q.filter(Squadron.wing_id == w_id)
    rows = [_capability_for_squadron(db, s) for s in q.all()]
    # Wing averages and subject totals
    agg = {k: 0 for k in SUBJECT_KEYS}
    for r in rows:
        for k in SUBJECT_KEYS:
            agg[k] += r["subject_sessions"][k]
    tot = sum(agg.values()) or 1
    wing_avg = {k: round(agg[k] / tot * 100) for k in SUBJECT_KEYS}
    gaps = {k: {"none": sum(1 for r in rows if r["subject_facilitators"][k] == 0),
                "one": sum(1 for r in rows if r["subject_facilitators"][k] == 1)}
            for k in SUBJECT_KEYS}
    return {"subjects": SUBJECT_KEYS, "squadrons": rows, "wing_avg": wing_avg,
            "wing_subject_totals": agg, "capability_gaps": gaps, "squadron_count": len(rows)}

@router.get("/reports/national-capability")
def national_capability(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "national_viewer", "national_admin", "system_admin", "auditor")
    out = []
    for w in db.query(Wing).filter(Wing.is_archived == False).all():  # noqa: E712
        sqs = db.query(Squadron).filter(Squadron.wing_id == w.id,
                                        Squadron.is_archived == False).all()  # noqa: E712
        rows = [_capability_for_squadron(db, s) for s in sqs]
        fac_total = sum(r["facilitator_count"] for r in rows)
        subj_none = {k: sum(1 for r in rows if r["subject_facilitators"][k] == 0) for k in SUBJECT_KEYS}
        agg = {k: sum(r["subject_sessions"][k] for r in rows) for k in SUBJECT_KEYS}
        tot = sum(agg.values()) or 1
        dist = {k: round(agg[k] / tot * 100) for k in SUBJECT_KEYS}
        out.append({"wing_id": w.id, "code": w.code, "name": w.name,
                    "squadrons": len(rows), "facilitator_total": fac_total,
                    "subject_none_sqns": subj_none, "subject_distribution": dist})
    return {"subjects": SUBJECT_KEYS, "wings": out}


@router.get("/reports/national-overview")
def national_overview(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "national_viewer", "national_admin", "system_admin", "auditor")
    out = []
    for w in db.query(Wing).filter(Wing.is_archived == False).all():  # noqa: E712
        sqns = db.query(Squadron).filter(Squadron.wing_id == w.id, Squadron.is_archived == False).all()  # noqa: E712
        sess = db.query(Session).join(Squadron, Squadron.id == Session.squadron_id).filter(Squadron.wing_id == w.id).all()
        delivered = sum(1 for s in sess if s.status == "delivered")
        nd = sum(1 for s in sess if s.status == "not_delivered")
        covs = [_coverage_for(db, sq.id)["coverage_pct"] for sq in sqns]
        coverage_pct = round(sum(covs) / len(covs)) if covs else 0
        out.append({"wing_id": w.id, "code": w.code, "name": w.name, "squadrons": len(sqns),
                    "sessions": len(sess), "delivered": delivered, "not_delivered": nd,
                    "coverage_pct": coverage_pct})
    return {"wings": out}


# ── ACTION ITEMS ──
class ActionIn(BaseModel):
    title: str
    description: str | None = None
    owner: str | None = None
    due_date: str | None = None
    severity: str | None = "action_required"


@router.get("/action-items")
def list_actions(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _active_squadron(p)
    rows = db.query(ActionItem).filter(ActionItem.squadron_id == sq).order_by(ActionItem.status.desc()).all()
    return [{"action_id": a.id, "title": a.title, "description": a.description, "owner": a.owner,
             "due_date": a.due_date, "status": a.status, "severity": a.severity, "source": a.source} for a in rows]


@router.post("/action-items")
def add_action(body: ActionIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _active_squadron(p)
    s = db.get(Squadron, sq)
    from ..permissions import require_can_write_squadron
    require_can_write_squadron(p, s.id, s.wing_id)
    a = ActionItem(scope="squadron", squadron_id=sq, wing_id=s.wing_id, title=body.title,
                   description=body.description, owner=body.owner, due_date=body.due_date,
                   severity=body.severity or "action_required", source="manual", created_by=p.user_id)
    db.add(a); db.commit()
    audit(db, p, object_type="action_item", object_id=a.id, action="create")
    return {"ok": True, "action_id": a.id}


@router.post("/action-items/{aid}/close")
def close_action(aid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    a = db.get(ActionItem, aid)
    if not a:
        raise HTTPException(404, detail={"error": "not_found"})
    from ..permissions import require_can_write_squadron
    require_can_write_squadron(p, a.squadron_id, a.wing_id)
    a.status = "closed"; a.closed_by = p.user_id; a.closed_at = utcnow()
    db.commit()
    audit(db, p, object_type="action_item", object_id=a.id, action="close")
    return {"ok": True}


# ── EXCEPTIONS / AUTOMATION ──
@router.post("/exceptions/run-checks")
def run_checks(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq = _active_squadron(p)
    if not sq:
        return {"created": 0}
    today = date.today()
    # clear prior automation items
    db.query(ActionItem).filter(ActionItem.squadron_id == sq, ActionItem.source == "automation",
                                ActionItem.status == "open").delete()
    created = 0
    pns = db.query(ParadeNight).filter(ParadeNight.squadron_id == sq).all()
    for pn in pns:
        try:
            d = datetime.strptime(pn.date, "%Y-%m-%d").date()
        except Exception:
            logging.warning("run_checks: unparsable ParadeNight.date %r on parade_night_id=%s", pn.date, pn.id)
            continue
        days = (d - today).days
        sess = db.query(Session).filter(Session.parade_night_id == pn.id).all()
        for s in sess:
            if 0 <= days <= 7 and not s.facilitator_id and not s.facilitator_display_name_at_time:
                db.add(ActionItem(scope="squadron", squadron_id=sq, wing_id=pn.wing_id,
                                  title="Facilitator needed before parade",
                                  description=f"{pn.date} period {s.period_number} has no facilitator ({days} days out).",
                                  severity="action_required", source="automation", due_date=pn.date)); created += 1
            if 0 <= days <= 3 and not s.training_area_id and not s.training_area_name_at_time:
                db.add(ActionItem(scope="squadron", squadron_id=sq, wing_id=pn.wing_id,
                                  title="Room needed urgently",
                                  description=f"{pn.date} period {s.period_number} has no room ({days} days out).",
                                  severity="command_decision_required", source="automation", due_date=pn.date)); created += 1
    db.commit()
    audit(db, p, object_type="automation", object_id=sq, action="run_checks", new={"created": created})
    return {"created": created}


# ── IMPORT (preview + commit + rollback) ──
class ImportPreviewIn(BaseModel):
    import_type: str = "cadets"
    csv_text: str


class ImportCommitIn(ImportPreviewIn):
    pass


@router.post("/import/preview")
def import_preview(body: ImportPreviewIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    rows = [r for r in csv.reader(io.StringIO(body.csv_text)) if any(c.strip() for c in r)]
    if not rows:
        raise HTTPException(400, detail={"error": "no_rows"})
    headers, data = rows[0], rows[1:]
    # Strip leading = + - @ from cells to neutralise spreadsheet formula injection.
    def safe(v): return ("'" + v) if v[:1] in ("=", "+", "-", "@") else v
    preview = [{h: safe(c) for h, c in zip(headers, r)} for r in data[:50]]
    detected = {f: _guess(headers, n) for f, n in {
        "first_name": ["first", "given"], "last_name": ["last", "surname", "family"],
        "service_number": ["service", "number", "sn"], "rank": ["rank"],
        "attendance_percentage": ["attend", "%"], "phase": ["phase"]}.items()}
    return {"headers": headers, "row_count": len(data), "preview": preview, "detected": detected}


@router.post("/import/commit")
def import_commit(body: ImportCommitIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Commit a cadet import. Records an import log so it can be rolled back."""
    from ..permissions import require_can_write_squadron
    from ..models import Cadet
    sq = _active_squadron(p)
    s = db.get(Squadron, sq)
    require_can_write_squadron(p, s.id, s.wing_id)
    if body.import_type != "cadets":
        raise HTTPException(400, detail={"error": "unsupported_type",
                                         "message": "Only cadet import commit is implemented in this milestone."})
    rows = [r for r in csv.reader(io.StringIO(body.csv_text)) if any(c.strip() for c in r)]
    headers, data = rows[0], rows[1:]
    idx = {h.lower().strip(): i for i, h in enumerate(headers)}
    log = ImportLog(user_id=p.user_id, squadron_id=sq, import_type="cadets", rows_read=len(data))
    db.add(log); db.commit()
    accepted = rejected = 0
    errors = []
    for r in data:
        def g(*names):
            for n in names:
                if n in idx and idx[n] < len(r):
                    return r[idx[n]].strip()
            return ""
        sn = g("service_number", "service number", "sn")
        ln = g("last_name", "last name", "surname")
        if not ln:
            rejected += 1; errors.append("missing last_name"); continue
        att = g("attendance_percentage", "attendance %", "attendance")
        c = Cadet(squadron_id=sq, service_number=sn or None, rank=g("rank") or None,
                  first_name=g("first_name", "first name", "given") or None, last_name=ln,
                  phase=g("phase") or None,
                  attendance_percentage=float(att) if att.replace(".", "", 1).isdigit() else None,
                  created_by=p.user_id)
        # tag for rollback via created_by + import correlation in audit
        db.add(c); accepted += 1
    log.rows_accepted = accepted; log.rows_rejected = rejected
    log.validation_errors = json.dumps(errors[:50]); log.committed = 1
    db.commit()
    audit(db, p, object_type="import", object_id=log.id, action="import",
          new={"type": "cadets", "accepted": accepted, "rejected": rejected})
    return {"ok": True, "import_id": log.id, "accepted": accepted, "rejected": rejected}


@router.post("/import/rollback")
def import_rollback(import_id: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    from ..models import Cadet, CadetClassMembership
    log = db.get(ImportLog, import_id)
    if not log or not log.committed:
        raise HTTPException(404, detail={"error": "not_found_or_not_committed"})
    from ..permissions import require_can_write_squadron
    s = db.get(Squadron, log.squadron_id)
    require_can_write_squadron(p, s.id, s.wing_id)
    # Soft-archive cadets created by this import (correlated by created_by + created_at >= log time).
    cadets = db.query(Cadet).filter(Cadet.squadron_id == log.squadron_id,
                                    Cadet.created_by == log.user_id,
                                    Cadet.created_at >= log.created_at).all()
    cadet_ids = [c.id for c in cadets]
    for c in cadets:
        c.is_archived = True; c.archived_at = utcnow()
    # R5-M17: archive CadetClassMembership rows for rolled-back cadets so they no
    # longer inflate class member counts or appear in planning reports.
    if cadet_ids:
        now = utcnow()
        for m in db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id.in_(cadet_ids),
            CadetClassMembership.is_archived == False,  # noqa: E712
        ).all():
            m.is_archived = True; m.archived_at = now
    log.rollback_status = "rolled_back"; db.commit()
    audit(db, p, object_type="import", object_id=log.id, action="import_rollback",
          new={"archived": len(cadets)})
    return {"ok": True, "archived": len(cadets)}


def _guess(headers, needles):
    for h in headers:
        for n in needles:
            if n.lower() in h.lower():
                return h
    return None


# ── GET /api/recent-changes (HELP-05) ─────────────────────────────────────────
# Activity feed: recent audit-log events scoped to the requesting user's org
# unit (squadron → squadron; wing_admin → all squadrons in their wing;
# national/system_admin → everything within the date window).

_PLANNING_OBJECT_TYPES = {
    "parade_night", "session", "session_audience", "session_outcome",
    "scheduled_session", "planning_notice", "planning_year",
    "training_class", "class_membership",
}

_ACTION_LABELS = {
    "create": "Created",
    "update": "Updated",
    "delete": "Deleted",
    "archive": "Archived",
    "restore": "Restored",
    "record_outcome": "Outcome recorded",
    "cancel": "Cancelled",
    "reschedule": "Rescheduled",
    "publish": "Published",
    "unpublish": "Unpublished",
    "set_audience": "Audience updated",
    "close": "Closed",
}


@router.get("/recent-changes")
def recent_changes(
    days: int = 7,
    limit: int = 50,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Recent audit-log entries for planning objects in the user's org unit.

    Accessible to all authenticated roles; scope is enforced server-side — a
    sqn_admin sees only their squadron, a wing_admin sees their whole wing, and
    national/system roles see everything within the window.
    """
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
    q = (db.query(AuditLog)
         .filter(AuditLog.timestamp >= since,
                 AuditLog.object_type.in_(_PLANNING_OBJECT_TYPES))
         .order_by(AuditLog.timestamp.desc()))

    role = p.role
    sq_id = p.acting_squadron_id or p.squadron_id
    wi_id = p.acting_wing_id or p.wing_id

    if role in ("sqn_admin", "sqn_general"):
        q = q.filter(AuditLog.squadron_id == sq_id)
    elif role in ("wing_admin", "wing_viewer"):
        q = q.filter(AuditLog.wing_id == wi_id)
    # national/auditor/system_admin: no additional filter — full scope

    rows = q.limit(min(limit, 200)).all()
    return {"count": len(rows), "since": since.isoformat(), "changes": [
        {
            "id": e.id,
            "timestamp": iso_z(e.timestamp) if e.timestamp else None,
            "role": e.role,
            "object_type": e.object_type,
            "object_id": e.object_id,
            "action": e.action,
            "label": _ACTION_LABELS.get(e.action, e.action.replace("_", " ").capitalize()),
            "squadron_id": e.squadron_id,
            "wing_id": e.wing_id,
        }
        for e in rows
    ]}
