"""Regression tests: Planning Workspace write endpoints require Proxy/Intervention Mode.

Finding 5: Several squadron-scoped write endpoints used _require_year_access (no proxy
awareness) instead of require_can_write_squadron (proxy/intervention aware). Wing Admin
could mutate squadron planning data without activating Proxy Mode.

Covers:
- add_parade_date (POST /years/{id}/parade-dates)
- generate_parade_dates (POST /years/{id}/generate-parade-dates)
- update_future_parade_day (POST /years/{id}/update-future-parade-day)
- delete_parade_date (DELETE /parade-dates/{id})
- create_session (POST /parade-dates/{id}/sessions)
- assign_mission (POST /years/{id}/assign-mission)
"""
import pytest
from tests.conftest import login, next_test_year


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _nat_admin_hdr(client):
    return login(client, "ADMINNATIONAL")


def _general_hdr(client):
    return login(client, "703SQN2026")


def _auditor_hdr(client):
    return login(client, "AUDITOR2026")


def _get_sqn_id(client):
    hdr = _sqn_admin_hdr(client)
    me = client.get("/api/auth/me", headers=hdr)
    return me.json()["session"]["squadron_id"]


def _make_sqn_year(client, sqn_admin_hdr=None):
    """Create a squadron planning year as sqn_admin. Returns the year object."""
    hdr = sqn_admin_hdr or _sqn_admin_hdr(client)
    year = next_test_year()
    r = client.post("/api/planning/years",
                    json={"year": year, "name": f"{year} Proxy Test Year"},
                    headers=hdr)
    assert r.status_code == 200, f"Failed to create year: {r.text}"
    return r.json()


def _add_parade_date(client, year_id, hdr, date_str="2030-10-01"):
    return client.post(f"/api/planning/years/{year_id}/parade-dates",
                       json={"parade_date": date_str},
                       headers=hdr)


def _enter_proxy(client, wing_hdr, sqn_id):
    r = client.post(f"/api/proxy/enter/{sqn_id}",
                    json={"reason": "Finding 5 proxy RBAC regression test"},
                    headers=wing_hdr)
    assert r.status_code == 200, f"proxy/enter failed: {r.text}"


def _exit_proxy(client, hdr):
    client.post("/api/proxy/exit", headers=hdr)


# ─── add_parade_date ────────────────────────────────────────────────────────

class TestAddParadeDateProxy:

    def test_sqn_general_cannot_add_parade_date(self, client):
        year = _make_sqn_year(client)
        r = _add_parade_date(client, year["planning_year_id"], _general_hdr(client))
        assert r.status_code == 403, r.text

    def test_auditor_cannot_add_parade_date(self, client):
        year = _make_sqn_year(client)
        r = _add_parade_date(client, year["planning_year_id"], _auditor_hdr(client))
        assert r.status_code == 403, r.text

    def test_wing_admin_cannot_add_parade_date_without_proxy(self, client):
        """Wing Admin must not add parade dates to a squadron year without Proxy Mode."""
        year = _make_sqn_year(client)
        wing_hdr = _wing_admin_hdr(client)
        r = _add_parade_date(client, year["planning_year_id"], wing_hdr)
        assert r.status_code == 403, (
            f"Wing Admin added parade date without Proxy Mode — status {r.status_code}: {r.text}"
        )
        assert r.json()["detail"]["error"] == "proxy_required", r.text

    def test_wing_admin_can_add_parade_date_with_proxy(self, client):
        """Wing Admin with active Proxy Mode can add parade dates."""
        year = _make_sqn_year(client)
        sqn_id = year["unit_id"]
        wing_hdr = _wing_admin_hdr(client)
        _enter_proxy(client, wing_hdr, sqn_id)
        try:
            r = _add_parade_date(client, year["planning_year_id"], wing_hdr,
                                 date_str="2030-10-15")
            assert r.status_code == 200, f"Proxy add_parade_date failed: {r.text}"
        finally:
            _exit_proxy(client, wing_hdr)

    def test_national_admin_cannot_add_parade_date_without_intervention(self, client):
        """National Admin must not add parade dates without Delegated Intervention."""
        year = _make_sqn_year(client)
        nat_hdr = _nat_admin_hdr(client)
        r = _add_parade_date(client, year["planning_year_id"], nat_hdr)
        assert r.status_code == 403, (
            f"National Admin added parade date without Intervention — status {r.status_code}: {r.text}"
        )
        assert r.json()["detail"]["error"] == "intervention_required", r.text

    def test_sqn_admin_can_add_parade_date(self, client):
        year = _make_sqn_year(client)
        r = _add_parade_date(client, year["planning_year_id"], _sqn_admin_hdr(client))
        assert r.status_code == 200, r.text


# ─── generate_parade_dates ──────────────────────────────────────────────────

class TestGenerateParadeDatesProxy:

    def _gen_payload(self):
        return {
            "start_date": "2030-09-01",
            "end_date": "2030-12-31",
            "weekday": 2,  # Wednesday
            "parade_type": "standard",
        }

    def test_wing_admin_cannot_generate_without_proxy(self, client):
        year = _make_sqn_year(client)
        wing_hdr = _wing_admin_hdr(client)
        r = client.post(f"/api/planning/years/{year['planning_year_id']}/generate-parade-dates",
                        json=self._gen_payload(),
                        headers=wing_hdr)
        assert r.status_code == 403, (
            f"Wing Admin generated parade dates without Proxy — status {r.status_code}: {r.text}"
        )
        assert r.json()["detail"]["error"] == "proxy_required", r.text

    def test_national_admin_cannot_generate_without_intervention(self, client):
        year = _make_sqn_year(client)
        nat_hdr = _nat_admin_hdr(client)
        r = client.post(f"/api/planning/years/{year['planning_year_id']}/generate-parade-dates",
                        json=self._gen_payload(),
                        headers=nat_hdr)
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["error"] == "intervention_required", r.text

    def test_wing_admin_can_generate_with_proxy(self, client):
        year = _make_sqn_year(client)
        sqn_id = year["unit_id"]
        wing_hdr = _wing_admin_hdr(client)
        _enter_proxy(client, wing_hdr, sqn_id)
        try:
            r = client.post(f"/api/planning/years/{year['planning_year_id']}/generate-parade-dates",
                            json=self._gen_payload(),
                            headers=wing_hdr)
            assert r.status_code == 200, f"Proxy generate failed: {r.text}"
        finally:
            _exit_proxy(client, wing_hdr)

    def test_sqn_general_cannot_generate(self, client):
        year = _make_sqn_year(client)
        r = client.post(f"/api/planning/years/{year['planning_year_id']}/generate-parade-dates",
                        json=self._gen_payload(),
                        headers=_general_hdr(client))
        assert r.status_code == 403, r.text


# ─── create_session ─────────────────────────────────────────────────────────

class TestCreateSessionProxy:

    def _make_parade_night(self, client, year_id, sqn_admin_hdr):
        r = _add_parade_date(client, year_id, sqn_admin_hdr, date_str="2030-11-05")
        assert r.status_code == 200, r.text
        return r.json()["parade_date_id"]

    def test_wing_admin_cannot_create_session_without_proxy(self, client):
        year = _make_sqn_year(client)
        sqn_hdr = _sqn_admin_hdr(client)
        pn_id = self._make_parade_night(client, year["planning_year_id"], sqn_hdr)
        wing_hdr = _wing_admin_hdr(client)
        r = client.post(f"/api/planning/parade-dates/{pn_id}/sessions",
                        json={"session_number": 1, "cadet_group": "junior"},
                        headers=wing_hdr)
        assert r.status_code == 403, (
            f"Wing Admin created session without Proxy Mode — status {r.status_code}: {r.text}"
        )
        assert r.json()["detail"]["error"] == "proxy_required", r.text

    def test_national_admin_cannot_create_session_without_intervention(self, client):
        year = _make_sqn_year(client)
        sqn_hdr = _sqn_admin_hdr(client)
        pn_id = self._make_parade_night(client, year["planning_year_id"], sqn_hdr)
        nat_hdr = _nat_admin_hdr(client)
        r = client.post(f"/api/planning/parade-dates/{pn_id}/sessions",
                        json={"session_number": 1, "cadet_group": "junior"},
                        headers=nat_hdr)
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["error"] == "intervention_required", r.text

    def test_sqn_general_cannot_create_session(self, client):
        year = _make_sqn_year(client)
        sqn_hdr = _sqn_admin_hdr(client)
        pn_id = self._make_parade_night(client, year["planning_year_id"], sqn_hdr)
        r = client.post(f"/api/planning/parade-dates/{pn_id}/sessions",
                        json={"session_number": 1, "cadet_group": "junior"},
                        headers=_general_hdr(client))
        assert r.status_code == 403, r.text

    def test_sqn_admin_can_create_session(self, client):
        year = _make_sqn_year(client)
        sqn_hdr = _sqn_admin_hdr(client)
        pn_id = self._make_parade_night(client, year["planning_year_id"], sqn_hdr)
        r = client.post(f"/api/planning/parade-dates/{pn_id}/sessions",
                        json={"session_number": 1, "cadet_group": "junior"},
                        headers=sqn_hdr)
        assert r.status_code == 200, r.text

    def test_wing_admin_can_create_session_with_proxy(self, client):
        year = _make_sqn_year(client)
        sqn_hdr = _sqn_admin_hdr(client)
        pn_id = self._make_parade_night(client, year["planning_year_id"], sqn_hdr)
        sqn_id = year["unit_id"]
        wing_hdr = _wing_admin_hdr(client)
        _enter_proxy(client, wing_hdr, sqn_id)
        try:
            r = client.post(f"/api/planning/parade-dates/{pn_id}/sessions",
                            json={"session_number": 2, "cadet_group": "junior"},
                            headers=wing_hdr)
            assert r.status_code == 200, f"Proxy create_session failed: {r.text}"
        finally:
            _exit_proxy(client, wing_hdr)


# ─── delete_parade_date ─────────────────────────────────────────────────────

class TestDeleteParadeDateProxy:

    def test_wing_admin_cannot_delete_parade_date_without_proxy(self, client):
        year = _make_sqn_year(client)
        sqn_hdr = _sqn_admin_hdr(client)
        r = _add_parade_date(client, year["planning_year_id"], sqn_hdr, date_str="2030-12-03")
        assert r.status_code == 200
        pn_id = r.json()["parade_date_id"]
        wing_hdr = _wing_admin_hdr(client)
        r2 = client.delete(f"/api/planning/parade-dates/{pn_id}", headers=wing_hdr)
        assert r2.status_code == 403, (
            f"Wing Admin deleted parade date without Proxy — status {r2.status_code}: {r2.text}"
        )
        assert r2.json()["detail"]["error"] == "proxy_required", r2.text

    def test_national_admin_cannot_delete_without_intervention(self, client):
        year = _make_sqn_year(client)
        sqn_hdr = _sqn_admin_hdr(client)
        r = _add_parade_date(client, year["planning_year_id"], sqn_hdr, date_str="2030-12-10")
        assert r.status_code == 200
        pn_id = r.json()["parade_date_id"]
        nat_hdr = _nat_admin_hdr(client)
        r2 = client.delete(f"/api/planning/parade-dates/{pn_id}", headers=nat_hdr)
        assert r2.status_code == 403, r2.text
        assert r2.json()["detail"]["error"] == "intervention_required", r2.text
