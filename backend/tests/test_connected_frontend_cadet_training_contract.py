"""Static Main TMS UI contracts for Cadet Rosters and Training Records.

The connected frontend is intentionally a single-file SPA, so these focused source
checks are a cheap guard for workflow regressions that backend tests cannot see.
They do not prescribe styling; they lock the user-visible behaviours from the
remediation brief.
"""

from __future__ import annotations

from pathlib import Path

import pytest


HTML = Path(__file__).resolve().parents[2] / "connected-frontend" / "index.html"


def _html() -> str:
    if not HTML.exists():
        pytest.skip("connected-frontend/index.html not present in this checkout")
    return HTML.read_text(encoding="utf-8")


def _slice(src: str, start: str, end: str | None = None, *, limit: int = 12000) -> str:
    pos = src.find(start)
    assert pos >= 0, f"missing frontend source marker: {start}"
    if end:
        end_pos = src.find(end, pos + len(start))
        if end_pos >= 0:
            return src[pos:end_pos]
    return src[pos:pos + limit]


def test_roster_uses_cea_number_label_not_legacy_service_number_label():
    src = _html()
    roster = _slice(src, "async function loadCadetRoster()", "async function removeCadetFromClass")
    assert "CEA Number" in roster, "Roster identity column must be labelled CEA Number"
    assert "<th>Service #</th>" not in roster, "Legacy Service # label must not remain in the roster"


def test_roster_has_checkbox_selection_for_bulk_actions():
    src = _html()
    roster = _slice(src, "async function loadCadetRoster()", "async function removeCadetFromClass")
    assert 'type="checkbox"' in roster or "type='checkbox'" in roster, (
        "Cadet roster must be spreadsheet-like with row selection checkboxes for bulk actions"
    )


def test_roster_exposes_distinct_add_to_class_and_remove_from_class_actions():
    src = _html()
    roster = _slice(src, "async function loadCadetRoster()", "function openAddCadetModal")
    assert "Add to Class" in roster, "Concurrent membership needs an explicit Add to Class action"
    assert "Remove from Class" in roster, "Membership lifecycle action must say Remove from Class"


def test_move_to_class_uses_one_atomic_backend_move_not_remove_then_add():
    src = _html()
    move = _slice(src, "async function moveCadetsToClass", "function openAddCadetModal")
    assert "target_class_id" in move, "Move to Class must send the selected target class to the canonical move endpoint"
    assert "action:'move'" in move or 'action:"move"' in move or '"action":"move"' in move, (
        "Move to Class must call bulk-membership action=move so validation/history are atomic"
    )
    assert not ("action:'remove'" in move and "action:'add'" in move), (
        "Move to Class must not remove the source membership and then separately add the target; "
        "an add failure would strand the Cadet"
    )


def test_add_cadet_button_is_not_an_alias_for_add_existing_membership_prompt():
    src = _html()
    add = _slice(src, "function openAddCadetModal", "// ═══════════════════════════════════════════════════════════\n// TRAINING RECORDS")
    assert "bulkAddCadetsToClass(classId)" not in add, (
        "Add Cadet must open/create a Cadet record workflow; it must not merely alias the "
        "existing-Cadet Add to Class prompt"
    )


def test_roster_does_not_duplicate_central_cea_import_controls():
    src = _html()
    roster_page = _slice(src, '<div id="page-cadets" class="page">', '<div id="page-training-records" class="page">')
    assert "Import CSV" not in roster_page
    assert "Download CSV Template" not in roster_page


def test_individual_training_record_shows_cea_number_and_memberships():
    src = _html()
    detail = _slice(src, "async function showCadetTrainingRecord", "async function exportTrainingRecords")
    assert "service_number" in detail, "Individual Training Record must display the Cadet's CEA number"
    assert "memberships" in detail, "Individual Training Record must display current/historical class membership context"


def test_individual_training_record_renders_attempt_history_not_summary_only():
    src = _html()
    detail = _slice(src, "async function showCadetTrainingRecord", "async function exportTrainingRecords")
    assert "attempts" in detail, (
        "Each curriculum item in the individual Training Record must expose all delivery attempts/outcomes, "
        "not only the summary completion date"
    )
