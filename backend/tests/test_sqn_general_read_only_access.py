"""sqn_general read-only access to Account Management and the Audit log.

Product decision (2026-09-28): a Squadron General user sees everything in Main
TMS read-only, including Account Management and the Audit log, scoped to their
own squadron. Writes stay refused, no access-code secret is ever returned, and
another squadron's accounts and audit rows stay invisible.
"""
from tests.conftest import login

SQN_GENERAL = "703SQN2026"
SECRET_KEYS = {"code", "code_hash", "access_code", "new_code", "hash", "plaintext"}


def _get_sqn_id(client, headers, code):
    for s in client.get("/api/squadrons", headers=headers).json():
        if s["code"] == code:
            return s["squadron_id"]
    return None


def _create_general(client, sqn_code, name):
    h_nat = login(client, "ADMINNATIONAL")
    sqn_id = _get_sqn_id(client, login(client, "ADMIN7WG"), sqn_code)
    r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": name, "role": "sqn_general", "squadron_id": sqn_id,
    })
    assert r.status_code == 200, r.text
    return r.json()["user_id"], sqn_id


# ── Account Management: read ────────────────────────────────────────────────

def test_sqn_general_can_list_own_squadron_accounts(client):
    h = login(client, SQN_GENERAL)
    own_sqn = client.get("/api/auth/me", headers=h).json()["session"]["squadron_id"]
    r = client.get("/api/accounts", headers=h)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "own squadron has seeded accounts"
    assert all(row["squadron_id"] == own_sqn for row in rows)


def test_sqn_general_account_rows_never_carry_secrets(client):
    h = login(client, SQN_GENERAL)
    r = client.get("/api/accounts", headers=h)
    assert r.status_code == 200, r.text  # otherwise the loop below passes vacuously
    rows = r.json()
    assert rows
    for row in rows:
        assert not (SECRET_KEYS & set(row)), f"secret field exposed: {SECRET_KEYS & set(row)}"


def test_sqn_general_cannot_see_other_squadron_accounts(client):
    other_uid, other_sqn = _create_general(client, "704", "SG Isolation 704")
    h = login(client, SQN_GENERAL)
    listed = client.get(f"/api/accounts?squadron_id={other_sqn}", headers=h).json()
    assert all(row["user_id"] != other_uid for row in listed)
    assert all(row["squadron_id"] != other_sqn for row in listed)
    assert client.get(f"/api/accounts/{other_uid}", headers=h).status_code == 403


def test_sqn_general_can_read_own_squadron_account_by_id(client):
    own_uid, _ = _create_general(client, "703", "SG Own 703")
    h = login(client, SQN_GENERAL)
    r = client.get(f"/api/accounts/{own_uid}", headers=h)
    assert r.status_code == 200, r.text
    assert not (SECRET_KEYS & set(r.json()))


# ── Account Management: writes stay refused ─────────────────────────────────

def test_sqn_general_account_writes_still_refused(client):
    target_uid, sqn_id = _create_general(client, "703", "SG Write Target")
    h = login(client, SQN_GENERAL)
    attempts = [
        client.post("/api/accounts", headers=h, json={
            "display_name": "Nope", "role": "sqn_general", "squadron_id": sqn_id}),
        client.patch(f"/api/accounts/{target_uid}", headers=h, json={"display_name": "Renamed"}),
        client.post(f"/api/accounts/{target_uid}/reset-code", headers=h, json={}),
        client.post(f"/api/accounts/{target_uid}/disable", headers=h, json={}),
        client.post(f"/api/accounts/{target_uid}/change-role", headers=h, json={"new_role": "sqn_admin"}),
    ]
    for r in attempts:
        assert r.status_code == 403, f"{r.request.method} {r.request.url.path} -> {r.status_code}"


# ── Audit log: read, own squadron only ──────────────────────────────────────

def test_sqn_general_can_read_own_squadron_audit_only(client):
    # Audit rows carry the ACTOR's scope, so each audited action must be taken
    # by a squadron-scoped actor: 703's admin, and a 704 admin created here.
    h_nat = login(client, "ADMINNATIONAL")
    sqn703 = _get_sqn_id(client, login(client, "ADMIN7WG"), "703")
    sqn704 = _get_sqn_id(client, login(client, "ADMIN7WG"), "704")
    r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "SG Audit 704 Admin", "role": "sqn_admin",
        "squadron_id": sqn704, "new_code": "SGAUD704ADM"})
    assert r.status_code == 200, r.text
    h704 = login(client, "SGAUD704ADM")
    h703 = login(client, "ADMIN703")
    own = client.post("/api/accounts", headers=h703, json={
        "display_name": "SG Audit Own", "role": "sqn_general", "squadron_id": sqn703})
    other = client.post("/api/accounts", headers=h704, json={
        "display_name": "SG Audit Other", "role": "sqn_general", "squadron_id": sqn704})
    assert own.status_code == 200 and other.status_code == 200, (own.text, other.text)
    own_uid, other_uid = own.json()["user_id"], other.json()["user_id"]
    h = login(client, SQN_GENERAL)
    r = client.get("/api/audit", headers=h)
    assert r.status_code == 200, r.text
    object_ids = {row["object_id"] for row in r.json()}
    assert own_uid in object_ids, "own-squadron account creation must be visible"
    assert other_uid not in object_ids, "another squadron's audit rows must stay invisible"


# ── Unauthenticated stays refused ───────────────────────────────────────────

def test_accounts_and_audit_require_authentication(client):
    assert client.get("/api/accounts").status_code == 401
    assert client.get("/api/audit").status_code == 401
