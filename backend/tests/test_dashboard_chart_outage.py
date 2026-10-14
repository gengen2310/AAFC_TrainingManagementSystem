"""D20 (2026-10-12): a database outage during /api/dashboard/charts gave 500.

Found in the national-scale failure drill: _safe_chart isolates one broken
chart by catching every exception. During an outage it also swallowed the
first OperationalError, leaving the session in a failed transaction; the
next chart then raised PendingRollbackError, which the outage handler does
not map, so the request ended 500 instead of 503 database_unavailable.
Connectivity errors now propagate; a chart's own bug is still isolated.
"""
import pytest
from sqlalchemy.exc import OperationalError

from app.routers.dashboard import _safe_chart


def test_a_database_outage_is_not_swallowed_by_chart_isolation():
    def builder():
        raise OperationalError("SELECT 1", {}, Exception("server closed the connection"))
    with pytest.raises(OperationalError):
        _safe_chart("class_curriculum_progress", builder)


def test_a_broken_chart_is_still_isolated():
    def builder():
        raise KeyError("a bug in one chart")
    out = _safe_chart("class_curriculum_progress", builder)
    assert out["error"] is True and out["chart_type"] == "error"
