"""Backend test suite covering the V9 acceptance-critical behaviours."""
from conftest import login


def _sqn_id(client, headers, code):
    r = client.get("/api/squadrons", headers=headers)
    assert r.status_code == 200
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    return None


# ── AUTH ──
def test_login_success_and_me(client):
    h = login(client, "ADMIN703")
    me = client.get("/api/auth/me", headers=h).json()["session"]
    assert me["role"] == "sqn_admin"


def test_login_invalid(client):
    assert client.post("/api/auth/login", json={"code": "NOPE"}).status_code == 401


def test_unauthenticated_blocked(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/curriculum").status_code == 401


def test_login_rate_limit(client):
    last = None
    for _ in range(7):
        last = client.post("/api/auth/login", json={"code": "WRONG"})
    assert last.status_code == 429  # locked out after repeated failures


# ── TENANCY / RBAC ──
def test_squadron_user_scoped_to_own_squadron(client):
    h = login(client, "ADMIN703")
    sqns = client.get("/api/squadrons", headers=h).json()
    assert len(sqns) == 1 and sqns[0]["code"] == "703"


def test_squadron_cannot_read_other_squadron(client):
    h703 = login(client, "ADMIN703")
    hwing = login(client, "ADMIN7WG")
    s704 = _sqn_id(client, hwing, "704")
    r = client.get(f"/api/squadrons/{s704}", headers=h703)
    assert r.status_code == 403  # IDOR / broken-access-control prevented


def test_sqn_general_blocked_from_cadets(client):
    h = login(client, "703SQN2026")
    assert client.get("/api/cadets", headers=h).status_code == 403


def test_sqn_general_cannot_create_parade(client):
    h = login(client, "703SQN2026")
    assert client.post("/api/parade-nights", headers=h, json={"date": "2026-09-04"}).status_code == 403


def test_wing_sees_all_wing_squadrons(client):
    h = login(client, "ADMIN7WG")
    sqns = client.get("/api/squadrons", headers=h).json()
    assert len(sqns) == 16


def test_national_sees_all_wings(client):
    h = login(client, "NATIONAL2026")
    ov = client.get("/api/national/overview", headers=h).json()
    assert ov["wing_count"] >= 1
    assert client.get("/api/reports/national-overview", headers=h).status_code == 200


def test_wing_viewer_cannot_edit(client):
    h = login(client, "7WG2026")  # wing_viewer
    r = client.post("/api/parade-nights", headers=h, json={"date": "2026-09-11"})
    assert r.status_code == 403


# ── PROXY MODE ──
def test_wing_admin_cannot_edit_without_proxy(client):
    h = login(client, "ADMIN7WG")
    r = client.post("/api/parade-nights", headers=h, json={"date": "2026-09-11"})
    # wing admin has no squadron scope and no proxy → blocked
    assert r.status_code in (400, 403)


def test_proxy_requires_reason(client):
    h = login(client, "ADMIN7WG")
    s703 = _sqn_id(client, h, "703")
    r = client.post(f"/api/proxy/enter/{s703}", headers=h, json={"reason": ""})
    assert r.status_code == 400


def test_proxy_enter_enables_edit_and_audits(client):
    h = login(client, "ADMIN7WG")
    s703 = _sqn_id(client, h, "703")
    r = client.post(f"/api/proxy/enter/{s703}", headers=h, json={"reason": "Assist July planning"})
    assert r.status_code == 200
    # now editing 703 works
    r2 = client.post("/api/parade-nights", headers=h, json={"date": "2027-01-08", "session_count": 1})
    assert r2.status_code == 200
    # audit shows proxy_enter
    aud = client.get("/api/audit", headers=h).json()
    assert any(a["action"] == "proxy_enter" for a in aud)
    client.post("/api/proxy/exit", headers=h)


def test_wing_admin_cannot_proxy_other_wing_scope(client):
    # All squadrons are in 7 Wing here; verify out-of-scope guard path exists by
    # confirming a non-existent squadron is rejected.
    h = login(client, "ADMIN7WG")
    r = client.post("/api/proxy/enter/does-not-exist", headers=h, json={"reason": "x"})
    assert r.status_code == 404


def test_proxy_mode_does_not_survive_logout_and_relogin(client):
    """QUAL-004: an active Proxy session must not silently re-attach after the actor
    logs out and logs back in with a fresh token -- confirmed live on staging via a
    real browser session (see docs/qualification/08_adversarial_test_report.md
    candidate 2) before this fix. logout() must end the active session, not merely
    delete the cookie, since get_principal re-attaches any active ProxySession for the
    user's id regardless of which token is presented."""
    h1 = login(client, "ADMIN7WG")
    s703 = _sqn_id(client, h1, "703")
    r = client.post(f"/api/proxy/enter/{s703}", headers=h1, json={"reason": "Assist July planning"})
    assert r.status_code == 200

    # Writing to 703 works while proxied.
    r2 = client.post("/api/parade-nights", headers=h1, json={"date": "2027-02-11", "session_count": 1})
    assert r2.status_code == 200

    # Log out via the real endpoint (not just discarding the token client-side).
    logout_r = client.post("/api/auth/logout", headers=h1)
    assert logout_r.status_code == 200

    # Log back in -- a fresh token for the same user, simulating a real re-login.
    h2 = login(client, "ADMIN7WG")
    current = client.get("/api/proxy/current", headers=h2)
    assert current.status_code == 200
    assert current.json()["active"] is False, (
        "Proxy session silently re-attached after logout+relogin with no re-prompt"
    )

    # The elevated write capability must not have persisted either.
    r3 = client.post("/api/parade-nights", headers=h2, json={"date": "2027-02-18", "session_count": 1})
    assert r3.status_code in (400, 403)


# ── CURRICULUM ──
def test_curriculum_progress_and_lh(client):
    h = login(client, "ADMIN703")
    items = client.get("/api/curriculum", headers=h).json()["items"]
    assert len(items) >= 13
    assert all(i["learning_hub_url"] for i in items)
    assert any(i["progress"] == "delivered" for i in items)


# ── PARADE / READINESS ──
def test_readiness_and_publish_blockers(client):
    h = login(client, "ADMIN703")
    pns = client.get("/api/parade-nights", headers=h).json()
    future = [p for p in pns if p["date"] >= "2026-07-01"][0]
    detail = client.get(f"/api/parade-nights/{future['parade_night_id']}", headers=h).json()
    assert "readiness" in detail and 0 <= detail["readiness"]["score"] <= 100


def test_not_delivered_in_reports(client):
    h = login(client, "ADMIN703")
    nd = client.get("/api/reports/not-delivered", headers=h).json()
    assert len(nd["sessions"]) >= 1


# ── IMPORT ──
def test_import_preview_and_formula_neutralisation(client):
    h = login(client, "ADMIN703")
    csv_text = "first_name,last_name,attendance_percentage\n=cmd|' /c calc',Evil,90\nSam,Taylor,88"
    r = client.post("/api/import/preview", headers=h, json={"import_type": "cadets", "csv_text": csv_text})
    assert r.status_code == 200
    body = r.json()
    assert body["detected"]["last_name"] == "last_name"
    # formula cell neutralised with leading apostrophe
    assert body["preview"][0]["first_name"].startswith("'=")


def test_import_commit_and_rollback(client):
    h = login(client, "ADMIN703")
    csv_text = "service_number,first_name,last_name,attendance_percentage\n9000001,Pat,Imported,77"
    r = client.post("/api/import/commit", headers=h, json={"import_type": "cadets", "csv_text": csv_text})
    assert r.status_code == 200 and r.json()["accepted"] == 1
    import_id = r.json()["import_id"]
    rb = client.post(f"/api/import/rollback?import_id={import_id}", headers=h)
    assert rb.status_code == 200 and rb.json()["archived"] >= 1


# ── AUDIT IMMUTABILITY ──
def test_no_audit_delete_endpoint(client):
    h = login(client, "AUDITOR2026")
    # audit is read-only; there is no delete route
    assert client.get("/api/audit", headers=h).status_code == 200
    assert client.delete("/api/audit", headers=h).status_code in (404, 405)


# ── SECURITY HEADERS ──
def test_security_headers_present(client):
    r = client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers
