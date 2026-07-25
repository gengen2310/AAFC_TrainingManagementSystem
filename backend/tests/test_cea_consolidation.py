"""DEFECT-005: CEA import pipeline consolidation.

Two CEA import pipelines existed: connected-frontend's legacy
POST /api/activities/import-cea (Activity model, no persisted review step,
per-squadron-only dedup) and Planning Workspace's
POST /api/planning/years/{year_id}/cea/import (CeaActivity model, full
needs-review/classify workflow, import-batch history). Consolidated onto
the reviewed pipeline; the legacy one is retired.
"""
import io

from tests.conftest import login


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def test_legacy_cea_import_is_retired(client):
    """The legacy endpoint must respond 410, never accept an import again."""
    hdr = _sqn_admin(client)
    r = client.post("/api/activities/import-cea", headers=hdr,
                    files={"file": ("x.csv", b"SeqNr,Name,Start date\n1,Test,01/01/2026", "text/csv")})
    assert r.status_code == 410
    assert r.json()["detail"]["error"] == "retired"


def test_legacy_cea_import_retired_even_with_preview_flag(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/activities/import-cea?preview=true", headers=hdr,
                    files={"file": ("x.csv", b"SeqNr,Name,Start date\n1,Test,01/01/2026", "text/csv")})
    assert r.status_code == 410


def test_legacy_cea_import_requires_auth_even_though_retired(client):
    """Retirement must not accidentally make the route publicly reachable."""
    r = client.post("/api/activities/import-cea",
                    files={"file": ("x.csv", b"SeqNr,Name\n1,Test", "text/csv")})
    assert r.status_code == 401


# ── classify(): sqn_admin must not overwrite a wing-wide CEA activity ────────
#
# CeaActivity.unit_id is only ever set for a manually-created, squadron-owned
# activity (create_manual_activity) -- never by the CSV import path, which
# leaves it null for a wing-wide/shared activity. A sqn_admin reaches a
# wing-imported activity's classify endpoint whenever a wing_admin imports
# into that specific squadron's own year_id (wing_admin can write into any
# squadron's year under require_year_access's wing_admin branch), so this was
# a real, reachable path, not a hypothetical.

def _wing_admin_year_for_squadron(client, sqn_admin_hdr):
    """Get the sqn_admin's own planning year id (created lazily if needed)."""
    r = client.get("/api/planning/years", headers=sqn_admin_hdr)
    assert r.status_code == 200, r.text
    years = r.json() if isinstance(r.json(), list) else r.json().get("years", [])
    if years:
        return years[0]["planning_year_id"]
    r = client.post("/api/planning/years", json={"year": 2098, "name": "CEA Test Year"},
                    headers=sqn_admin_hdr)
    assert r.status_code == 200, r.text
    return r.json()["planning_year_id"]


def test_sqn_admin_cannot_classify_wing_imported_cea_activity(client):
    sqn_hdr = _sqn_admin(client)
    wing_hdr = _wing_admin(client)
    year_id = _wing_admin_year_for_squadron(client, sqn_hdr)

    csv_content = b"ActivityID,Name,StartDate\nWING-1,Wing Imported Event,2099-06-01\n"
    r = client.post(
        f"/api/planning/years/{year_id}/cea/import",
        files={"file": ("wing.csv", io.BytesIO(csv_content), "text/csv")},
        headers=wing_hdr,
    )
    assert r.status_code == 200, r.text

    r = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=sqn_hdr)
    assert r.status_code == 200
    activity_id = next(a["id"] for a in r.json()["activities"] if a["cea_activity_id"] == "WING-1")

    r = client.patch(f"/api/planning/cea/{activity_id}/classify",
                     json={"importance": "must_attend"}, headers=sqn_hdr)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "wing_wide_activity"


def test_wing_admin_can_classify_wing_imported_cea_activity(client):
    wing_hdr = _wing_admin(client)
    sqn_hdr = _sqn_admin(client)
    year_id = _wing_admin_year_for_squadron(client, sqn_hdr)

    csv_content = b"ActivityID,Name,StartDate\nWING-2,Another Wing Event,2099-07-01\n"
    r = client.post(
        f"/api/planning/years/{year_id}/cea/import",
        files={"file": ("wing.csv", io.BytesIO(csv_content), "text/csv")},
        headers=wing_hdr,
    )
    assert r.status_code == 200, r.text

    r = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=wing_hdr)
    assert r.status_code == 200
    activity_id = next(a["id"] for a in r.json()["activities"] if a["cea_activity_id"] == "WING-2")

    r = client.patch(f"/api/planning/cea/{activity_id}/classify",
                     json={"importance": "must_attend"}, headers=wing_hdr)
    assert r.status_code == 200, r.text


def test_sqn_admin_can_still_classify_own_manual_cea_activity(client):
    """Regression guard: the unit_id-based check must not block a sqn_admin
    from classifying their own manually-created (squadron-owned) activity --
    only wing-wide/imported ones."""
    sqn_hdr = _sqn_admin(client)
    year_id = _wing_admin_year_for_squadron(client, sqn_hdr)

    r = client.post(f"/api/planning/years/{year_id}/cea/activities",
                    json={"activity_name": "My own squadron event"}, headers=sqn_hdr)
    assert r.status_code == 200, r.text
    activity_id = r.json()["id"]

    r = client.patch(f"/api/planning/cea/{activity_id}/classify",
                     json={"importance": "high"}, headers=sqn_hdr)
    assert r.status_code == 200, r.text
