"""Training import helpers: facilitator CSV column aliasing and cell
formula-injection neutralisation, rank normalisation, facilitator name
indexing for workbook linking, curriculum duration parsing and Learning Hub
URL segment matching.

Moved verbatim from routers/training.py (stabilisation Phase 3, C5). Pure
string/row processing: no HTTP, no authorization.
"""
from __future__ import annotations


def _lh_last_segment(url: str) -> str:
    """The final non-empty path segment of a URL, ignoring query string and
    trailing slash -- used only to compare against a curriculum item's
    identifier, never to construct/guess a URL."""
    from urllib.parse import urlsplit
    path = urlsplit(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def _normalise_rank(rank: str | None) -> str | None:
    """Strip whitespace; truncate to DB column limit. Does NOT reject non-catalogue values."""
    if rank is None:
        return None
    rank = rank.strip()
    if not rank:
        return None
    return rank[:40]  # matches Facilitator.current_rank String(40)


_FAC_CSV_FIELDS = {
    "rank": ("rank", "current_rank"),
    "first_name": ("first_name", "first name", "firstname", "given name"),
    "last_name": ("last_name", "last name", "lastname", "surname", "family name"),
    "type": ("type", "facilitator type"),
    "subject_areas": ("subject_areas", "subject areas", "subjects"),
    "active_status": ("active_status", "active", "active status"),
}


def _neutralise_csv_cell(v: str) -> str:
    """Strip a leading formula-trigger character (=, +, -, @, tab, CR) so a
    re-exported/opened-in-Excel copy of this data can never execute a
    formula injected via an uploaded CSV cell (CSV/Excel formula injection)."""
    v = (v or "").strip()
    while v and v[0] in "=+-@\t\r":
        v = v[1:].strip()
    return v


def _fac_csv_get(row: dict, key: str) -> str:
    norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
    for alias in _FAC_CSV_FIELDS[key]:
        if alias in norm and norm[alias]:
            return _neutralise_csv_cell(norm[alias])
    return ""


def _facilitator_name_index(facilitators) -> dict[str, str]:
    """Lower-cased name -> facilitator id, for linking workbook rows by name.

    Facilitator has no display_name (reading it crashed every squadron-scoped
    import with 500). Each facilitator is indexed under the codebase's display
    form "rank first last" and under "first last". A key two facilitators share
    is dropped entirely, so an ambiguous name links nobody rather than the
    wrong person.
    """
    index: dict[str, str] = {}
    ambiguous: set[str] = set()
    for f in facilitators:
        names = {" ".join(x for x in [f.current_rank, f.first_name, f.last_name] if x),
                 " ".join(x for x in [f.first_name, f.last_name] if x)}
        for name in names:
            key = name.strip().lower()
            if not key:
                continue
            if key in index and index[key] != f.id:
                ambiguous.add(key)
            index[key] = f.id
    for key in ambiguous:
        index.pop(key, None)
    return index


def _parse_duration(raw: str) -> int:
    """Parse a duration string like '60', '60 min', '1 hr', '1.5 hrs' → minutes."""
    if not raw:
        return 60
    raw = raw.strip().lower()
    import re
    m = re.match(r'(\d+(?:\.\d+)?)\s*(hr|hour|h)', raw)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.match(r'(\d+)', raw)
    if m:
        return int(m.group(1))
    return 60


# Curriculum CSV header -> CurriculumImportItem field. Moved verbatim from
# routers/training.py (2026-10-12, router line ratchet).
_CSV_CURR_COL_MAP = {
    # CSV header (lower-stripped) → CurriculumImportItem field
    "training phase": "phase",
    "phase": "phase",
    "experiential code": "code",
    "code": "code",
    "module code": "code",
    "module_code": "code",
    "title": "title",
    "module title": "title",
    "module_title": "title",
    "elements": "element",
    "element": "element",
    "foundation or extension": "core_status",
    "foundation/extension": "core_status",     # the field's name in the TRGO brief (D17)
    # The Main TMS export's own headers, so export -> CSV -> import is a no-op (D17).
    "identifier": "identifier",
    "part": "part_number",
    "part number": "part_number",
    "core status": "core_status",
    "duration (min)": "duration_minutes",
    "foundation / extension": "core_status",
    "type": "core_status",
    "instructor suitability": "instructor_suitability",
    "instructor_suitability": "instructor_suitability",
    "timing": "duration_minutes",
    "duration": "duration_minutes",
    "duration_min": "duration_minutes",
    "location": "location",
    "learning hub link": "learning_hub_url",
    "learning hub url": "learning_hub_url",
    "url": "learning_hub_url",
}
