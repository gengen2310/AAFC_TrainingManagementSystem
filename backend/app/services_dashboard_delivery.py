"""Delivery metrics: trends, forecasts, term comparison, weekly outcomes, outcome
distributions, cancellations, and command-level delivery series.

Moved verbatim from routers/dashboard.py (stabilisation, service extraction). Pure
read-side computation: no HTTP, no authorization -- callers resolve scope first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from sqlalchemy.orm import Session as DBSession

from .models import ParadeNight, Session, Squadron
from .services_dashboard_common import (
    _DELIVERED,
    _STATUS_COLORS,
    _TERMINAL,
    _iso_week,
    _unit_pns_and_sessions,
)


def _weekly_outcomes(sessions: list, pns: list) -> dict:
    """Stacked bar: sessions by outcome per parade-night week."""
    pn_map = {pn.id: pn.date for pn in pns}
    weeks: dict[str, dict] = defaultdict(lambda: {
        "label": "", "delivered": 0, "delivered_with_issue": 0,
        "not_delivered": 0, "cancelled": 0, "rescheduled": 0, "planned": 0,
    })
    for s in sessions:
        pn_date = pn_map.get(s.parade_night_id)
        if not pn_date:
            continue
        wk = _iso_week(pn_date)
        bucket = weeks[wk]
        bucket["label"] = wk
        st = s.status or "planned"
        if st in bucket:
            bucket[st] += 1
    data = sorted(weeks.values(), key=lambda r: r["label"])
    total = sum(r["delivered"] + r["delivered_with_issue"] for r in data)
    return {
        "chart_id": "weekly_outcomes",
        "title": "Training delivered each week",
        "explanation": "Sessions delivered, cancelled or not delivered per week.",
        "question": "Are we delivering the planned training program reliably?",
        "chart_type": "stacked_bar",
        "x_axis": "Week",
        "y_axis": "Sessions",
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "delivered_with_issue", "label": "Delivered (with issue)", "color": _STATUS_COLORS["delivered_with_issue"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "rescheduled", "label": "Rescheduled", "color": _STATUS_COLORS["rescheduled"]},
            {"key": "planned", "label": "Planned", "color": _STATUS_COLORS["planned"]},
        ],
        "data": data,
        "insight": f"{total} sessions delivered across {len(data)} weeks." if data else None,
        "empty_state": "No sessions recorded for this period.",
        "drill_down": {"route": "parade-nights", "filters": {}},
        "permission_scope": "squadron",
    }


def _delivery_trend(sessions: list, pns: list, weeks: int = 12) -> dict:
    """Line chart: delivery reliability % for the last N weeks."""
    today = date.today()
    pn_map = {pn.id: pn.date for pn in pns}
    # Build per-week buckets (terminal sessions only)
    wk_buckets: dict[str, dict] = defaultdict(lambda: {"delivered": 0, "total": 0})
    for s in sessions:
        if s.status not in _TERMINAL:
            continue
        pn_date = pn_map.get(s.parade_night_id)
        if not pn_date:
            continue
        d = date.fromisoformat(pn_date)
        if d > today:
            continue  # skip future
        wk = _iso_week(pn_date)
        wk_buckets[wk]["total"] += 1
        if s.status in _DELIVERED:
            wk_buckets[wk]["delivered"] += 1

    # Build the rolling 12-week window (cutoff = 12 weeks ago)
    cutoff = today - timedelta(weeks=weeks)
    def _week_start(wk: str) -> date:
        """Convert 'YYYY-Www' to the Monday of that ISO week."""
        # wk format: "2026-W30"
        year = int(wk[:4])
        week = int(wk[6:])
        # ISO week 1 day 1 of that year
        jan4 = date(year, 1, 4)
        start_of_week1 = jan4 - timedelta(days=jan4.weekday())
        return start_of_week1 + timedelta(weeks=week - 1)

    recent = {k: v for k, v in wk_buckets.items() if _week_start(k) >= cutoff}

    data = []
    for wk in sorted(recent):
        b = recent[wk]
        not_del = b["total"] - b["delivered"]
        pct = round(b["delivered"] / b["total"] * 100) if b["total"] else None
        nd_pct = round(not_del / b["total"] * 100) if b["total"] else None
        data.append({
            "label": wk,
            "reliability_pct": pct,
            "not_delivered_pct": nd_pct,
            "delivered": b["delivered"],
            "not_delivered": not_del,
            "total": b["total"],
            "is_anomaly": False,
        })

    # Anomaly detection: flag weeks with ≥4 sessions where delivery rate
    # drops ≥20 pp below the window average. Min-session threshold avoids
    # flagging a single cancelled session on a quiet night as an anomaly.
    valid = [d for d in data if d["reliability_pct"] is not None]
    anomaly_weeks: list[str] = []
    if len(valid) >= 3:
        avg_pct = sum(v["reliability_pct"] for v in valid) / len(valid)
        for row in data:
            if row["reliability_pct"] is not None and row["total"] >= 4:
                if row["reliability_pct"] < avg_pct - 20:
                    row["is_anomaly"] = True
                    anomaly_weeks.append(row["label"])

    # Insight: trend direction + N/D rate + anomaly summary
    insight = None
    if len(valid) >= 4:
        last4_rel = [v["reliability_pct"] for v in valid[-4:]]
        first4_rel = [v["reliability_pct"] for v in valid[:4]]
        avg_nd = round(sum(v["not_delivered_pct"] or 0 for v in valid[-4:]) / 4)
        if sum(last4_rel) / 4 > sum(first4_rel) / 4 + 5:
            insight = f"Delivery reliability has improved over the past four weeks (non-delivery rate {avg_nd}%)."
        elif sum(last4_rel) / 4 < sum(first4_rel) / 4 - 5:
            insight = f"Delivery reliability has declined recently — non-delivery rate {avg_nd}% over the past four weeks. Review causes."
        elif avg_nd >= 20:
            insight = f"Delivery is stable but the non-delivery rate remains {avg_nd}% — review causes."
    if anomaly_weeks:
        anomaly_note = f"Anomalous weeks detected (delivery ≥20 pp below average): {', '.join(anomaly_weeks)}. Review those parade nights."
        insight = f"{insight} {anomaly_note}".strip() if insight else anomaly_note

    return {
        "chart_id": "delivery_trend",
        "title": "Delivery reliability trend",
        "explanation": "Percentage of scheduled sessions delivered each week over the past 12 weeks.",
        "question": "Is our delivery reliability improving or declining?",
        "chart_type": "line",
        "x_axis": "Week",
        "y_axis": "Reliability %",
        "thresholds": {"green": 80, "amber": 60, "red": 0},
        "data": data,
        "insight": insight,
        "empty_state": "Not enough delivery history to show a trend.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }


_REASON_NOT_RECORDED_LABEL = "Reason not recorded (needs information)"


def _cancellation_reasons(sessions: list, pns: list) -> dict:
    """Ranked bar: most common cancellation / not-delivered reasons.

    A session with no reason recorded is a data-quality gap, not itself an
    operational cause of disruption — it is shown (so the count isn't hidden) but
    is never allowed to be the chart's "most common cause" headline, and is
    labelled/coloured distinctly from a real, named reason."""
    today_str = date.today().isoformat()
    pn_map = {pn.id: pn.date for pn in pns}
    reason_cnt: dict[str, int] = defaultdict(int)

    for s in sessions:
        pn_date = pn_map.get(s.parade_night_id, "")
        if pn_date >= today_str:
            continue
        reason = None
        if s.status == "cancelled":
            reason = (s.cancelled_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        elif s.status == "not_delivered":
            reason = (s.not_delivered_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        if reason:
            # Truncate long free-text to first sentence / 60 chars
            if reason != _REASON_NOT_RECORDED_LABEL:
                reason = reason[:60] + ("…" if len(reason) > 60 else "")
            reason_cnt[reason] += 1

    data = sorted(
        [{"label": r, "count": c,
          "data_quality_gap": r == _REASON_NOT_RECORDED_LABEL,
          "drill_id": "__no_reason__" if r == _REASON_NOT_RECORDED_LABEL else r}
         for r, c in reason_cnt.items()],
        key=lambda x: -x["count"],
    )[:12]  # top 12

    real_data = [d for d in data if not d["data_quality_gap"]]
    missing_count = next((d["count"] for d in data if d["data_quality_gap"]), 0)
    insight = None
    if real_data:
        top = real_data[0]
        insight = f"Most common cause: \"{top['label']}\" ({top['count']} sessions)."
        if missing_count:
            insight += f" ({missing_count} additional session(s) have no reason recorded.)"
    elif missing_count:
        insight = f"{missing_count} cancelled/not-delivered session(s) have no reason recorded yet."

    return {
        "chart_id": "cancellation_reasons",
        "title": "Cancellation and not-delivered reasons",
        "explanation": "Why sessions were not delivered, ranked by frequency.",
        "question": "What is causing the most disruptions to our training program?",
        "chart_type": "bar_horizontal",
        "x_axis": "Sessions",
        "y_axis": "Reason",
        "data": data,
        "insight": insight,
        "empty_state": "No cancellations or not-delivered sessions in this period.",
        "drill_down": {"route": "parade-nights", "filters": {"status": "not_delivered"}},
        "permission_scope": "squadron",
    }


def _session_outcomes_distribution(sessions: list) -> dict:
    """Donut/bar: overall session status distribution for the period."""
    counts = defaultdict(int)
    for s in sessions:
        counts[s.status or "planned"] += 1
    total = sum(counts.values())

    data = [
        {"status": st, "label": lb, "count": counts.get(st, 0),
         "pct": round(counts.get(st, 0) / total * 100) if total else 0,
         "color": _STATUS_COLORS.get(st, "#ccc")}
        for st, lb in [
            ("delivered", "Delivered"),
            ("delivered_with_issue", "Delivered (with issue)"),
            ("not_delivered", "Not Delivered"),
            ("cancelled", "Cancelled"),
            ("rescheduled", "Rescheduled"),
            ("planned", "Planned"),
        ]
    ]
    del_count = counts.get("delivered", 0) + counts.get("delivered_with_issue", 0)
    insight = None
    if total > 0:
        pct = round(del_count / total * 100)
        if pct >= 80:
            insight = f"{pct}% of sessions were delivered — strong program delivery."
        elif pct >= 60:
            insight = f"{pct}% of sessions delivered — some disruption this period."
        else:
            insight = f"Only {pct}% of sessions delivered — review causes of disruption."

    return {
        "chart_id": "session_outcomes",
        "title": "Session outcomes",
        "explanation": "Overall distribution of session outcomes for the selected period.",
        "question": "What proportion of our sessions are being delivered?",
        "chart_type": "donut",
        "data": data,
        "insight": insight,
        "empty_state": "No sessions recorded for this period.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }


def _squadron_delivery_comparison(db: DBSession, wing_id: str, window_start: str, window_end: str) -> dict:
    """Wing: grouped bar comparing squadron session counts by outcome."""
    sqns = db.query(Squadron).filter(
        Squadron.wing_id == wing_id,
        Squadron.is_archived == False,  # noqa: E712
    ).all()

    data = []
    for sqn in sqns:
        pns = db.query(ParadeNight).filter(
            ParadeNight.squadron_id == sqn.id,
            ParadeNight.date >= window_start,
            ParadeNight.date <= window_end,
        ).all()
        pn_ids = [pn.id for pn in pns]
        sessions = db.query(Session).filter(
            Session.parade_night_id.in_(pn_ids),
            Session.is_archived == False,  # noqa: E712
        ).all() if pn_ids else []
        delivered = sum(1 for s in sessions if s.status in _DELIVERED)
        not_del = sum(1 for s in sessions if s.status == "not_delivered")
        cancelled = sum(1 for s in sessions if s.status == "cancelled")
        planned = sum(1 for s in sessions if s.status == "planned")
        data.append({
            "label": sqn.code,
            "name": sqn.short_name,
            "delivered": delivered,
            "not_delivered": not_del,
            "cancelled": cancelled,
            "planned": planned,
        })

    return {
        "chart_id": "squadron_delivery_comparison",
        "title": "Squadron session outcomes comparison",
        "explanation": "Delivered, not delivered and cancelled sessions for each squadron.",
        "question": "How does session delivery compare across squadrons?",
        "chart_type": "grouped_bar",
        "x_axis": "Sessions",
        "y_axis": "Squadron",
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "planned", "label": "Planned", "color": _STATUS_COLORS["planned"]},
        ],
        "data": data,
        "empty_state": "No session data for this period.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "wing",
    }


def _command_weekly_delivered(all_sessions: list, all_pns: list) -> dict:
    """B1 — Training delivered each week, aggregated across the whole scope
    (all subordinate units' sessions combined, counted first — not averaged)."""
    chart = _weekly_outcomes(all_sessions, all_pns)
    chart.update({
        "purpose": "Assess whether the approved training program is being delivered across all subordinate units.",
        "measure": "Sessions by outcome (delivered / delivered with issue / cancelled / not delivered / planned) per week, summed across all subordinate units.",
        "assessment": chart.get("insight") or "No sessions recorded for this period.",
        "action": "Investigate degradation, confirm recovery, or note sustained delivery performance to command.",
    })
    return chart


def _command_reliability_trend(all_sessions: list, all_pns: list) -> dict:
    """B2 — Delivery reliability, 12-week trend, aggregated across scope.
    Thresholds are labelled explicitly, not colour-only."""
    chart = _delivery_trend(all_sessions, all_pns)
    chart.update({
        "purpose": "Assess whether delivery reliability across subordinate units is improving, stable or deteriorating.",
        "measure": "Delivered sessions divided by sessions due for delivery, aggregated across all subordinate units, per week.",
        "assessment": chart.get("insight") or "Not enough delivery history to assess a trend.",
        "action": "Assess whether command action is producing the required effect; escalate if reliability is deteriorating.",
        "threshold_labels": {
            "80": "80% or greater — meeting reference.",
            "60": "60–79% — command attention required.",
            "0": "Below 60% — significant delivery deficiency.",
        },
    })
    return chart


def _outcomes_by_unit(db: DBSession, scope: str, units: list[dict], window_start: str, window_end: str) -> dict:
    """B3 — Session outcomes by subordinate scope, 100%-stacked. Wing view:
    one bar per Squadron. National view: one bar per Wing. Raw counts are
    kept alongside percentages — the denominator is never hidden."""
    rows = []
    for u in units:
        _, sessions = _unit_pns_and_sessions(db, u["kind"], u["id"], window_start, window_end)
        counts = {"delivered": 0, "delivered_with_issue": 0, "cancelled": 0, "not_delivered": 0, "outstanding": 0}
        for s in sessions:
            st = s.status or "planned"
            if st in ("delivered", "delivered_with_issue", "cancelled", "not_delivered"):
                counts[st] += 1
            else:
                counts["outstanding"] += 1
        total = sum(counts.values())
        pct = {k: (round(v / total * 100) if total else 0) for k, v in counts.items()}
        rows.append({"unit_id": u["id"], "label": u["code"], "name": u["name"],
                     "total": total, "counts": counts, "pct": pct})

    unit_noun = "Squadron" if scope == "wing" else "Wing"
    isolated = sum(1 for r in rows if r["total"] and r["pct"]["delivered"] + r["pct"]["delivered_with_issue"] < 60)
    insight = (f"{isolated} of {len(rows)} {unit_noun}s below 60% delivered this period."
               if rows and isolated else ("Delivery performance is consistent across all units." if rows else None))

    return {
        "chart_id": "outcomes_by_unit",
        "title": f"Session outcomes by {unit_noun.lower()}",
        "purpose": "Determine whether reduced delivery performance is isolated to one unit or systemic across the formation.",
        "measure": "Delivered, delivered-with-issue, cancelled, not-delivered and outstanding sessions per unit, shown as a percentage of that unit's own total.",
        "assessment": insight or "No session data for this period.",
        "action": "Determine the appropriate level of command action — local correction for an isolated unit, coordinated action if systemic.",
        "question": "Is reduced delivery performance isolated or systemic?",
        "chart_type": "stacked_bar_horizontal_100",
        "x_axis": "% of sessions",
        "y_axis": unit_noun,
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "delivered_with_issue", "label": "Delivered (with issue)", "color": _STATUS_COLORS["delivered_with_issue"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "outstanding", "label": "Outcome outstanding", "color": "#b0b7bb"},
        ],
        "data": rows,
        "insight": insight,
        "empty_state": "No session data for this period.",
        "drill_down": {"route": "parade-nights",
                       "filters": ({"squadron_id": "{{unit_id}}"} if scope == "wing" else {"wing_id": "{{unit_id}}"})},
    }


def _cancellation_pareto(all_sessions: list) -> dict:
    """B4 — Cancellation and non-delivery causes, aggregated across scope,
    with cumulative percentage (a genuine Pareto chart, not just a ranked bar)."""
    today_str = date.today().isoformat()
    reason_cnt: dict[str, int] = defaultdict(int)
    for s in all_sessions:
        reason = None
        if s.status == "cancelled":
            reason = (s.cancelled_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        elif s.status == "not_delivered":
            reason = (s.not_delivered_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        if reason:
            if reason != _REASON_NOT_RECORDED_LABEL:
                reason = reason[:60] + ("…" if len(reason) > 60 else "")
            reason_cnt[reason] += 1

    ranked = sorted(reason_cnt.items(), key=lambda x: -x[1])[:12]
    total = sum(c for _, c in ranked)
    running = 0
    data = []
    for label, count in ranked:
        running += count
        data.append({
            "label": label, "count": count,
            "data_quality_gap": label == _REASON_NOT_RECORDED_LABEL,
            "drill_id": "__no_reason__" if label == _REASON_NOT_RECORDED_LABEL else label,
            "cumulative_pct": round(running / total * 100) if total else 0,
        })

    real_data = [d for d in data if not d["data_quality_gap"]]
    insight = None
    if real_data:
        insight = f"Most common cause: \"{real_data[0]['label']}\" ({real_data[0]['count']} sessions, {real_data[0]['cumulative_pct']}% cumulative)."
    elif data:
        insight = f"{data[0]['count']} cancelled/not-delivered session(s) have no reason recorded yet."

    return {
        "chart_id": "cancellation_pareto",
        "title": "Cancellation and non-delivery causes",
        "purpose": "Identify which causes account for the majority of failed training across the formation.",
        "measure": "Cancelled and not-delivered sessions grouped by recorded reason, ranked by frequency, with cumulative percentage.",
        "assessment": insight or "No cancellations or non-delivered sessions in this period.",
        "action": "Concentrate command effort on the causes producing the greatest operational effect (the top of the Pareto ranking).",
        "question": "Which causes account for the majority of failed training?",
        "chart_type": "pareto",
        "x_axis": "Reason",
        "y_axis": "Sessions",
        "data": data,
        "insight": insight,
        "empty_state": "No cancellations or not-delivered sessions in this period.",
        "drill_down": {"route": "parade-nights", "filters": {"status": "not_delivered"}},
    }


def _term_comparison_ytd(all_sessions: list, all_pns: list) -> dict:
    """Stat card: YTD delivery rate + current-vs-prior term comparison."""
    today = date.today()
    today_iso = today.isoformat()
    year_prefix = str(today.year) + "-"

    pn_map = {pn.id: (pn.date, pn.term) for pn in all_pns}

    # Bucket terminal sessions by term; track latest PN date per term for ordering.
    term_buckets: dict[str, dict] = {}
    ytd_delivered = 0
    ytd_total = 0

    for s in all_sessions:
        if s.status not in _TERMINAL:
            continue
        info = pn_map.get(s.parade_night_id)
        if not info:
            continue
        pn_date, term = info
        if not pn_date:
            continue

        if pn_date.startswith(year_prefix) and pn_date <= today_iso:
            ytd_total += 1
            if s.status in _DELIVERED:
                ytd_delivered += 1

        if not term:
            continue
        if term not in term_buckets:
            term_buckets[term] = {"delivered": 0, "total": 0, "latest": "0000-00-00"}
        term_buckets[term]["total"] += 1
        if s.status in _DELIVERED:
            term_buckets[term]["delivered"] += 1
        if pn_date > term_buckets[term]["latest"]:
            term_buckets[term]["latest"] = pn_date

    sorted_terms = sorted(term_buckets.items(), key=lambda x: x[1]["latest"], reverse=True)

    def _pct(bucket: dict) -> int | None:
        return round(bucket["delivered"] / bucket["total"] * 100) if bucket["total"] else None

    ytd_pct = round(ytd_delivered / ytd_total * 100) if ytd_total else None
    cur_label = sorted_terms[0][0] if len(sorted_terms) >= 1 else None
    cur_pct = _pct(sorted_terms[0][1]) if len(sorted_terms) >= 1 else None
    prv_label = sorted_terms[1][0] if len(sorted_terms) >= 2 else None
    prv_pct = _pct(sorted_terms[1][1]) if len(sorted_terms) >= 2 else None
    delta = (cur_pct - prv_pct) if (cur_pct is not None and prv_pct is not None) else None

    insight_parts = []
    if ytd_pct is not None:
        insight_parts.append(
            f"Year-to-date delivery rate is {ytd_pct}% "
            f"({ytd_delivered} of {ytd_total} sessions delivered)."
        )
    if delta is not None:
        direction = "up" if delta > 0 else "down" if delta < 0 else "unchanged"
        insight_parts.append(
            f"Delivery is {direction} {abs(delta)} percentage point(s) "
            f"compared to {prv_label}."
        )

    return {
        "chart_id": "term_comparison_ytd",
        "chart_type": "term_comparison_ytd",
        "title": "Delivery — term comparison and year to date",
        "explanation": (
            "Year-to-date delivery reliability and a comparison between the "
            "current and previous training term."
        ),
        "question": "Is delivery improving between terms, and what is this year's overall rate?",
        "data": {
            "ytd_delivered": ytd_delivered,
            "ytd_total": ytd_total,
            "ytd_pct": ytd_pct,
            "current_term": cur_label,
            "current_term_pct": cur_pct,
            "prev_term": prv_label,
            "prev_term_pct": prv_pct,
            "delta_pct": delta,
        },
        "insight": " ".join(insight_parts) if insight_parts else None,
        "empty_state": "Not enough term data to compare. Record training term details on Parade Nights to enable this view.",
        "permission_scope": "squadron",
    }


def _delivery_forecast(all_sessions: list, all_pns: list) -> dict:
    """Stat card: deterministic end-of-year delivery forecast.

    Projects how many remaining planned sessions will be delivered based on
    the year-to-date delivery rate. Fully explainable — no AI or opaque
    scoring. Assumes future rate = historical rate (stated in insight).
    """
    today = date.today()
    today_iso = today.isoformat()
    year_prefix = str(today.year) + "-"
    year_end = f"{today.year}-12-31"

    pn_map = {pn.id: pn.date for pn in all_pns}

    ytd_delivered = 0
    ytd_nd = 0
    remaining_planned = 0

    for s in all_sessions:
        pn_date = pn_map.get(s.parade_night_id)
        if not pn_date:
            continue
        in_year = pn_date.startswith(year_prefix)
        in_past = in_year and pn_date <= today_iso
        in_future = in_year and pn_date > today_iso and pn_date <= year_end

        if in_past and s.status in _TERMINAL:
            if s.status in _DELIVERED:
                ytd_delivered += 1
            else:
                ytd_nd += 1
        elif in_future and s.status == "planned":
            remaining_planned += 1

    ytd_total = ytd_delivered + ytd_nd
    rate = ytd_delivered / ytd_total if ytd_total else None

    projected_delivered = round(remaining_planned * rate) if (rate is not None and remaining_planned > 0) else None
    projected_missed = (remaining_planned - projected_delivered) if projected_delivered is not None else None

    insight_parts = []
    if rate is not None:
        insight_parts.append(f"Year-to-date delivery rate: {round(rate * 100)}%.")
    if projected_delivered is not None:
        insight_parts.append(
            f"At this rate, {projected_delivered} of {remaining_planned} remaining planned sessions "
            f"are expected to be delivered by year end. "
            f"{projected_missed} are at risk of not being delivered."
        )
        insight_parts.append("Forecast assumes the historical rate continues — review if circumstances have changed.")
    elif remaining_planned > 0 and rate is None:
        insight_parts.append(
            f"{remaining_planned} sessions planned for the rest of the year. "
            "No historical delivery data available to forecast against."
        )

    return {
        "chart_id": "delivery_forecast",
        "chart_type": "delivery_forecast",
        "title": "Delivery forecast — end of year",
        "explanation": (
            "Projects remaining planned sessions against the year-to-date delivery rate. "
            "Deterministic: forecast = remaining planned × historical rate. No AI scoring."
        ),
        "question": "At our current rate, how many planned sessions are at risk of not being delivered by year end?",
        "data": {
            "ytd_delivered": ytd_delivered,
            "ytd_not_delivered": ytd_nd,
            "ytd_total_terminal": ytd_total,
            "delivery_rate_pct": round(rate * 100) if rate is not None else None,
            "remaining_planned": remaining_planned,
            "projected_delivered": projected_delivered,
            "projected_missed": projected_missed,
        },
        "insight": " ".join(insight_parts) if insight_parts else None,
        "empty_state": "Not enough data to forecast. Record outcomes on past Parade Nights to enable this view.",
        "permission_scope": "squadron",
    }


def _long_term_delivery_trend(sessions: list, pns: list, terms: int = 4) -> dict:
    """Line: delivery reliability per term (long-range strategic view)."""
    pn_map = {pn.id: (pn.date, pn.term) for pn in pns}
    term_buckets: dict[str, dict] = defaultdict(lambda: {"delivered": 0, "total": 0})
    for s in sessions:
        if s.status not in _TERMINAL:
            continue
        info = pn_map.get(s.parade_night_id)
        if not info:
            continue
        term = info[1] or "Unknown"
        term_buckets[term]["total"] += 1
        if s.status in _DELIVERED:
            term_buckets[term]["delivered"] += 1

    data = [
        {
            "label": term,
            "reliability_pct": round(v["delivered"] / v["total"] * 100) if v["total"] else None,
            "delivered": v["delivered"],
            "total": v["total"],
        }
        for term, v in sorted(term_buckets.items())
    ][-terms * 3:]  # last 3× terms to have some history

    return {
        "chart_id": "long_term_delivery_trend",
        "title": "Long-term delivery trend by term",
        "explanation": "Delivery reliability percentage per training term.",
        "question": "Is our training program becoming more or less reliable over time?",
        "chart_type": "line",
        "x_axis": "Term",
        "y_axis": "Reliability %",
        "thresholds": {"green": 80, "amber": 60, "red": 0},
        "data": data,
        "empty_state": "Not enough multi-term history to show a trend.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }
