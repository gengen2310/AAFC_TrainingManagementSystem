"""Phase A: year model tests — Wing.timezone, PlanningYear.status, lifecycle, rollover."""
from tests.conftest import login, next_test_year
from datetime import date, timedelta


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _nat_admin_hdr(client):
    return login(client, "ADMINNATIONAL")


# ── Wing.timezone ─────────────────────────────────────────────

def test_wing_timezone_returned_in_year_list(client):
    """Wing.timezone must be set for 7WG so rollover is computable."""
    h = _wing_admin_hdr(client)
    r = client.get("/api/planning/years?wing_id=", headers=h)
    # Wing timezone is not in year list — test via a dedicated endpoint
    # This test verifies the endpoint exists and returns Perth.
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["timezone"] == "Australia/Perth"


def test_wing_timezone_sqn_returns_their_wing_tz(client):
    h = _sqn_admin_hdr(client)
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["timezone"] == "Australia/Perth"


def test_wing_timezone_no_wing_returns_400(client):
    h = _nat_admin_hdr(client)
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "no_wing"


def test_wing_timezone_requires_auth(client):
    r = client.get("/api/planning/wing-timezone")
    assert r.status_code == 401


# ── PlanningYear.status field ─────────────────────────────────

def test_new_year_has_status_active(client):
    h = _sqn_admin_hdr(client)
    r = client.post("/api/planning/years",
                    json={"year": next_test_year(), "name": "Status test"},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "status" in body, "status field missing from year response"
    assert body["status"] == "active"
    assert body["active_status"] is True  # backward-compat: both present


def test_archive_year_sets_status_archived(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Archive test"},
                     headers=h).json()
    yr_id = yr["planning_year_id"]
    r = client.patch(f"/api/planning/years/{yr_id}",
                     json={"active_status": False, "version": yr["version"]},
                     headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "archived"
    assert body["active_status"] is False


def test_restore_year_sets_status_active(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Restore test"},
                     headers=h).json()
    yr_id = yr["planning_year_id"]
    # Archive it first
    client.patch(f"/api/planning/years/{yr_id}",
                 json={"active_status": False, "version": yr["version"]},
                 headers=h)
    yr2 = client.get(f"/api/planning/years/{yr_id}", headers=h).json()
    # Restore
    r = client.patch(f"/api/planning/years/{yr_id}",
                     json={"active_status": True, "version": yr2["version"]},
                     headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    assert r.json()["active_status"] is True


# ── resolve_active_year() / rollover ─────────────────────────


def _archive_other_active_years(db, squadron_id, keep_id):
    """Archive all active planning years for this squadron except `keep_id`.

    Previous tests leave multiple active years for squadron 703 in the shared
    test DB.  resolve_active_year() uses .first() to find "the" active year, so
    the tests must ensure exactly one active year exists when they run.
    """
    from app.models.planning import PlanningYear
    others = (
        db.query(PlanningYear)
        .filter(
            PlanningYear.unit_id == squadron_id,
            PlanningYear.status == "active",
            PlanningYear.id != keep_id,
        )
        .all()
    )
    for y in others:
        y.status = "archived"
        y.active_status = False
    db.commit()


def test_rollover_promotes_draft_to_active(client):
    """A draft year with rollover date in the past is promoted on first read."""
    from app.database import SessionLocal
    from app.services_year import resolve_active_year
    from app.models.planning import PlanningYear

    h = _sqn_admin_hdr(client)
    base = next_test_year()
    # Create the active year.
    active_yr = client.post(
        "/api/planning/years",
        json={"year": base, "name": f"Active {base}"},
        headers=h,
    ).json()
    assert "unit_id" in active_yr, active_yr
    squadron_id = active_yr["unit_id"]
    wing_id = active_yr["wing_id"]
    active_yr_id = active_yr["planning_year_id"]

    # Create the draft year (base+1 is reserved for this rollover test by the
    # step-3 counter convention).  It starts as active — set to draft directly.
    draft_year_num = base + 1
    draft_yr = client.post(
        "/api/planning/years",
        json={"year": draft_year_num, "name": f"Draft {draft_year_num}"},
        headers=h,
    ).json()
    draft_yr_id = draft_yr["planning_year_id"]

    # Isolate the test: archive all pre-existing active years except our own,
    # and set the draft year to 'draft' status.
    db = SessionLocal()
    try:
        _archive_other_active_years(db, squadron_id, keep_id=active_yr_id)
        py = db.get(PlanningYear, draft_yr_id)
        py.status = "draft"
        py.active_status = False
        db.commit()
    finally:
        db.close()

    # Trigger rollover with _today set to 1 Jan of the draft year (rollover due).
    db = SessionLocal()
    try:
        result = resolve_active_year(
            squadron_id, wing_id, db,
            _today=date(draft_year_num, 1, 1),
        )
        assert result is not None, "resolve_active_year must return a year"
        assert result.id == draft_yr_id, (
            "The draft year should have been promoted to active"
        )
        assert result.status == "active"
        assert result.active_status is True

        old_active = db.get(PlanningYear, active_yr_id)
        db.refresh(old_active)
        assert old_active.status == "archived", (
            "Previously active year should be archived after rollover"
        )
        assert old_active.active_status is False
    finally:
        db.close()


def test_rollover_does_not_trigger_before_rollover_date(client):
    """A draft year with rollover date in the future is NOT auto-promoted."""
    from app.database import SessionLocal
    from app.services_year import resolve_active_year
    from app.models.planning import PlanningYear

    h = _sqn_admin_hdr(client)
    base = next_test_year()
    active_yr = client.post(
        "/api/planning/years",
        json={"year": base, "name": f"Active {base}"},
        headers=h,
    ).json()
    squadron_id = active_yr["unit_id"]
    wing_id = active_yr["wing_id"]
    active_yr_id = active_yr["planning_year_id"]

    draft_year_num = base + 1
    draft_yr = client.post(
        "/api/planning/years",
        json={"year": draft_year_num, "name": f"Draft {draft_year_num}"},
        headers=h,
    ).json()
    draft_yr_id = draft_yr["planning_year_id"]

    # Isolate: archive all other active years; set our draft year to 'draft'.
    db = SessionLocal()
    try:
        _archive_other_active_years(db, squadron_id, keep_id=active_yr_id)
        py = db.get(PlanningYear, draft_yr_id)
        py.status = "draft"
        py.active_status = False
        db.commit()
    finally:
        db.close()

    # _today = Dec 31 of the year before the draft year — rollover date not reached.
    day_before = date(draft_year_num, 1, 1) - timedelta(days=1)
    db = SessionLocal()
    try:
        result = resolve_active_year(
            squadron_id, wing_id, db,
            _today=day_before,
        )
        # Should return the EXISTING active year, unchanged.
        assert result is not None
        assert result.id == active_yr_id, (
            "Active year should remain unchanged when rollover date not yet reached"
        )
        assert result.status == "active"

        draft_check = db.get(PlanningYear, draft_yr_id)
        db.refresh(draft_check)
        assert draft_check.status == "draft", (
            "Draft year should NOT have been promoted before its rollover date"
        )
    finally:
        db.close()


# ── Lifecycle endpoints ───────────────────────────────────────


def _archive_existing_drafts(client, h):
    """Archive any lingering draft years for this user's squadron.

    The rollover tests directly set years to 'draft' status via the DB and may
    leave them behind. This helper ensures a clean slate before lifecycle tests
    that need to create a new draft (one-draft-per-squadron rule).
    """
    years = client.get("/api/planning/years", headers=h).json()
    for yr in years:
        if yr.get("status") == "draft":
            client.post(f"/api/planning/years/{yr['planning_year_id']}/archive", headers=h)


def _archive_existing_active_and_drafts(client, h):
    """Archive all active and draft years for this user's squadron.

    Used before promote tests: ensures exactly the year created in the test is
    the current active year when the promote happens, so the post-promote
    assertion can check the correct year_id.
    """
    years = client.get("/api/planning/years", headers=h).json()
    for yr in years:
        if yr.get("status") in ("active", "draft"):
            client.post(f"/api/planning/years/{yr['planning_year_id']}/archive", headers=h)


def test_create_draft_year(client):
    h = _sqn_admin_hdr(client)
    _archive_existing_drafts(client, h)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    r = client.post("/api/planning/years/draft",
                    json={"year": base + 1, "name": f"Draft {base + 1}",
                          "source_year_id": active_yr["planning_year_id"]},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["active_status"] is False
    assert body["year"] == base + 1


def test_create_draft_fails_if_draft_already_exists(client):
    h = _sqn_admin_hdr(client)
    _archive_existing_drafts(client, h)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    client.post("/api/planning/years/draft",
                json={"year": base + 1, "name": f"Draft {base + 1}",
                      "source_year_id": active_yr["planning_year_id"]},
                headers=h)
    # Second draft should be rejected
    r = client.post("/api/planning/years/draft",
                    json={"year": base + 2, "name": f"Draft {base + 2}",
                          "source_year_id": active_yr["planning_year_id"]},
                    headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "draft_already_exists"


def test_promote_draft_to_active(client):
    h = _sqn_admin_hdr(client)
    _archive_existing_active_and_drafts(client, h)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1, "name": f"Draft {base + 1}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h).json()
    r = client.post(f"/api/planning/years/{draft_yr['planning_year_id']}/promote",
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "active"
    assert body["active_status"] is True
    # Old active should now be archived
    old = client.get(f"/api/planning/years/{active_yr['planning_year_id']}", headers=h).json()
    assert old["status"] == "archived"
    assert old["active_status"] is False


def test_promote_fails_if_not_draft(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Active"},
                     headers=h).json()
    r = client.post(f"/api/planning/years/{yr['planning_year_id']}/promote", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "not_a_draft"


def test_archive_year(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "To archive"},
                     headers=h).json()
    r = client.post(f"/api/planning/years/{yr['planning_year_id']}/archive", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "archived"
    assert r.json()["active_status"] is False


def test_lifecycle_requires_sqn_admin(client):
    h = login(client, "703SQN2026")  # sqn_general
    yr_id = client.get("/api/planning/years", headers=login(client, "ADMIN703")).json()[0]["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/archive", headers=h)
    assert r.status_code == 403


def test_lifecycle_requires_auth(client):
    r = client.post("/api/planning/years/draft",
                    json={"year": 2099, "name": "Unauth", "source_year_id": "fake-id"})
    assert r.status_code == 401


def test_create_draft_requires_sqn_admin(client):
    """sqn_general must not be able to create a draft year (403)."""
    h = login(client, "703SQN2026")  # sqn_general
    r = client.post("/api/planning/years/draft",
                    json={"year": 2099, "name": "Forbidden draft",
                          "source_year_id": "00000000-0000-0000-0000-000000000000"},
                    headers=h)
    assert r.status_code == 403


def test_promote_requires_sqn_admin(client):
    """sqn_general must not be able to promote a year (403)."""
    h_admin = login(client, "ADMIN703")
    h_gen = login(client, "703SQN2026")  # sqn_general
    # Get a real year_id from the seeded data to hit the scope check
    yr_id = client.get("/api/planning/years", headers=h_admin).json()[0]["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/promote", headers=h_gen)
    assert r.status_code == 403


def test_promote_requires_auth(client):
    """Unauthenticated promote must return 401."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/api/planning/years/{fake_id}/promote")
    assert r.status_code == 401


def test_archive_requires_auth(client):
    """Unauthenticated archive must return 401."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/api/planning/years/{fake_id}/archive")
    assert r.status_code == 401
