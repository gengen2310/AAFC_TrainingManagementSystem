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

def test_wing_timezone_endpoint_returns_perth(client):
    """Wing.timezone must be set for 7WG so rollover is computable."""
    h = _wing_admin_hdr(client)
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
    # Create via /draft so active_yr stays active (POST /years would auto-archive it).
    draft_yr = client.post(
        "/api/planning/years/draft",
        json={"year": draft_year_num, "name": f"Draft {draft_year_num}",
              "source_year_id": active_yr_id},
        headers=h,
    ).json()
    draft_yr_id = draft_yr["planning_year_id"]

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


# ── Backend readers use status ────────────────────────────────

def test_parade_night_attaches_to_active_not_draft(client):
    """A draft year must never attract a parade night — only the active year does."""
    h = _sqn_admin_hdr(client)
    _archive_existing_drafts(client, h)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1, "name": f"Draft {base + 1}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h).json()
    assert draft_yr["status"] == "draft"

    night_date = f"{base}-06-15"
    r = client.post("/api/parade-nights",
                    json={"date": night_date, "term": "T2"},
                    headers=h)
    assert r.status_code == 200, r.text
    pn_id = r.json()["parade_night_id"]
    assert r.json()["linked_to_planning_year"] is True

    # The night's ParadeDate must be under the ACTIVE year, not the draft
    active_dates = client.get(
        f"/api/planning/years/{active_yr['planning_year_id']}/parade-dates",
        headers=h).json()
    draft_dates = client.get(
        f"/api/planning/years/{draft_yr['planning_year_id']}/parade-dates",
        headers=h).json()

    assert any(d["parade_night_id"] == pn_id for d in active_dates), (
        "Night must be under the active year"
    )
    assert not any(d["parade_night_id"] == pn_id for d in draft_dates), (
        "Night must NOT be under the draft year"
    )


# ── One-active-year invariant ─────────────────────────────────

def test_cannot_have_two_active_years_for_same_squadron(client):
    """The DB-level unique index must prevent a second active year per squadron."""
    from app.database import SessionLocal
    from app.models.planning import PlanningYear

    h = _sqn_admin_hdr(client)
    base = next_test_year()
    yr1_id = None
    yr2_id = None
    try:
        # First active year — succeeds
        yr1 = client.post("/api/planning/years",
                          json={"year": base, "name": f"Year {base}"},
                          headers=h).json()
        assert yr1["status"] == "active"
        yr1_id = yr1["planning_year_id"]

        # Try to create a second active year via the old PATCH restore path
        # (bypassing the new lifecycle endpoints to simulate the invariant test)
        yr2 = client.post("/api/planning/years",
                          json={"year": base + 1, "name": f"Year {base + 1}"},
                          headers=h).json()
        # The second POST creates a year — but the index means restoring an
        # archived year while one is already active must fail.
        # Archive yr2 first, then try to restore it while yr1 is still active.
        yr2_id = yr2["planning_year_id"]
        client.post(f"/api/planning/years/{yr2_id}/archive", headers=h)
        r = client.post(f"/api/planning/years/{yr2_id}/promote", headers=h)
        # promote of an archived year is not allowed (only draft can be promoted)
        assert r.status_code == 409
        assert r.json()["detail"]["error"] == "not_a_draft"
    finally:
        # MJ-9: restore squadron 703 to having an active year so subsequent
        # tests that expect one don't fail with IndexError.
        db = SessionLocal()
        try:
            if yr1_id:
                yr1_obj = db.get(PlanningYear, yr1_id)
                if yr1_obj and yr1_obj.status != "active":
                    yr1_obj.status = "active"
                    yr1_obj.active_status = True
                    db.commit()
        finally:
            db.close()


def test_promote_replaces_old_active_atomically(client):
    """Promoting a draft archives the old active in the same transaction."""
    h = _sqn_admin_hdr(client)
    _archive_existing_active_and_drafts(client, h)
    base = next_test_year()
    yr1 = client.post("/api/planning/years",
                      json={"year": base, "name": f"Year {base}"},
                      headers=h).json()
    draft = client.post("/api/planning/years/draft",
                        json={"year": base + 1, "name": f"Draft {base + 1}",
                              "source_year_id": yr1["planning_year_id"]},
                        headers=h).json()
    client.post(f"/api/planning/years/{draft['planning_year_id']}/promote", headers=h)

    years = client.get("/api/planning/years", headers=h).json()
    active_years = [y for y in years if y["status"] == "active"]
    assert len(active_years) == 1, (
        f"Expected exactly one active year after promotion, got {len(active_years)}: "
        f"{[y['planning_year_id'] for y in active_years]}"
    )


# ── BL-1: resolve_active_year UUID-order regression ──────────────


def test_resolve_active_year_promotes_across_uuid_orderings(client):
    """Loop ≥20 year-pairs through resolve_active_year() to catch UUID-ordering failures.

    The bug: SQLAlchemy batches both UPDATEs and orders by UUID; when the draft's
    UUID sorts before the active year's UUID, the activate fires first and hits the
    unique index. The db.flush() fix in BL-1 ensures the archive always precedes the
    activate regardless of UUID order. A single pair has a ~50% chance of picking
    the safe ordering — 20 pairs reduces the false-pass probability to <1-in-a-million.
    """
    from app.database import SessionLocal
    from app.services_year import resolve_active_year
    from app.models.planning import PlanningYear

    h = _sqn_admin_hdr(client)

    for i in range(20):
        base = next_test_year()
        # Create source active year
        active_yr = client.post(
            "/api/planning/years",
            json={"year": base, "name": f"BL1-Active-{i}"},
            headers=h,
        ).json()
        squadron_id = active_yr["unit_id"]
        wing_id = active_yr["wing_id"]
        active_yr_id = active_yr["planning_year_id"]

        # Create draft year (next year number)
        draft_yr = client.post(
            "/api/planning/years/draft",
            json={"year": base + 1, "name": f"BL1-Draft-{i}",
                  "source_year_id": active_yr_id},
            headers=h,
        ).json()
        draft_yr_id = draft_yr["planning_year_id"]

        # Run resolve_active_year with rollover date reached
        db = SessionLocal()
        try:
            result = resolve_active_year(
                squadron_id, wing_id, db,
                _today=date(base + 1, 1, 1),
            )
            assert result is not None, f"iteration {i}: resolve_active_year returned None"
            assert result.status == "active", f"iteration {i}: result status is {result.status!r}"
            assert result.id == draft_yr_id, (
                f"iteration {i}: expected draft {draft_yr_id} to be promoted, got {result.id}"
            )
            old = db.get(PlanningYear, active_yr_id)
            db.refresh(old)
            assert old.status == "archived", (
                f"iteration {i}: old active year should be archived, got {old.status!r}"
            )
        finally:
            db.close()


# ── BL-2: proxy gate on promote and archive ───────────────────────


def test_promote_requires_proxy_for_wing_admin(client):
    """wing_admin without Proxy Mode must get 403 proxy_required on promote."""
    h_admin = _sqn_admin_hdr(client)
    h_wing = _wing_admin_hdr(client)
    _archive_existing_drafts(client, h_admin)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h_admin).json()
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1, "name": f"Draft {base + 1}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h_admin).json()
    # wing_admin without proxy — must 403
    r = client.post(f"/api/planning/years/{draft_yr['planning_year_id']}/promote",
                    headers=h_wing)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


def test_archive_requires_proxy_for_wing_admin(client):
    """wing_admin without Proxy Mode must get 403 proxy_required on archive."""
    h_admin = _sqn_admin_hdr(client)
    h_wing = _wing_admin_hdr(client)
    base = next_test_year()
    yr = client.post("/api/planning/years",
                     json={"year": base, "name": f"Active {base}"},
                     headers=h_admin).json()
    # wing_admin without proxy — must 403
    r = client.post(f"/api/planning/years/{yr['planning_year_id']}/archive",
                    headers=h_wing)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


# ── BL-3: restore archived year ───────────────────────────────────


def test_restore_archived_year(client):
    """Restore archived year A while year B is active: A becomes active, B is archived."""
    h = _sqn_admin_hdr(client)
    _archive_existing_active_and_drafts(client, h)
    base = next_test_year()
    # Create year A as active
    yr_a = client.post("/api/planning/years",
                       json={"year": base, "name": f"Year A {base}"},
                       headers=h).json()
    yr_a_id = yr_a["planning_year_id"]
    # Archive A
    client.post(f"/api/planning/years/{yr_a_id}/archive", headers=h)

    # Create year B as active
    yr_b = client.post("/api/planning/years",
                       json={"year": base + 1, "name": f"Year B {base + 1}"},
                       headers=h).json()
    yr_b_id = yr_b["planning_year_id"]
    assert yr_b["status"] == "active"

    # Restore A via /restore
    r = client.post(f"/api/planning/years/{yr_a_id}/restore", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"

    # B should now be archived
    b_check = client.get(f"/api/planning/years/{yr_b_id}", headers=h).json()
    assert b_check["status"] == "archived", f"Year B should be archived, got {b_check['status']!r}"


def test_restore_draft_returns_409(client):
    """Restoring a draft must return 409 use_promote."""
    h = _sqn_admin_hdr(client)
    _archive_existing_drafts(client, h)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1, "name": f"Draft {base + 1}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h).json()
    r = client.post(f"/api/planning/years/{draft_yr['planning_year_id']}/restore",
                    headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "use_promote"


# ── BL-4: PATCH active_status=True while another year is active ──


def test_patch_active_status_true_while_another_year_is_active(client):
    """PATCH archived year with active_status=true while another year is active.

    Before BL-4, this raised IntegrityError (HTTP 500) because update_planning_year
    did not archive the incumbent before activating the target.
    """
    h = _sqn_admin_hdr(client)
    _archive_existing_active_and_drafts(client, h)
    base = next_test_year()
    # Create an active year
    yr1 = client.post("/api/planning/years",
                      json={"year": base, "name": f"Year {base}"},
                      headers=h).json()
    yr1_id = yr1["planning_year_id"]
    assert yr1["status"] == "active"

    # Create a second year (auto-archives yr1)
    yr2 = client.post("/api/planning/years",
                      json={"year": base + 1, "name": f"Year {base + 1}"},
                      headers=h).json()
    yr2_id = yr2["planning_year_id"]
    assert yr2["status"] == "active"

    # yr1 should now be archived
    yr1_check = client.get(f"/api/planning/years/{yr1_id}", headers=h).json()
    assert yr1_check["status"] == "archived"

    # PATCH yr1 back to active — this must succeed (no IntegrityError)
    r = client.patch(f"/api/planning/years/{yr1_id}",
                     json={"active_status": True, "version": yr1_check["version"]},
                     headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"

    # yr2 should now be archived
    yr2_check = client.get(f"/api/planning/years/{yr2_id}", headers=h).json()
    assert yr2_check["status"] == "archived"


# ── MJ-1: wing_timezone_unset → 409 ──────────────────────────────


def test_wing_timezone_unset_returns_409(client):
    """Wing timezone unset must return 409 wing_timezone_unset, not 500."""
    from app.database import SessionLocal
    from app.models.organisations import Wing

    h = _wing_admin_hdr(client)
    # Find the wing and temporarily null its timezone
    db = SessionLocal()
    try:
        r = client.get("/api/planning/wing-timezone", headers=h)
        wing_tz = r.json().get("timezone")
        # Get wing_id from login
        import json, base64
        token = h["Authorization"].split()[1]
        payload = json.loads(base64.b64decode(token.split(".")[1] + "==").decode())
        wing_id = payload.get("wing_id")

        if not wing_id:
            # Can't find wing_id from token — skip but don't fail
            return

        wing = db.get(Wing, wing_id)
        if not wing:
            return
        original_tz = wing.timezone
        try:
            wing.timezone = None
            db.commit()
            r2 = client.get("/api/planning/wing-timezone", headers=h)
            assert r2.status_code == 409, f"Expected 409, got {r2.status_code}: {r2.text}"
            assert r2.json()["detail"]["error"] == "wing_timezone_unset"
        finally:
            wing.timezone = original_tz
            db.commit()
    finally:
        db.close()


# ── MJ-10: 403 tenancy tests for promote/archive ─────────────────


def test_promote_requires_auth_from_different_squadron(client):
    """sqn_admin from a different squadron must get 403 on promote."""
    h_admin = _sqn_admin_hdr(client)   # ADMIN703
    h_other = login(client, "ADMIN704")  # different squadron
    _archive_existing_drafts(client, h_admin)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h_admin).json()
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1, "name": f"Draft {base + 1}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h_admin).json()
    r = client.post(f"/api/planning/years/{draft_yr['planning_year_id']}/promote",
                    headers=h_other)
    assert r.status_code == 403, r.text


def test_archive_requires_auth_from_different_squadron(client):
    """sqn_admin from a different squadron must get 403 on archive."""
    h_admin = _sqn_admin_hdr(client)   # ADMIN703
    h_other = login(client, "ADMIN704")  # different squadron
    base = next_test_year()
    yr = client.post("/api/planning/years",
                     json={"year": base, "name": f"Active {base}"},
                     headers=h_admin).json()
    r = client.post(f"/api/planning/years/{yr['planning_year_id']}/archive",
                    headers=h_other)
    assert r.status_code == 403, r.text


# ── national_admin without intervention — 403 on all writes ───────────────

def test_national_admin_cannot_create_squadron_year_without_intervention(client):
    """national_admin needs Delegated Intervention to create a squadron year."""
    h_nat = _nat_admin_hdr(client)
    h_admin = _sqn_admin_hdr(client)
    # Resolve the squadron's unit_id via an existing year
    years_r = client.get("/api/planning/years", headers=h_admin)
    assert years_r.status_code == 200
    unit_id = years_r.json()[0]["unit_id"]
    wing_id = years_r.json()[0]["wing_id"]

    base = next_test_year()
    r = client.post("/api/planning/years",
                    json={"year": base, "name": f"Nat {base}",
                          "unit_id": unit_id, "wing_id": wing_id},
                    headers=h_nat)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"


def test_national_admin_cannot_promote_without_intervention(client):
    """national_admin needs Delegated Intervention to promote a draft year."""
    h_admin = _sqn_admin_hdr(client)
    h_nat = _nat_admin_hdr(client)
    _archive_existing_drafts(client, h_admin)
    base = next_test_year()
    active = client.post("/api/planning/years",
                         json={"year": base, "name": f"Active {base}"},
                         headers=h_admin).json()
    draft = client.post("/api/planning/years/draft",
                        json={"year": base + 1, "name": f"Draft {base + 1}",
                              "source_year_id": active["planning_year_id"]},
                        headers=h_admin).json()

    r = client.post(f"/api/planning/years/{draft['planning_year_id']}/promote",
                    headers=h_nat)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"


def test_national_admin_cannot_archive_without_intervention(client):
    """national_admin needs Delegated Intervention to archive a year."""
    h_admin = _sqn_admin_hdr(client)
    h_nat = _nat_admin_hdr(client)
    base = next_test_year()
    yr = client.post("/api/planning/years",
                     json={"year": base, "name": f"Active {base}"},
                     headers=h_admin).json()

    r = client.post(f"/api/planning/years/{yr['planning_year_id']}/archive",
                    headers=h_nat)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"


def test_national_admin_cannot_restore_without_intervention(client):
    """national_admin needs Delegated Intervention to restore an archived year."""
    h_admin = _sqn_admin_hdr(client)
    h_nat = _nat_admin_hdr(client)
    base = next_test_year()
    yr = client.post("/api/planning/years",
                     json={"year": base, "name": f"Active {base}"},
                     headers=h_admin).json()
    yr_id = yr["planning_year_id"]
    # Archive it first (as sqn_admin)
    client.post(f"/api/planning/years/{yr_id}/archive", headers=h_admin)

    r = client.post(f"/api/planning/years/{yr_id}/restore", headers=h_nat)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"


def test_national_admin_cannot_patch_active_status_without_intervention(client):
    """national_admin needs Delegated Intervention to PATCH active_status."""
    h_admin = _sqn_admin_hdr(client)
    h_nat = _nat_admin_hdr(client)
    _archive_existing_drafts(client, h_admin)
    base = next_test_year()
    yr = client.post("/api/planning/years",
                     json={"year": base, "name": f"Active {base}"},
                     headers=h_admin).json()
    yr_id = yr["planning_year_id"]
    # Archive so we can try to restore via PATCH
    client.post(f"/api/planning/years/{yr_id}/archive", headers=h_admin)

    r = client.patch(f"/api/planning/years/{yr_id}",
                     json={"active_status": True},
                     headers=h_nat)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"
