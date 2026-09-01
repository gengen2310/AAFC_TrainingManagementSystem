"""CLASS-14: backfill Training Classes from legacy Session.cadet_group / Cadet.phase data.

Design doc: docs/product-review/parallel-class-impact-analysis.md ("Proposed target
shape"), gap register entry CLASS-14 (docs/remediation/master_gap_register.csv).

WHAT THIS DOES
Session.cadet_group and Cadet.phase are free-text strings predating the TrainingClass
model (CLASS-01). This script creates the TrainingClass/SessionAudience/
CadetClassMembership rows those free-text values imply, so existing squadrons'
history becomes visible through the new class-aware UI surfaces without anyone
re-entering it by hand. It NEVER modifies or clears Session.cadet_group or
Cadet.phase -- those stay in place as the read-compatibility path this program's
own capability-preservation rule requires. This is a pure additive backfill.

SAFETY MODEL
- Defaults to --dry-run (report only, zero writes). Real writes require --commit.
- Idempotent: safe to re-run. Re-running with --commit after a prior --commit run
  produces zero new rows (every create is preceded by an existence check).
- Never guesses. Any case this script cannot resolve with certainty (no matching
  PlanningYear, no matching CurriculumPhase, or a squadron that already has its own
  non-migration TrainingClass for that stage/year) is reported as SKIPPED, not
  auto-resolved. See _find_matching_stage and the AMBIGUOUS_EXISTING_CLASS skip
  reason.
- Rows this script creates are tagged for identification and safe rollback:
  TrainingClass/SessionAudience get created_by=MIGRATION_TAG; CadetClassMembership
  gets source=MIGRATION_SOURCE (its own dedicated field for exactly this purpose,
  per CLASS-09's own design).
- --rollback deletes only rows this script created, and refuses (reports, does not
  delete) to remove a migration-created TrainingClass that has since gained a real,
  non-migration SessionAudience or CadetClassMembership link -- that would destroy
  a real user's subsequent work, not just undo this script's own output.

NOT YET AUTHORISED FOR ANY REAL ENVIRONMENT.
Per this program's own capability-preservation and data-safety rules, and per gap
register CLASS-14's own explicit flag ("this is the item most likely to need
explicit user sign-off before execution, given it touches historical training
records across every squadron"), this script must only be run with --commit against
a disposable rehearsal copy of a database until the user has explicitly reviewed a
--dry-run report against the real target (staging or production) and given fresh,
explicit authorisation naming that environment. Running --dry-run is always safe
(zero writes) and does not require this authorisation.

USAGE
    python -m scripts.migrate_legacy_class_data                       # dry-run, all squadrons
    python -m scripts.migrate_legacy_class_data --squadron-id <id>    # dry-run, one squadron
    python -m scripts.migrate_legacy_class_data --commit              # real run, all squadrons
    python -m scripts.migrate_legacy_class_data --rollback --commit   # undo a prior run
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import and_, or_

from app.database import SessionLocal
from app.models import (
    Cadet,
    CadetClassMembership,
    CurriculumPhase,
    ParadeNight,
    PlanningYear,
    Session as TrainingSession,
    SessionAudience,
    Squadron,
    TrainingClass,
)

MIGRATION_TAG = "legacy-migration"
MIGRATION_SOURCE = "legacy_migration"  # CadetClassMembership.source is VARCHAR(20) -- must fit

_PREFIX_RE = re.compile(r"^[a-z]\.\s*")


def _normalize_stage_label(label: str) -> str:
    """'A. Orientation' / 'orientation' / 'Orientation' all normalize to 'orientation'.

    The national CurriculumPhase catalogue uses a letter-dot-space prefix
    convention (confirmed via direct inspection of seeded data: 'A. Orientation'
    .. 'K. Gold'); squadron-scoped custom phases do not follow it. Session.cadet_group
    is lowercase with no prefix; Cadet.phase is Title Case with no prefix. Stripping
    an optional prefix and lowercasing both sides is the one rule that reconciles
    all three conventions without guessing at a fuzzy/partial match.
    """
    return _PREFIX_RE.sub("", label.strip().lower())


@dataclass
class MigrationReport:
    squadron_id: str
    created_classes: list[dict] = field(default_factory=list)
    reused_classes: list[dict] = field(default_factory=list)
    created_audiences: int = 0
    created_memberships: int = 0
    skipped: list[dict] = field(default_factory=list)
    # dry-run only: (training_year_id, training_stage_id) -> True, once this pass
    # has already reported "would create" for that combo. Without this, a second
    # cadet/session sharing the same not-yet-real stage would each independently
    # report their own "would create", double- (or N-times-) counting one class.
    _dry_run_pending: dict = field(default_factory=dict)

    def skip(self, reason: str, **detail):
        self.skipped.append({"reason": reason, **detail})


def _find_matching_stage(db, squadron_id: str, wing_id: str | None, label: str) -> CurriculumPhase | None:
    """Most-specific-scope-wins match: squadron's own phase beats wing beats
    national/system, since a unit's own defined stage represents its actual
    current choice. Returns None (never guesses) if nothing matches exactly."""
    conditions = [CurriculumPhase.scope_level.in_(["national", "system"])]
    if wing_id:
        conditions.append(and_(CurriculumPhase.scope_level == "wing", CurriculumPhase.wing_id == wing_id))
    conditions.append(and_(CurriculumPhase.scope_level == "squadron", CurriculumPhase.squadron_id == squadron_id))
    candidates = db.query(CurriculumPhase).filter(
        CurriculumPhase.is_archived == False,  # noqa: E712
        CurriculumPhase.active_status == True,  # noqa: E712
        or_(*conditions),
    ).all()
    scope_rank = {"squadron": 0, "wing": 1, "national": 2, "system": 2}
    matches = [c for c in candidates if _normalize_stage_label(c.display_name) == label]
    if not matches:
        return None
    matches.sort(key=lambda c: scope_rank.get(c.scope_level, 9))
    return matches[0]


def _find_or_create_class(
    db, report: MigrationReport, *, squadron_id: str, training_year_id: str, stage: CurriculumPhase,
    dry_run: bool,
) -> str | None:
    """Returns the training_class_id to link into, or None if this (squadron,
    year, stage) combo is ambiguous (a real, non-migration class already exists
    for it) and must be left for manual review rather than guessed at.

    In a dry run for a not-yet-existing class, returns a placeholder string
    (truthy, but guaranteed to never match a real training_classes.id) instead
    of a real id -- cached per (training_year_id, stage.id) on the report so a
    second session/cadet sharing the same not-yet-real class reuses the same
    placeholder rather than each independently reporting their own "would
    create" (which would over-count how many classes a real run would make).
    Callers can query for pre-existing SessionAudience/CadetClassMembership
    rows against this placeholder exactly as they would a real id -- since it
    never matches a real row, that query naturally (and correctly) finds none.
    """
    existing = db.query(TrainingClass).filter(
        TrainingClass.squadron_id == squadron_id,
        TrainingClass.training_year_id == training_year_id,
        TrainingClass.training_stage_id == stage.id,
        TrainingClass.is_archived == False,  # noqa: E712
    ).all()
    non_migration = [c for c in existing if c.created_by != MIGRATION_TAG]
    if non_migration:
        report.skip(
            "AMBIGUOUS_EXISTING_CLASS",
            training_year_id=training_year_id, stage=stage.display_name,
            existing_class_ids=[c.id for c in non_migration],
            detail="squadron already has a manually-created Training Class for this "
                   "Stage/Year -- historical sessions/cadets not auto-linked, since "
                   "which class they'd belong to (if the squadron has since split "
                   "into multiple classes for this stage) cannot be inferred safely",
        )
        return None
    migration_created = [c for c in existing if c.created_by == MIGRATION_TAG]
    if migration_created:
        return migration_created[0].id
    key = (training_year_id, stage.id)
    if dry_run:
        if key in report._dry_run_pending:
            return report._dry_run_pending[key]
        placeholder_id = f"<would-create:{key[0]}:{key[1]}>"
        report._dry_run_pending[key] = placeholder_id
        report.created_classes.append({
            "training_year_id": training_year_id, "stage": stage.display_name, "would_create": True,
        })
        return placeholder_id
    existing_nums = {r.class_number for r in db.query(TrainingClass.class_number).filter(
        TrainingClass.squadron_id == squadron_id,
        TrainingClass.training_year_id == training_year_id,
        TrainingClass.is_archived == False,  # noqa: E712
    ).all()}
    n = 1
    while n in existing_nums:
        n += 1
    new_class = TrainingClass(
        squadron_id=squadron_id, training_year_id=training_year_id, training_stage_id=stage.id,
        display_name=stage.display_name.split(". ", 1)[-1] if ". " in stage.display_name else stage.display_name,
        class_number=n, created_by=MIGRATION_TAG, updated_by=MIGRATION_TAG,
    )
    db.add(new_class)
    db.flush()
    report.created_classes.append({
        "training_class_id": new_class.id, "training_year_id": training_year_id, "stage": stage.display_name,
    })
    return new_class.id


def migrate_squadron(db, squadron: Squadron, *, dry_run: bool) -> MigrationReport:
    report = MigrationReport(squadron_id=squadron.id)

    # ── Part 1: Session.cadet_group -> TrainingClass + SessionAudience ──
    rows = (
        db.query(TrainingSession, ParadeNight)
        .join(ParadeNight, ParadeNight.id == TrainingSession.parade_night_id)
        .filter(
            ParadeNight.squadron_id == squadron.id,
            ParadeNight.is_archived == False,  # noqa: E712
            TrainingSession.is_archived == False,  # noqa: E712
            TrainingSession.cadet_group.isnot(None),
        )
        .all()
    )
    # Phase B: ParadeNight now carries planning_year_id as a direct FK instead of
    # the old integer training_year column. Group by the FK directly; the PlanningYear
    # lookup is now a simple pk get rather than a year-number match.
    grouped: dict[tuple[str, str], list[TrainingSession]] = defaultdict(list)
    for sess, pn in rows:
        grouped[(pn.planning_year_id, sess.cadet_group)].append(sess)

    for (planning_year_id, cadet_group), sessions in grouped.items():
        label = _normalize_stage_label(cadet_group)
        py = db.get(PlanningYear, planning_year_id)
        if not py:
            report.skip("NO_MATCHING_PLANNING_YEAR", planning_year_id=planning_year_id, cadet_group=cadet_group,
                        session_count=len(sessions))
            continue
        stage = _find_matching_stage(db, squadron.id, squadron.wing_id, label)
        if not stage:
            report.skip("NO_MATCHING_STAGE", planning_year_id=planning_year_id, cadet_group=cadet_group,
                        session_count=len(sessions))
            continue
        tclass_id = _find_or_create_class(
            db, report, squadron_id=squadron.id, training_year_id=py.id, stage=stage, dry_run=dry_run,
        )
        if tclass_id is None:
            continue
        for sess in sessions:
            already = db.query(SessionAudience).filter(
                SessionAudience.session_id == sess.id, SessionAudience.training_class_id == tclass_id,
            ).first()
            if already:
                continue
            if dry_run:
                report.created_audiences += 1
                continue
            db.add(SessionAudience(session_id=sess.id, training_class_id=tclass_id, created_by=MIGRATION_TAG))
            report.created_audiences += 1

    # ── Part 2: Cadet.phase -> TrainingClass + CadetClassMembership ──
    # Uses the squadron's current ACTIVE PlanningYear, not a historical one --
    # CadetClassMembership is a forward-looking "current standing" lifecycle join
    # (per CLASS-09's own design), not a historical snapshot like Session/
    # SessionAudience above. Only active (non-archived) Cadets are considered --
    # this is an operational-membership backfill, not a historical reconstruction,
    # so an inactive Cadet's stale phase value is left alone.
    active_year = db.query(PlanningYear).filter(
        PlanningYear.unit_id == squadron.id, PlanningYear.active_status == True,  # noqa: E712
    ).order_by(PlanningYear.year.desc()).first()

    cadets = db.query(Cadet).filter(
        Cadet.squadron_id == squadron.id, Cadet.is_archived == False,  # noqa: E712
        Cadet.phase.isnot(None), Cadet.active_status == True,  # noqa: E712
    ).all()
    for cadet in cadets:
        if not active_year:
            report.skip("NO_ACTIVE_PLANNING_YEAR", cadet_id=cadet.id, phase=cadet.phase)
            continue
        label = _normalize_stage_label(cadet.phase)
        stage = _find_matching_stage(db, squadron.id, squadron.wing_id, label)
        if not stage:
            report.skip("NO_MATCHING_STAGE", cadet_id=cadet.id, phase=cadet.phase)
            continue
        tclass_id = _find_or_create_class(
            db, report, squadron_id=squadron.id, training_year_id=active_year.id, stage=stage, dry_run=dry_run,
        )
        if tclass_id is None:
            continue
        already = db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id == cadet.id, CadetClassMembership.training_class_id == tclass_id,
            CadetClassMembership.active_status == True,  # noqa: E712
            CadetClassMembership.is_archived == False,  # noqa: E712
        ).first()
        if already:
            continue
        if dry_run:
            report.created_memberships += 1
            continue
        db.add(CadetClassMembership(
            cadet_id=cadet.id, training_class_id=tclass_id, active_status=True, source=MIGRATION_SOURCE,
        ))
        report.created_memberships += 1

    return report


def run(*, squadron_id: str | None, dry_run: bool) -> list[MigrationReport]:
    db = SessionLocal()
    try:
        q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
        if squadron_id:
            q = q.filter(Squadron.id == squadron_id)
        squadrons = q.all()
        reports = [migrate_squadron(db, sqn, dry_run=dry_run) for sqn in squadrons]
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return reports
    finally:
        db.close()


def rollback(*, squadron_id: str | None, dry_run: bool) -> dict:
    """Removes only rows this script created. Refuses (reports, does not delete)
    to touch a migration-created TrainingClass that has since gained a real,
    non-migration SessionAudience or CadetClassMembership link."""
    db = SessionLocal()
    result = {"deleted_classes": [], "deleted_audiences": 0, "deleted_memberships": 0, "refused": []}
    try:
        q = db.query(TrainingClass).filter(
            TrainingClass.created_by == MIGRATION_TAG, TrainingClass.is_archived == False,  # noqa: E712
        )
        if squadron_id:
            q = q.filter(TrainingClass.squadron_id == squadron_id)
        for tclass in q.all():
            audiences = db.query(SessionAudience).filter(SessionAudience.training_class_id == tclass.id).all()
            memberships = db.query(CadetClassMembership).filter(
                CadetClassMembership.training_class_id == tclass.id,
            ).all()
            foreign_audiences = [a for a in audiences if a.created_by != MIGRATION_TAG]
            foreign_memberships = [m for m in memberships if m.source != MIGRATION_SOURCE]
            if foreign_audiences or foreign_memberships:
                result["refused"].append({
                    "training_class_id": tclass.id, "display_name": tclass.display_name,
                    "foreign_audience_count": len(foreign_audiences),
                    "foreign_membership_count": len(foreign_memberships),
                })
                continue
            result["deleted_classes"].append({"training_class_id": tclass.id, "display_name": tclass.display_name})
            result["deleted_audiences"] += len(audiences)
            result["deleted_memberships"] += len(memberships)
            if not dry_run:
                for a in audiences:
                    db.delete(a)
                for m in memberships:
                    db.delete(m)
                db.delete(tclass)
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return result
    finally:
        db.close()


def _print_report(reports: list[MigrationReport], dry_run: bool) -> None:
    verb = "Would create" if dry_run else "Created"
    total_classes = sum(len(r.created_classes) for r in reports)
    total_audiences = sum(r.created_audiences for r in reports)
    total_memberships = sum(r.created_memberships for r in reports)
    total_skipped = sum(len(r.skipped) for r in reports)
    print(f"Squadrons processed: {len(reports)}")
    print(f"{verb} {total_classes} TrainingClass row(s), {total_audiences} SessionAudience row(s), "
          f"{total_memberships} CadetClassMembership row(s).")
    print(f"Skipped {total_skipped} case(s) (reported, not guessed):")
    reason_counts: dict[str, int] = defaultdict(int)
    for r in reports:
        for s in r.skipped:
            reason_counts[s["reason"]] += 1
    for reason, count in sorted(reason_counts.items()):
        print(f"  {reason}: {count}")
    if dry_run:
        print("\nDRY RUN -- no writes made. Re-run with --commit to apply.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--squadron-id", default=None, help="Limit to one squadron (default: all squadrons).")
    parser.add_argument("--commit", action="store_true", help="Actually write. Default is dry-run (report only).")
    parser.add_argument("--rollback", action="store_true", help="Undo a prior --commit run instead of migrating.")
    args = parser.parse_args()

    dry_run = not args.commit
    if args.rollback:
        result = rollback(squadron_id=args.squadron_id, dry_run=dry_run)
        verb = "Would delete" if dry_run else "Deleted"
        print(f"{verb} {len(result['deleted_classes'])} TrainingClass row(s) "
              f"({result['deleted_audiences']} SessionAudience, {result['deleted_memberships']} "
              f"CadetClassMembership).")
        if result["refused"]:
            print(f"Refused to delete {len(result['refused'])} class(es) with non-migration links since created:")
            for r in result["refused"]:
                print(f"  {r['training_class_id']} ({r['display_name']}): "
                      f"{r['foreign_audience_count']} foreign audience row(s), "
                      f"{r['foreign_membership_count']} foreign membership row(s)")
        if dry_run:
            print("\nDRY RUN -- no writes made. Re-run with --rollback --commit to apply.")
        return 0

    reports = run(squadron_id=args.squadron_id, dry_run=dry_run)
    _print_report(reports, dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
