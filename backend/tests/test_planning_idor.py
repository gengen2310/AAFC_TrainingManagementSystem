"""Regression tests for IDOR fixes in planning router.

Covers:
  IDOR-001: CEA endpoints missing _require_year_access()
  IDOR-002: Notice endpoints missing parade-date ownership check
  IDOR-003: Facilitator leave endpoints missing squadron scope check
  MISS-001: CEA CSV import missing file-size guard

Each test verifies that:
  (a) a legitimate owner can perform the operation
  (b) a different-squadron admin is rejected (403 or 404)
  (c) unauthenticated requests are rejected (401)
  (d) read-only roles are rejected on write operations (403)
"""
import io
import pytest
from tests.conftest import login


# ─── helpers ──────────────────────────────────────────────────────────────────

def _hdr(client, code):
    return login(client, code)


def _make_year(client, hdr, year=2099, name="IDOR Test Year"):
    r = client.post("/api/planning/years", json={"year": year, "name": name}, headers=hdr)
    assert r.status_code == 200, f"year creation failed: {r.text}"
    return r.json()["planning_year_id"]


def _add_parade_date(client, hdr, year_id, date="2099-05-02"):
    r = client.post(
        f"/api/planning/years/{year_id}/parade-dates",
        json={"parade_date": date, "parade_type": "standard"},
        headers=hdr,
    )
    assert r.status_code == 200, f"parade date creation failed: {r.text}"
    return r.json()["parade_date_id"]


def _create_manual_activity(client, hdr, year_id, name="IDOR Test Activity"):
    r = client.post(
        f"/api/planning/years/{year_id}/cea/activities",
        json={"activity_name": name, "activity_start_date": "2099-07-01"},
        headers=hdr,
    )
    assert r.status_code == 200, f"activity creation failed: {r.text}"
    return r.json()["id"]


def _create_notice(client, hdr, date_id, text="IDOR Test Notice"):
    r = client.post(
        f"/api/planning/parade-dates/{date_id}/notices",
        json={"notice_text": text, "priority": "normal"},
        headers=hdr,
    )
    assert r.status_code == 200, f"notice creation failed: {r.text}"
    return r.json()["notice_id"]


# ─── IDOR-001: CEA endpoints ──────────────────────────────────────────────────

class TestCEAListActivitiesScoping:
    """list_cea_activities must enforce year scope."""

    def test_owner_can_list_own_cea_activities(self, client):
        hdr = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr)
        _create_manual_activity(client, hdr, year_id)
        r = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr)
        assert r.status_code == 200
        assert isinstance(r.json()["activities"], list)

    def test_different_sqn_admin_blocked_from_cea_activities(self, client):
        # 703 admin creates a year; 704 admin tries to access it
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_704 = _hdr(client, "ADMIN704")
        year_id = _make_year(client, hdr_703)
        r = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr_704)
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_unauthenticated_cea_activities_rejected(self, client):
        # No login in this test — fresh client has no token or cookie
        r = client.get("/api/planning/years/00000000-0000-0000-0000-000000000001/cea/activities")
        assert r.status_code == 401

    def test_sqn_general_cannot_list_cea_activities(self, client):
        hdr_gen = _hdr(client, "703SQN2026")
        hdr_adm = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr_adm)
        r = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr_gen)
        assert r.status_code == 403


class TestCEAListBatchesScoping:
    """list_cea_batches must enforce year scope."""

    def test_owner_can_list_own_batches(self, client):
        hdr = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr)
        r = client.get(f"/api/planning/years/{year_id}/cea/batches", headers=hdr)
        assert r.status_code == 200
        assert "batches" in r.json()

    def test_different_sqn_admin_blocked_from_batches(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_704 = _hdr(client, "ADMIN704")
        year_id = _make_year(client, hdr_703)
        r = client.get(f"/api/planning/years/{year_id}/cea/batches", headers=hdr_704)
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_unauthenticated_batches_rejected(self, client):
        r = client.get("/api/planning/years/00000000-0000-0000-0000-000000000002/cea/batches")
        assert r.status_code == 401


class TestCreateManualActivityScoping:
    """create_manual_activity must enforce year scope."""

    def test_owner_can_create_manual_activity(self, client):
        hdr = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr)
        r = client.post(
            f"/api/planning/years/{year_id}/cea/activities",
            json={"activity_name": "Own activity", "activity_start_date": "2099-08-01"},
            headers=hdr,
        )
        assert r.status_code == 200

    def test_different_sqn_admin_cannot_create_in_foreign_year(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_704 = _hdr(client, "ADMIN704")
        year_id = _make_year(client, hdr_703)
        r = client.post(
            f"/api/planning/years/{year_id}/cea/activities",
            json={"activity_name": "Sneaky activity", "activity_start_date": "2099-08-01"},
            headers=hdr_704,
        )
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_sqn_general_cannot_create_manual_activity(self, client):
        hdr_gen = _hdr(client, "703SQN2026")
        hdr_adm = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr_adm)
        r = client.post(
            f"/api/planning/years/{year_id}/cea/activities",
            json={"activity_name": "Blocked", "activity_start_date": "2099-08-01"},
            headers=hdr_gen,
        )
        assert r.status_code == 403


class TestClassifyCEAActivityScoping:
    """classify_cea_activity must enforce the activity's year scope."""

    def test_owner_can_classify_own_activity(self, client):
        hdr = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr)
        activity_id = _create_manual_activity(client, hdr, year_id)
        r = client.patch(
            f"/api/planning/cea/{activity_id}/classify",
            json={"importance": "key_event"},
            headers=hdr,
        )
        assert r.status_code == 200

    def test_different_sqn_admin_cannot_classify_foreign_activity(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_704 = _hdr(client, "ADMIN704")
        year_id = _make_year(client, hdr_703)
        activity_id = _create_manual_activity(client, hdr_703, year_id)
        r = client.patch(
            f"/api/planning/cea/{activity_id}/classify",
            json={"importance": "must_attend"},
            headers=hdr_704,
        )
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_unauthenticated_classify_rejected(self, client):
        r = client.patch(
            "/api/planning/cea/00000000-0000-0000-0000-000000000003/classify",
            json={"importance": "key_event"},
        )
        assert r.status_code == 401


class TestLocalHideScoping:
    """set_local_hide must enforce the activity's year scope."""

    def test_owner_can_set_local_hide(self, client):
        hdr = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr)
        activity_id = _create_manual_activity(client, hdr, year_id)
        r = client.post(
            f"/api/planning/cea/{activity_id}/local-hide",
            json={"is_hidden": True, "local_note": "Test hide"},
            headers=hdr,
        )
        assert r.status_code == 200

    def test_different_sqn_admin_cannot_hide_foreign_activity(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_704 = _hdr(client, "ADMIN704")
        year_id = _make_year(client, hdr_703)
        activity_id = _create_manual_activity(client, hdr_703, year_id)
        r = client.post(
            f"/api/planning/cea/{activity_id}/local-hide",
            json={"is_hidden": True},
            headers=hdr_704,
        )
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"


# ─── IDOR-002: Notice endpoints ───────────────────────────────────────────────

class TestNoticeScoping:
    """Notice endpoints must enforce parade-date ownership."""

    def _setup(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr_703)
        date_id = _add_parade_date(client, hdr_703, year_id)
        notice_id = _create_notice(client, hdr_703, date_id)
        return hdr_703, year_id, date_id, notice_id

    def test_owner_can_list_notices(self, client):
        hdr_703, _, date_id, _ = self._setup(client)
        r = client.get(f"/api/planning/parade-dates/{date_id}/notices", headers=hdr_703)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_different_sqn_admin_cannot_list_notices(self, client):
        hdr_703, _, date_id, _ = self._setup(client)
        hdr_704 = _hdr(client, "ADMIN704")
        r = client.get(f"/api/planning/parade-dates/{date_id}/notices", headers=hdr_704)
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_owner_can_create_notice(self, client):
        hdr_703, _, date_id, _ = self._setup(client)
        r = client.post(
            f"/api/planning/parade-dates/{date_id}/notices",
            json={"notice_text": "Second notice"},
            headers=hdr_703,
        )
        assert r.status_code == 200

    def test_different_sqn_admin_cannot_create_notice(self, client):
        hdr_703, _, date_id, _ = self._setup(client)
        hdr_704 = _hdr(client, "ADMIN704")
        r = client.post(
            f"/api/planning/parade-dates/{date_id}/notices",
            json={"notice_text": "Foreign notice"},
            headers=hdr_704,
        )
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_owner_can_update_notice(self, client):
        hdr_703, _, _, notice_id = self._setup(client)
        r = client.patch(
            f"/api/planning/notices/{notice_id}",
            json={"notice_text": "Updated text"},
            headers=hdr_703,
        )
        assert r.status_code == 200

    def test_different_sqn_admin_cannot_update_notice(self, client):
        hdr_703, _, _, notice_id = self._setup(client)
        hdr_704 = _hdr(client, "ADMIN704")
        r = client.patch(
            f"/api/planning/notices/{notice_id}",
            json={"notice_text": "Tampered"},
            headers=hdr_704,
        )
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_owner_can_archive_notice(self, client):
        hdr_703, _, _, notice_id = self._setup(client)
        r = client.post(f"/api/planning/notices/{notice_id}/archive", headers=hdr_703)
        assert r.status_code == 200

    def test_different_sqn_admin_cannot_archive_notice(self, client):
        _, _, _, notice_id = self._setup(client)
        hdr_704 = _hdr(client, "ADMIN704")
        r = client.post(f"/api/planning/notices/{notice_id}/archive", headers=hdr_704)
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_unauthenticated_notice_list_rejected(self, client):
        r = client.get("/api/planning/parade-dates/00000000-0000-0000-0000-000000000004/notices")
        assert r.status_code == 401

    def test_sqn_general_cannot_create_notice(self, client):
        _, _, date_id, _ = self._setup(client)
        hdr_gen = _hdr(client, "703SQN2026")
        r = client.post(
            f"/api/planning/parade-dates/{date_id}/notices",
            json={"notice_text": "Readonly notice"},
            headers=hdr_gen,
        )
        assert r.status_code == 403


# ─── IDOR-003: Facilitator leave ─────────────────────────────────────────────

class TestFacilitatorLeaveScoping:
    """Facilitator leave endpoints must enforce squadron ownership."""

    def _get_703_facilitator_id(self, client):
        hdr = _hdr(client, "ADMIN703")
        r = client.get("/api/planning/facilitators", headers=hdr)
        assert r.status_code == 200
        facs = r.json()
        assert len(facs) > 0, "Expected seeded facilitators for 703"
        return facs[0]["facilitator_id"]

    def test_sqn_admin_only_sees_own_squadron_facilitators(self, client):
        """GET /api/planning/facilitators must resolve scope via the same
        _view_squadron_id() every other resource endpoint uses -- previously
        this endpoint had its own bespoke role filter with no national_admin/
        system_admin branch at all (silently unfiltered), so a squadron
        admin's own list here could disagree with what /api/facilitators
        (training.py) shows for the same squadron."""
        hdr703 = _hdr(client, "ADMIN703")
        facs = client.get("/api/planning/facilitators", headers=hdr703).json()
        assert facs, "Expected seeded facilitators for 703"
        assert all(f["unit_id"] == facs[0]["unit_id"] for f in facs)

    def test_national_admin_sees_empty_list_without_explicit_squadron(self, client):
        """Previously national_admin/system_admin hit no role branch at all in
        this endpoint's old bespoke filter, so the query stayed completely
        unfiltered and returned every facilitator in the system. Viewing a
        specific squadron's facilitators as national_admin now requires an
        explicit, permission-checked unit_id -- same as every other resource
        endpoint -- not an accidental full dump."""
        hdr_nat = _hdr(client, "ADMINNATIONAL")
        r = client.get("/api/planning/facilitators", headers=hdr_nat)
        assert r.status_code == 200
        assert r.json() == []

    def test_national_admin_can_view_explicit_squadron_facilitators(self, client):
        hdr_nat = _hdr(client, "ADMINNATIONAL")
        hdr703 = _hdr(client, "ADMIN703")
        sqn_id = client.get("/api/auth/me", headers=hdr703).json()["session"]["squadron_id"]
        r = client.get(f"/api/planning/facilitators?unit_id={sqn_id}", headers=hdr_nat)
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_owner_can_list_facilitator_leave(self, client):
        hdr = _hdr(client, "ADMIN703")
        fac_id = self._get_703_facilitator_id(client)
        r = client.get(f"/api/planning/facilitators/{fac_id}/leave", headers=hdr)
        assert r.status_code == 200
        assert "leave" in r.json()

    def test_different_sqn_admin_cannot_list_facilitator_leave(self, client):
        fac_id = self._get_703_facilitator_id(client)
        hdr_704 = _hdr(client, "ADMIN704")
        r = client.get(f"/api/planning/facilitators/{fac_id}/leave", headers=hdr_704)
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_owner_can_add_facilitator_leave(self, client):
        hdr = _hdr(client, "ADMIN703")
        fac_id = self._get_703_facilitator_id(client)
        r = client.post(
            f"/api/planning/facilitators/{fac_id}/leave",
            json={"start_date": "2099-06-01", "end_date": "2099-06-07", "reason": "test"},
            headers=hdr,
        )
        assert r.status_code == 200

    def test_different_sqn_admin_cannot_add_facilitator_leave(self, client):
        fac_id = self._get_703_facilitator_id(client)
        hdr_704 = _hdr(client, "ADMIN704")
        r = client.post(
            f"/api/planning/facilitators/{fac_id}/leave",
            json={"start_date": "2099-06-01", "end_date": "2099-06-07"},
            headers=hdr_704,
        )
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"

    def test_unauthenticated_leave_list_rejected(self, client):
        r = client.get("/api/planning/facilitators/00000000-0000-0000-0000-000000000005/leave")
        assert r.status_code == 401

    def test_wing_admin_can_list_own_wing_facilitator_leave(self, client):
        """Wing admin can access facilitators in their own wing."""
        fac_id = self._get_703_facilitator_id(client)
        hdr_wing = _hdr(client, "ADMIN7WG")
        r = client.get(f"/api/planning/facilitators/{fac_id}/leave", headers=hdr_wing)
        assert r.status_code == 200


# ─── MISS-001: CEA import file size ──────────────────────────────────────────

class TestCEAImportFileSizeGuard:
    """import_cea_csv must reject files larger than UPLOAD_MAX_MB."""

    def _setup_wing_admin_year(self, client):
        hdr = _hdr(client, "ADMIN7WG")
        r = client.post("/api/planning/years", json={"year": 2099, "name": "Wing Year"}, headers=hdr)
        assert r.status_code == 200, r.text
        return hdr, r.json()["planning_year_id"]

    def test_small_csv_accepted(self, client):
        hdr, year_id = self._setup_wing_admin_year(client)
        csv_content = b"ActivityID,Name,StartDate,EndDate\n1,Test Activity,2099-06-01,2099-06-02\n"
        r = client.post(
            f"/api/planning/years/{year_id}/cea/import",
            files={"file": ("activities.csv", io.BytesIO(csv_content), "text/csv")},
            headers=hdr,
        )
        assert r.status_code == 200

    def test_oversized_csv_rejected(self, client):
        hdr, year_id = self._setup_wing_admin_year(client)
        # Default UPLOAD_MAX_MB is 5; generate 6 MB of content
        big_content = b"ActivityID,Name,StartDate,EndDate\n" + b"x" * (6 * 1024 * 1024)
        r = client.post(
            f"/api/planning/years/{year_id}/cea/import",
            files={"file": ("huge.csv", io.BytesIO(big_content), "text/csv")},
            headers=hdr,
        )
        assert r.status_code == 413, f"Expected 413, got {r.status_code}: {r.text}"

    def test_sqn_admin_cannot_import_cea(self, client):
        """CEA import is restricted to wing_admin and above."""
        hdr_sqn = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr_sqn)
        csv_content = b"ActivityID,Name,StartDate\n1,Test,2099-01-01\n"
        r = client.post(
            f"/api/planning/years/{year_id}/cea/import",
            files={"file": ("a.csv", io.BytesIO(csv_content), "text/csv")},
            headers=hdr_sqn,
        )
        assert r.status_code == 403

    def test_unauthenticated_import_rejected(self, client):
        csv_content = b"ActivityID,Name\n1,Test\n"
        r = client.post(
            "/api/planning/years/00000000-0000-0000-0000-000000000006/cea/import",
            files={"file": ("a.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert r.status_code == 401


# ─── No-regression: legitimate workflows must still work ─────────────────────

class TestLegitimateWorkflowsUnblocked:
    """Verify IDOR fixes do not block authorised access patterns."""

    def test_wing_admin_sees_all_wing_years(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_wing = _hdr(client, "ADMIN7WG")
        _make_year(client, hdr_703)
        r = client.get("/api/planning/years", headers=hdr_wing)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_nat_admin_can_read_any_cea_activities(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_nat = _hdr(client, "ADMINNATIONAL")
        year_id = _make_year(client, hdr_703)
        _create_manual_activity(client, hdr_703, year_id)
        r = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr_nat)
        assert r.status_code == 200

    def test_nat_admin_can_read_any_notice(self, client):
        hdr_703 = _hdr(client, "ADMIN703")
        hdr_nat = _hdr(client, "ADMINNATIONAL")
        year_id = _make_year(client, hdr_703)
        date_id = _add_parade_date(client, hdr_703, year_id)
        _create_notice(client, hdr_703, date_id)
        r = client.get(f"/api/planning/parade-dates/{date_id}/notices", headers=hdr_nat)
        assert r.status_code == 200

    def test_sqn_admin_full_cea_lifecycle(self, client):
        """Owner can create → classify → hide their own activity."""
        hdr = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr)
        act_id = _create_manual_activity(client, hdr, year_id, "Lifecycle Test")

        r = client.patch(
            f"/api/planning/cea/{act_id}/classify",
            json={"importance": "optional"},
            headers=hdr,
        )
        assert r.status_code == 200

        r = client.post(
            f"/api/planning/cea/{act_id}/local-hide",
            json={"is_hidden": True},
            headers=hdr,
        )
        assert r.status_code == 200

    def test_sqn_admin_full_notice_lifecycle(self, client):
        """Owner can create → update → archive their own notice."""
        hdr = _hdr(client, "ADMIN703")
        year_id = _make_year(client, hdr)
        date_id = _add_parade_date(client, hdr, year_id)
        notice_id = _create_notice(client, hdr, date_id, "Lifecycle Notice")

        r = client.patch(
            f"/api/planning/notices/{notice_id}",
            json={"notice_text": "Updated lifecycle"},
            headers=hdr,
        )
        assert r.status_code == 200

        r = client.post(f"/api/planning/notices/{notice_id}/archive", headers=hdr)
        assert r.status_code == 200


# ─── DEFECT-007: sqn_general planning-year scope ──────────────────────────────

class TestSqnGeneralYearScope:
    """sqn_general must only see their own squadron's planning years (DEFECT-007)."""

    def test_sqn_general_sees_own_year(self, client):
        """sqn_general can read planning years that belong to their squadron."""
        hdr_admin = _hdr(client, "ADMIN703")
        hdr_gen = _hdr(client, "703SQN2026")
        _make_year(client, hdr_admin, year=2088, name="Gen Scope Year")

        r = client.get("/api/planning/years", headers=hdr_gen)
        assert r.status_code == 200
        years = r.json()
        y2088 = [y for y in years if y["year"] == 2088]
        assert y2088, "sqn_general should see their own squadron's planning year"

    def test_sqn_general_cannot_see_other_squadron_year(self, client):
        """sqn_general from squadron 703 must not see planning years from squadron 701."""
        hdr_701 = _hdr(client, "ADMIN701")
        hdr_703_gen = _hdr(client, "703SQN2026")
        yr = _make_year(client, hdr_701, year=2087, name="701 Year — Gen Must Not See")
        yr_unit_id = client.get(
            f"/api/planning/years/{yr}", headers=hdr_701
        ).json().get("unit_id")

        r = client.get("/api/planning/years", headers=hdr_703_gen)
        assert r.status_code == 200
        years = r.json()
        leaked = [y for y in years if y.get("unit_id") == yr_unit_id and y["year"] == 2087]
        assert not leaked, (
            f"IDOR: sqn_general 703 can see planning year 2087 belonging to unit {yr_unit_id}"
        )
