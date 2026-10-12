"""Planning spreadsheet I/O helpers: Annual Program import parsing (dates,
times, parade-night rows, unit matching, CSV/XLSX decoding), CEA export row
normalisation, and formula-injection neutralisation for exported cells.

Moved verbatim from routers/planning.py (stabilisation Phase 3, C5). Pure
parsing over bytes, strings and already-loaded rows: no HTTP, no authorization.
"""
from __future__ import annotations

import csv as _csv, io, re
import json as _json
from datetime import date

from .models import Squadron


_PROG_DATE_FMTS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y"]


def _parse_prog_date(raw: str) -> str | None:
    """Parse a date string to ISO YYYY-MM-DD."""
    if not raw:
        return None
    from datetime import datetime
    for fmt in _PROG_DATE_FMTS:
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw.strip()[:10] or None


def _parse_prog_time(raw: str) -> str | None:
    """Normalise a time string to HH:MM."""
    if not raw:
        return None
    raw = raw.strip()
    parts = raw.split(":")
    if len(parts) >= 2:
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except ValueError:
            pass
    return raw[:5] or None


_PARADE_KWORDS = ("parade night", "training night", "parade ngt", "parade nt")


def _is_parade_row(name: str) -> bool:
    n = name.strip().lower()
    return any(kw in n for kw in _PARADE_KWORDS)


def _resolve_unit_sqn(unit_str: str, all_sqns: list) -> "Squadron | None":
    """Match a Unit column value to a Squadron by code or number prefix."""
    if not unit_str:
        return None
    u_up = unit_str.strip().upper()
    for sq in all_sqns:
        if sq.code and sq.code.strip().upper() == u_up:
            return sq
    m = re.match(r'^(\d+)', unit_str.strip())
    if m:
        num = m.group(1)
        for sq in all_sqns:
            if sq.code and re.match(r'^' + re.escape(num) + r'\b', sq.code.strip()):
                return sq
    u_lo = unit_str.strip().lower()
    for sq in all_sqns:
        if sq.name and u_lo in sq.name.lower():
            return sq
    return None


def _parse_program_file(content: bytes, is_xlsx: bool) -> list[dict]:
    """Decode CSV or XLSX bytes into a list of {header: value} dicts."""
    if is_xlsx:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        header_row = next(rows_iter, None)
        if not header_row:
            return []
        headers = [str(c).strip() if c is not None else "" for c in header_row]
        result = []
        for row in rows_iter:
            if all(v is None for v in row):
                continue
            result.append({h: (str(v) if v is not None else "") for h, v in zip(headers, row)})
        return result
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    reader = _csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _neutralise_cell(v):
    """Prevent CSV/formula injection in spreadsheet cells."""
    s = str(v) if v is not None else ""
    return ("'" + s) if s[:1] in ("=", "+", "-", "@") else s


def _parse_cea_date(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10] if len(raw) >= 10 else raw


def _parse_cea_time(raw: str | None) -> str | None:
    """HH:MM (24 h) from '9:30', '09:30', '09:30:00' or '9:30 AM'; None when
    absent or not a real time (the import reports that row, D18). The old
    rule kept the first five characters of anything with a colon, so '25:99'
    was stored and '9:30' was dropped."""
    if not raw:
        return None
    from datetime import datetime as _dt
    raw = raw.strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I:%M:%S %p"):
        try:
            return _dt.strptime(raw.upper(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None


_CEA_DATE_FIELDS = (("activity_start_date", ("StartDate", "Start date"), "StartDate"),
                    ("activity_end_date", ("EndDate", "End date"), "EndDate"),
                    ("nomination_start_date", ("NominationStartDate",), "NominationStartDate"),
                    ("nomination_end_date", ("NominationEndDate",), "NominationEndDate"))
_CEA_TIME_FIELDS = (("start_time", ("StartTime", "Start time"), "StartTime"),
                    ("end_time", ("EndTime", "End time"), "EndTime"))


def cea_row_problems(row: dict, parsed: dict) -> list[tuple[str, str]]:
    """(field, message) for each value in a CEA row that cannot be stored as
    given (D18). A present value that does not parse is a problem; an absent
    optional value is not. Pure: no database access."""
    from datetime import date as _date

    def raw(keys):
        for k in keys:
            v = (row.get(k) or "").strip()
            if v:
                return v
        return None

    problems = []
    if not parsed.get("activity_name"):
        problems.append(("Name", "has no activity name"))
    for field, keys, label in _CEA_DATE_FIELDS:
        value = raw(keys)
        if value is None:
            continue
        iso = parsed.get(field) or ""
        try:
            _date.fromisoformat(iso)
        except ValueError:
            problems.append((label, f"'{value}' is not a date (use DD/MM/YYYY)"))
    for field, keys, label in _CEA_TIME_FIELDS:
        value = raw(keys)
        if value is not None and not parsed.get(field):
            problems.append((label, f"'{value}' is not a time (use HH:MM, 24-hour)"))
    return problems


def _normalise_cea_row(row: dict) -> dict:
    """Map both full-export and simple-export CSV column names to internal fields."""
    def g(*keys: str) -> str | None:
        for k in keys:
            v = row.get(k, "").strip()
            if v:
                return v
        return None

    return {
        "cea_activity_id": g("ActivityID", "SeqNr"),
        "activity_type": g("ActivityTypeName", "SupportRequestType"),
        "status_name": g("StatusName"),
        "parent_unit": g("UnitParentName"),
        "host_unit": g("UnitName", "Unit"),
        "activity_name": g("SeqNrAndName", "Name", "ActivityName"),
        "nomination_start_date": _parse_cea_date(g("NominationStartDate")),
        "nomination_end_date": _parse_cea_date(g("NominationEndDate")),
        "activity_start_date": _parse_cea_date(g("StartDate", "Start date")),
        "activity_end_date": _parse_cea_date(g("EndDate", "End date")),
        "start_time": _parse_cea_time(g("StartTime", "Start time")),
        "end_time": _parse_cea_time(g("EndTime", "End time")),
        "location": g("Location"),
        "activity_poc": g("POC"),
        "notes": g("ActivityNotes", "Activity Notes", "SupportRequestTypeCode"),
    }


def cea_row_is_blank(row: dict) -> bool:
    """An all-empty CSV line (Excel pads exports with them): skipped silently (D18)."""
    return not any((v or "").strip() for v in row.values() if isinstance(v, str))


def cea_row_error_entries(row_number: int, problems: list[tuple[str, str]]) -> list[dict]:
    """The response's row_errors entries for one refused row (D18)."""
    return [{"row": row_number, "field": field,
             "message": f"Row {row_number}: {field} {message} — row not imported."}
            for field, message in problems]


# Moved verbatim from routers/planning.py (2026-10-12, router line ratchet).
def _parse_json_list(val) -> list:
    """Return val as a list, JSON-parsing it if stored as a TEXT string (Postgres TEXT vs JSON/JSONB mismatch)."""
    if not val:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            result = _json.loads(val)
            return result if isinstance(result, list) else []
        except (_json.JSONDecodeError, TypeError):
            return []
    return []


def _validate_iso_date(v: str, field_name: str) -> str:
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValueError(f"{field_name} must be a valid ISO-8601 date (YYYY-MM-DD), got '{v}'")
    return v
