"""Phase 2: bulk account archive/restore.

Covers: batch archive happy path, already-archived detection, self-exclusion,
the last-active-System-Administrator guard (batch and single-account),
out-of-scope per-account failure, mandatory reason + session-revocation
confirmation, batch audit correlation, restore round-trip, and archived-list
filtering.
"""
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _wing_admin_7wg(client):
    return login(client, "ADMIN7WG")


def _sqn_id_by_code(client, hdr, code):
    r = client.get("/api/squadrons", headers=hdr)
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    raise AssertionError(f"squadron {code} not found")


def _create_account(client, hdr, display_name, role, **scope):
    body = {"display_name": display_name, "role": role, **scope}
    r = client.post("/api/accounts", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["user_id"]


def test_batch_archive_happy_path(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    u1 = _create_account(client, hdr, "Batch Test One", "sqn_general", squadron_id=sqn_id)
    u2 = _create_account(client, hdr, "Batch Test Two", "sqn_general", squadron_id=sqn_id)

    r = client.post("/api/accounts/batch-archive", json={
        "account_ids": [u1, u2], "reason": "Redundant test accounts cleanup",
        "confirm_session_revocation": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["summary"]["archived"] == 2
    assert d["batch_id"]
    results_by_id = {x["account_id"]: x for x in d["results"]}
    assert results_by_id[u1]["result"] == "archived"
    assert results_by_id[u2]["result"] == "archived"

    listed = client.get("/api/accounts", headers=hdr).json()
    assert not any(a["user_id"] == u1 for a in listed)
    archived_listed = client.get("/api/accounts?include_archived=true", headers=hdr).json()
    match = next(a for a in archived_listed if a["user_id"] == u1)
    assert match["is_archived"] is True
    assert match["active_status"] is False


def test_batch_archive_reports_already_archived(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    u1 = _create_account(client, hdr, "Already Archived Test", "sqn_general", squadron_id=sqn_id)
    client.post(f"/api/accounts/{u1}/archive", json=None, headers=hdr, params={"reason": "pre-archive"})

    r = client.post("/api/accounts/batch-archive", json={
        "account_ids": [u1], "reason": "Second attempt on the same account",
        "confirm_session_revocation": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["result"] == "already_archived"
    assert r.json()["summary"]["archived"] == 0


def test_batch_archive_skips_caller_self_with_visible_reason(client):
    hdr = _sysadmin(client)
    me = client.get("/api/accounts", headers=hdr).json()
    # Find the sysadmin's own account id via /api/auth/me equivalent — use
    # the accounts list filtered to system_admin role and match by exclusion
    # isn't reliable across seeded data, so instead assert indirectly: try to
    # batch-archive an id equal to no real account plus a genuine self-test
    # via the single-account endpoint's existing self-guard is out of scope
    # here -- verify via the batch path using the principal's own user_id.
    import jwt as _jwt
    token = hdr["Authorization"].split(" ")[1]
    payload = _jwt.decode(token, options={"verify_signature": False})
    my_uid = payload["sub"]

    r = client.post("/api/accounts/batch-archive", json={
        "account_ids": [my_uid], "reason": "Attempting to archive myself",
        "confirm_session_revocation": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["results"][0]["result"] == "skipped"
    assert d["results"][0]["reason"] == "cannot_archive_self"
    assert d["summary"]["archived"] == 0


def test_batch_archive_never_drives_active_admin_count_to_zero(client):
    """The real guarantee this feature provides: no matter how many OTHER
    system_admin accounts a batch targets, at least one (the acting admin)
    always remains active afterwards -- the count can never reach zero.

    Note on the explicit "last_active_system_admin" skip branch in
    batch_archive_accounts: it is deliberately unreachable through this HTTP
    endpoint under normal use, and that is by design, not a bug. Reaching it
    would require an archiving actor whose own account is NOT counted as an
    active system_admin -- but get_principal() re-checks active_status on
    every single request, so the actor is always active for the whole
    duration of their own request, and the actor's own id is always excluded
    from the target list (the separate "cannot_archive_self" check, tested
    above). Together those two invariants put a floor of 1 under the count
    that no single authenticated request can cross. The branch is kept as
    defence-in-depth for any future caller of this same function that
    doesn't go through this exact request lifecycle (e.g. an internal script),
    not because it's exercised today."""
    hdr = _sysadmin(client)
    actor_uid = _create_account(client, hdr, "Floor Test Actor", "system_admin", new_code="FLOORACTOR2026")
    _create_account(client, hdr, "Floor Test B", "system_admin", new_code="FLOORB2026")
    _create_account(client, hdr, "Floor Test C", "system_admin", new_code="FLOORC2026")
    actor_hdr = login(client, "FLOORACTOR2026")

    all_active_admins = client.get("/api/accounts?role=system_admin&active_status=true", headers=actor_hdr).json()
    others = [a["user_id"] for a in all_active_admins if a["user_id"] != actor_uid]
    assert len(others) >= 2  # at least the two Floor Test accounts plus whatever was already seeded

    try:
        r = client.post("/api/accounts/batch-archive", json={
            "account_ids": others, "reason": "Attempting to archive every other admin at once",
            "confirm_session_revocation": True,
        }, headers=actor_hdr)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["summary"]["archived"] == len(others)  # every OTHER admin succeeds -- none skipped

        still_active = client.get("/api/accounts?role=system_admin&active_status=true", headers=actor_hdr).json()
        assert len(still_active) == 1
        assert still_active[0]["user_id"] == actor_uid  # the actor themselves is always the floor
    finally:
        # conftest's _seed fixture is session-scoped -- the same DB is reused
        # across this whole pytest invocation, and this test just archived
        # the real seeded SYSADMIN2026 account (it was one of `others`). Every
        # later test in the file/run that logs in as SYSADMIN2026 would
        # otherwise 401. Restore everything this test archived so the shared
        # DB is left exactly as this test found it.
        for uid in others:
            client.post(f"/api/accounts/{uid}/restore", headers=actor_hdr)


def test_batch_archive_requires_reason_of_minimum_length(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    u1 = _create_account(client, hdr, "Short Reason Test", "sqn_general", squadron_id=sqn_id)
    r = client.post("/api/accounts/batch-archive", json={
        "account_ids": [u1], "reason": "short", "confirm_session_revocation": True,
    }, headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "reason_required"


def test_batch_archive_requires_session_revocation_confirmation(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    u1 = _create_account(client, hdr, "No Confirm Test", "sqn_general", squadron_id=sqn_id)
    r = client.post("/api/accounts/batch-archive", json={
        "account_ids": [u1], "reason": "A perfectly good reason here",
    }, headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "session_revocation_not_confirmed"


def test_batch_archive_out_of_scope_account_reported_as_failed_not_silently_skipped(client):
    """A Wing Admin attempting to archive an account outside their Wing must
    get an explicit failed result for that item, not a silent drop or a
    whole-batch 403 that hides which item was the problem."""
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")  # 703 is in 7WG
    u1 = _create_account(client, hdr, "Out Of Scope Test", "sqn_general", squadron_id=sqn_id)

    r2 = client.post("/api/wings", json={"code": "BAWG1", "name": "BA Test Wing"}, headers=hdr)
    other_wing_id = r2.json()["wing_id"]
    r3 = client.post("/api/accounts", json={"display_name": "Other Wing Admin", "role": "wing_admin",
                                            "wing_id": other_wing_id, "new_code": "OTHERWINGADM01"}, headers=hdr)
    assert r3.status_code == 200, r3.text
    other_wing_admin_hdr = login(client, "OTHERWINGADM01")

    r = client.post("/api/accounts/batch-archive", json={
        "account_ids": [u1], "reason": "Attempting cross-wing archive",
        "confirm_session_revocation": True,
    }, headers=other_wing_admin_hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["results"][0]["result"] == "failed"
    assert d["results"][0]["reason"] == "out_of_scope"

    # The account must be unaffected.
    listed = client.get("/api/accounts", headers=hdr).json()
    assert any(a["user_id"] == u1 and a["active_status"] for a in listed)


def test_batch_archive_writes_one_correlated_batch_id_across_rows(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    u1 = _create_account(client, hdr, "Audit Correlation One", "sqn_general", squadron_id=sqn_id)
    u2 = _create_account(client, hdr, "Audit Correlation Two", "sqn_general", squadron_id=sqn_id)

    r = client.post("/api/accounts/batch-archive", json={
        "account_ids": [u1, u2], "reason": "Testing batch audit correlation",
        "confirm_session_revocation": True,
    }, headers=hdr)
    batch_id = r.json()["batch_id"]

    auditor_hdr = login(client, "AUDITOR2026")
    audit_rows = client.get(f"/api/system/audit-summary?action=batch_archive&limit=10", headers=auditor_hdr).json()
    assert audit_rows["count"] >= 1

    # GET /api/audit?batch_id=... returns every row this batch wrote -- one
    # per archived account plus the batch-level summary row -- so the
    # frontend wizard's "View batch audit" step can show a correlated view
    # without the caller having to know each individual account_id up front.
    correlated = client.get(f"/api/audit?batch_id={batch_id}", headers=auditor_hdr).json()
    assert len(correlated) == 3  # u1 + u2 account_archived rows, plus 1 batch_archive summary row
    assert all(row["batch_id"] == batch_id for row in correlated)
    assert {row["action"] for row in correlated} == {"account_archived", "batch_archive"}


def test_restore_reverses_archive(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    u1 = _create_account(client, hdr, "Restore Test", "sqn_general", squadron_id=sqn_id)
    client.post("/api/accounts/batch-archive", json={
        "account_ids": [u1], "reason": "Archiving before restore test",
        "confirm_session_revocation": True,
    }, headers=hdr)

    r = client.post(f"/api/accounts/{u1}/restore", headers=hdr)
    assert r.status_code == 200, r.text

    listed = client.get("/api/accounts", headers=hdr).json()
    match = next(a for a in listed if a["user_id"] == u1)
    assert match["is_archived"] is False
    assert match["active_status"] is True


def test_single_archive_endpoint_never_drives_active_admin_count_to_zero(client):
    """Same guarantee as test_batch_archive_never_drives_active_admin_count_to_zero,
    but through the single-account /archive endpoint: archiving every OTHER
    system_admin one at a time, in sequence, always leaves the acting admin
    active, never zero.

    The literal 409 last_active_system_admin branch in archive_account (line
    506) is unreachable through this endpoint for the identical structural
    reason as the batch endpoint's skip branch: `uid == p.user_id` is checked
    (and returns 400 cannot_archive_self) before the count check ever runs, so
    the actor never appears as the target, and the actor's own row -- always
    active for the life of their own request, per get_principal's per-request
    active_status re-check -- is itself included in
    _last_active_system_admin_count's tally. That guarantees the count the
    guard reads is always >= 1 purely from the actor's own row, so archiving
    any other single admin can never observe a pre-archive count of 1. Kept
    as defence-in-depth for callers outside this request lifecycle, not
    because today's HTTP path can trigger it."""
    hdr = _sysadmin(client)
    actor_uid = _create_account(client, hdr, "Solo Guard Test Actor", "system_admin", new_code="SOLOACTOR2026")
    _create_account(client, hdr, "Solo Guard Test B", "system_admin", new_code="SOLOB2026")
    _create_account(client, hdr, "Solo Guard Test C", "system_admin", new_code="SOLOC2026")
    actor_hdr = login(client, "SOLOACTOR2026")

    all_active_admins = client.get("/api/accounts?role=system_admin&active_status=true", headers=actor_hdr).json()
    others = [a["user_id"] for a in all_active_admins if a["user_id"] != actor_uid]
    assert len(others) >= 2

    try:
        for uid in others:
            r = client.post(f"/api/accounts/{uid}/archive", headers=actor_hdr,
                            params={"reason": "Archiving one other admin at a time"})
            assert r.status_code == 200, r.text

        still_active = client.get("/api/accounts?role=system_admin&active_status=true", headers=actor_hdr).json()
        assert len(still_active) == 1
        assert still_active[0]["user_id"] == actor_uid
    finally:
        for uid in others:
            client.post(f"/api/accounts/{uid}/restore", headers=actor_hdr)
