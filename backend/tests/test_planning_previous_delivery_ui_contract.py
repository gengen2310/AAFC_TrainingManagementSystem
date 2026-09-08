"""Planning Workspace previous-delivery warning UI contracts.

A previously delivered curriculum item remains schedulable, but the Training Officer
needs class-aware history context before choosing to repeat it.
"""

from __future__ import annotations

from pathlib import Path

import pytest


DRAWER = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "components"
    / "planning"
    / "PlanningRightDrawer.tsx"
)


def _src() -> str:
    if not DRAWER.exists():
        pytest.skip("PlanningRightDrawer.tsx not present in this checkout")
    return DRAWER.read_text(encoding="utf-8")


def test_previous_delivery_warning_is_non_blocking_and_keeps_repeat_scheduling_available():
    src = _src()
    assert "This lesson has been delivered previously. You can still schedule it again." in src


def test_previous_delivery_warning_offers_lesson_history_navigation():
    src = _src()
    assert "View lesson history" in src, (
        "Previous-delivery warning must give the operator a direct way to inspect all attempts/history"
    )


def test_previous_delivery_display_is_not_raw_date_only_order_when_class_context_exists():
    src = _src()
    assert "prevDeliveries.slice(0, 3)" not in src, (
        "Raw backend date order ignores the selected Training Class. Previous deliveries must be "
        "prioritised with same-class history first before the three-row warning preview is rendered"
    )
