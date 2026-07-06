"""Import AAFC Learning Hub national curriculum from CSV.

Usage (run from the backend/ directory):

    # Dry run — validates and reports without writing
    python -m scripts.import_national_curriculum_csv --dry-run "/path/to/AAFC Learning Hub.csv"

    # Commit — writes to the database
    python -m scripts.import_national_curriculum_csv "/path/to/AAFC Learning Hub.csv"

DATABASE_URL is read from the environment (defaults to the local SQLite dev DB).

Safety:
  - DATABASE_URL is never printed.
  - No access codes or secrets are logged.
  - All writes run inside a single transaction; any failure rolls back completely.
  - Idempotent: running twice gives 0 created / 0 updated / N skipped on the
    second run (nothing changes if data is identical).

Scope:
  - owning_level  = national
  - wing_id       = NULL
  - squadron_id   = NULL
  - recommended_term = NULL  (term assignment is squadron responsibility)
"""

import argparse
import csv
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── path bootstrap so script runs from backend/ as a module ─────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.database import SessionLocal          # noqa: E402 – after path bootstrap
from app.models import CurriculumElement       # noqa: E402
from app.models.training import CurriculumItem # noqa: E402
from app.models.operations import ImportLog, AuditLog  # noqa: E402

# ── element mapping ──────────────────────────────────────────────────────────
# (CSV display name after normalisation) → (db key, element display_name)
_ELEMENT_MAP: dict[str, tuple[str, str]] = {
    "Service Knowledge":    ("Service_Knowledge", "Service Knowledge"),
    "PDL":                  ("Personal_Dev",      "Personal Development (PDL)"),
    "Drill & Ceremonial":   ("Drill",             "Drill"),
    "Community Engagement": ("Service_Community", "Service & Community"),
    "Field Skills":         ("Field",             "Field Skills"),
    "Air and Space":        ("Air_Space",         "Air & Space"),
    "Aviation":             ("Aviation",          "Aviation"),
    "Cyber":                ("Cyber",             "Cyber"),
    "RPAS":                 ("RPAS",              "RPAS"),
    "Space":                ("Space",             "Space"),
}

# Phase mapping: CSV value (upper) → model phase string
_PHASE_MAP: dict[str, str] = {
    "ORIENTATION":   "A. Orientation",
    "INITIAL":       "B. Initial",
    "JUNIOR":        "C. Junior",
    "INTERMEDIATE":  "D. Intermediate",
    "BRONZE":        "I. Bronze",
    "SILVER":        "J. Silver",
    "GOLD":          "K. Gold",
}

# Foundation/Extension → core_status
# Note: CSV header has typo "Extention" and values may use either spelling.
_CORE_STATUS_MAP: dict[str, str] = {
    "foundation": "core",
    "extension":  "additional",
    "extention":  "additional",   # CSV typo variant
}

# Identifier typos: normalise before any DB lookup
_IDENTIFIER_CORRECTIONS: dict[str, str] = {
    "IN-M02-01": "INT-M02-01",   # "IN-" prefix missing the 'T'
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _normalise_element(raw: str) -> str:
    """Trim whitespace and fix known typos in element names."""
    cleaned = re.sub(r"\s+", " ", raw.strip())
    # Explicit typo: triple-l "Skillls"
    cleaned = re.sub(r"(?i)field\s+skillls", "Field Skills", cleaned)
    return cleaned


def _parse_duration(timing: str) -> tuple[int, str | None]:
    """Return (minutes, warning_or_None). Blank → 60 min with warning."""
    t = timing.strip()
    if not t:
        return 60, "blank Timing — defaulted to 60 min"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*mins?", t, re.IGNORECASE)
    if m:
        return int(float(m.group(1))), None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*hrs?", t, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 60), None
    return 60, f"unrecognised Timing {t!r} — defaulted to 60 min"


def _code_and_part(identifier: str) -> tuple[str, int]:
    """Split 'ORI-M01-02' → ('ORI-M01', 2). Falls back to (identifier, 1)."""
    parts = identifier.rsplit("-", 1)
    if len(parts) == 2:
        try:
            return parts[0], int(parts[1])
        except ValueError:
            pass
    return identifier, 1


def _normalise_location(raw: str) -> str | None:
    """Trim and upper-case; return None if blank."""
    v = raw.strip()
    return v if v else None


# ── CSV row validation ───────────────────────────────────────────────────────

def _validate_row(row: dict, rownum: int) -> tuple[dict | None, list[str]]:
    """Parse and validate a single CSV row.

    Returns (parsed_dict, warnings) on success with possible warnings,
    or (None, errors) on fatal validation failure.
    """
    warnings: list[str] = []
    errors: list[str] = []

    # Required string fields
    identifier_raw = row.get("Experiential Code", "").strip()
    if not identifier_raw:
        errors.append(f"row {rownum}: missing Experiential Code")
        return None, errors

    identifier = _IDENTIFIER_CORRECTIONS.get(identifier_raw, identifier_raw)
    if identifier != identifier_raw:
        warnings.append(f"row {rownum}: identifier corrected {identifier_raw!r} → {identifier!r}")

    title = row.get("Title", "").strip()
    if not title:
        errors.append(f"row {rownum}: missing Title for {identifier}")
        return None, errors

    # Phase
    phase_raw = row.get("Training Phase", "").strip().upper()
    phase = _PHASE_MAP.get(phase_raw)
    if not phase:
        errors.append(f"row {rownum} ({identifier}): unknown Training Phase {phase_raw!r}")
        return None, errors

    # Element
    element_raw = _normalise_element(row.get("Elements", ""))
    element_key, _element_display = _ELEMENT_MAP.get(element_raw, (None, None))
    if not element_key:
        errors.append(f"row {rownum} ({identifier}): unknown element {element_raw!r}")
        return None, errors

    # Core status
    found_ext = row.get("Foundation or Extention", "").strip().lower()
    core_status = _CORE_STATUS_MAP.get(found_ext)
    if not core_status:
        errors.append(f"row {rownum} ({identifier}): unknown Foundation/Extension value {found_ext!r}")
        return None, errors

    # Duration (non-fatal)
    duration, dur_warn = _parse_duration(row.get("Timing", ""))
    if dur_warn:
        warnings.append(f"row {rownum} ({identifier}): {dur_warn}")

    # Other fields
    instructor = row.get("Instructor Suitability", "").strip() or None
    lh_url = row.get("Learning Hub Link", "").strip() or None
    location_type = _normalise_location(row.get("Location", ""))

    code, part_number = _code_and_part(identifier)

    return {
        "identifier":             identifier,
        "code":                   code,
        "part_number":            part_number,
        "title":                  title,
        "phase":                  phase,
        "element":                element_key,
        "element_display":        _ELEMENT_MAP[element_raw][1],
        "duration_minutes":       duration,
        "core_status":            core_status,
        "instructor_suitability": instructor,
        "learning_hub_url":       lh_url,
        "location_type":          location_type,
    }, warnings


# ── element upsert ───────────────────────────────────────────────────────────

def _ensure_elements(db, parsed_rows: list[dict], dry_run: bool) -> dict[str, str]:
    """Ensure all required national curriculum_elements exist.

    Returns a dict of element_key → element.id for existing rows.
    In dry-run mode, nothing is written.
    """
    needed: dict[str, str] = {}   # key → display_name
    for row in parsed_rows:
        needed[row["element"]] = row["element_display"]

    result: dict[str, str] = {}
    now = datetime.now(timezone.utc)

    for key, display in needed.items():
        existing = (
            db.query(CurriculumElement)
            .filter_by(name=key, scope_level="national")
            .first()
        )
        if existing:
            result[key] = existing.id
            print(f"  element: {key!r} already exists — ok")
        else:
            eid = str(uuid.uuid4())
            print(f"  element: {key!r} → {'(dry-run)' if dry_run else 'creating'} '{display}'")
            if not dry_run:
                el = CurriculumElement(
                    id=eid,
                    name=key,
                    display_name=display,
                    scope_level="national",
                    active_status=True,
                    is_archived=False,
                    created_at=now,
                    updated_at=now,
                )
                db.add(el)
                db.flush()
                result[key] = eid
            else:
                result[key] = "(dry-run)"

    return result


# ── curriculum item upsert ───────────────────────────────────────────────────

def _upsert_item(db, parsed: dict, dry_run: bool, now: datetime) -> str:
    """Upsert one curriculum item.  Returns 'created' | 'updated' | 'skipped'."""
    existing: CurriculumItem | None = (
        db.query(CurriculumItem)
        .filter_by(identifier=parsed["identifier"], owning_level="national")
        .first()
    )

    desired = {
        "title":                  parsed["title"],
        "phase":                  parsed["phase"],
        "element":                parsed["element"],
        "duration_minutes":       parsed["duration_minutes"],
        "core_status":            parsed["core_status"],
        "instructor_suitability": parsed["instructor_suitability"],
        "learning_hub_url":       parsed["learning_hub_url"],
        "location_type":          parsed["location_type"],
        "code":                   parsed["code"],
        "part_number":            parsed["part_number"],
    }

    if existing is None:
        if not dry_run:
            item = CurriculumItem(
                id=str(uuid.uuid4()),
                owning_level="national",
                wing_id=None,
                squadron_id=None,
                identifier=parsed["identifier"],
                code=parsed["code"],
                part_number=parsed["part_number"],
                title=parsed["title"],
                phase=parsed["phase"],
                element=parsed["element"],
                duration_minutes=parsed["duration_minutes"],
                part_count=1,
                instructor_suitability=parsed["instructor_suitability"],
                core_status=parsed["core_status"],
                learning_hub_url=parsed["learning_hub_url"],
                location_type=parsed["location_type"],
                recommended_term=None,
                recommended_sequence=0,
                active_status=True,
                is_archived=False,
                created_at=now,
                updated_at=now,
            )
            db.add(item)
        return "created"

    # Item exists — check if any field differs
    changed = any(getattr(existing, k) != v for k, v in desired.items())
    if not changed:
        return "skipped"

    if not dry_run:
        for k, v in desired.items():
            setattr(existing, k, v)
        existing.updated_at = now
    return "updated"


# ── main import logic ────────────────────────────────────────────────────────

def run_import(csv_path: Path, dry_run: bool) -> dict:
    """Run the import.  Returns a stats dict."""
    print(f"\n{'DRY-RUN — ' if dry_run else ''}Importing national curriculum from: {csv_path.name}")
    print("─" * 64)

    # ── 1. read and parse CSV ────────────────────────────────────────────────
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        raw_rows = list(reader)

    rows_read = len(raw_rows)
    print(f"Rows read from CSV: {rows_read}")

    parsed_rows: list[dict] = []
    row_errors: list[str] = []
    all_warnings: list[str] = []

    for i, raw in enumerate(raw_rows, start=2):   # start=2 because row 1 is the header
        result, messages = _validate_row(raw, i)
        if result is None:
            row_errors.extend(messages)
        else:
            parsed_rows.append(result)
            all_warnings.extend(messages)

    rows_failed_validation = len(raw_rows) - len(parsed_rows)

    if all_warnings:
        print(f"\nWarnings ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"  ⚠  {w}")

    if row_errors:
        print(f"\nValidation errors ({len(row_errors)}):")
        for e in row_errors:
            print(f"  ✗  {e}")

    # Check for duplicate identifiers in the CSV itself
    seen: set[str] = set()
    dupes: list[str] = []
    for row in parsed_rows:
        ident = row["identifier"]
        if ident in seen:
            dupes.append(ident)
        seen.add(ident)
    if dupes:
        print(f"\nDuplicate identifiers in CSV (will keep first occurrence): {dupes}")

    print(f"\nRows valid: {len(parsed_rows)} | Invalid: {rows_failed_validation}")

    # ── 2. database operations ───────────────────────────────────────────────
    db = SessionLocal()
    stats = {
        "rows_read":    rows_read,
        "created":      0,
        "updated":      0,
        "skipped":      0,
        "failed":       rows_failed_validation,
        "dry_run":      dry_run,
        "warnings":     all_warnings,
        "errors":       row_errors,
    }

    try:
        print(f"\n{'[DRY-RUN] ' if dry_run else ''}Ensuring national curriculum elements exist:")
        _ensure_elements(db, parsed_rows, dry_run)

        print(f"\n{'[DRY-RUN] ' if dry_run else ''}Processing {len(parsed_rows)} curriculum items:")
        now = datetime.now(timezone.utc)
        deduplicated = {}
        for row in parsed_rows:
            if row["identifier"] not in deduplicated:
                deduplicated[row["identifier"]] = row

        for identifier, row in deduplicated.items():
            outcome = _upsert_item(db, row, dry_run, now)
            stats[outcome] += 1

        # ── 3. audit records ─────────────────────────────────���───────────────
        if not dry_run:
            import_log = ImportLog(
                id=str(uuid.uuid4()),
                user_id=None,         # system / script action
                squadron_id=None,
                import_type="national_curriculum_csv",
                filename=csv_path.name,
                rows_read=rows_read,
                rows_accepted=stats["created"] + stats["updated"],
                rows_rejected=stats["failed"],
                validation_errors=json.dumps(row_errors) if row_errors else None,
                committed=1,
                rollback_status=None,
                created_at=now,
                updated_at=now,
            )
            db.add(import_log)

            audit_entry = AuditLog(
                id=str(uuid.uuid4()),
                timestamp=now,
                user_id=None,
                role="system",
                scope="national",
                object_type="curriculum_item",
                object_id=None,
                action="bulk_import_national_csv",
                new_value=json.dumps({
                    "filename": csv_path.name,
                    "rows_read":  rows_read,
                    "created":    stats["created"],
                    "updated":    stats["updated"],
                    "skipped":    stats["skipped"],
                    "failed":     stats["failed"],
                }),
                reason=f"Script import: {csv_path.name}",
            )
            db.add(audit_entry)

            db.commit()
            print("\nTransaction committed successfully.")
        else:
            db.rollback()
            print("\n[DRY-RUN] No changes written — transaction rolled back.")

    except Exception as exc:
        db.rollback()
        stats["failed"] += 1
        print(f"\nFATAL ERROR — transaction rolled back: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()

    return stats


# ── entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    default_csv = Path(__file__).resolve().parent.parent.parent / "AAFC Learning Hub.csv"
    # Also check Downloads folder
    downloads_csv = Path.home() / "Downloads" / "AAFC Learning Hub.csv"

    parser = argparse.ArgumentParser(
        description="Import AAFC Learning Hub national curriculum CSV into the backend database."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        help="Path to the CSV file (default: searches repo root then ~/Downloads)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without writing to the database",
    )
    args = parser.parse_args()

    if args.csv_path:
        csv_path = Path(args.csv_path)
    elif default_csv.exists():
        csv_path = default_csv
    elif downloads_csv.exists():
        csv_path = downloads_csv
    else:
        print(
            "CSV not found. Provide a path:\n"
            "  python -m scripts.import_national_curriculum_csv --dry-run '/path/to/AAFC Learning Hub.csv'",
            file=sys.stderr,
        )
        sys.exit(1)

    if not csv_path.exists():
        print(f"File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    stats = run_import(csv_path, dry_run=args.dry_run)

    print("\n" + "═" * 64)
    print("IMPORT SUMMARY")
    print("═" * 64)
    print(f"  Mode:        {'DRY-RUN (no changes written)' if stats['dry_run'] else 'COMMITTED'}")
    print(f"  File:        {csv_path.name}")
    print(f"  Rows read:   {stats['rows_read']}")
    print(f"  Created:     {stats['created']}")
    print(f"  Updated:     {stats['updated']}")
    print(f"  Skipped:     {stats['skipped']}")
    print(f"  Failed:      {stats['failed']}")
    if stats["warnings"]:
        print(f"  Warnings:    {len(stats['warnings'])}")
    print("═" * 64)

    if stats["failed"] and not stats["dry_run"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
