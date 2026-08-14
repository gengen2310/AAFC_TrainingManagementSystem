"""Tests for Wing/Squadron CRUD, unit_type, and curriculum publication by scope."""
import pytest
from conftest import login


def _get_wing_id(c, h, code="7WG"):
    wings = c.get("/api/wings", headers=h).json()
    for w in wings:
        if w["code"] == code:
            return w["wing_id"]
    raise ValueError(f"Wing {code} not found")


def _get_sqn_id(c, h, code="703"):
    sqns = c.get("/api/squadrons", headers=h).json()
    for s in sqns:
        if s["code"] == code:
            return s["squadron_id"]
    raise ValueError(f"Squadron {code} not found")


# ── Wing creation ──

def test_nat_admin_can_create_wing(client):
    h = login(client, "ADMINNATIONAL")
    r = client.post("/api/wings", headers=h, json={
        "code": "8WG", "name": "8 Wing", "short_name": "8WG"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["code"] == "8WG"
    assert "wing_id" in data


def test_system_admin_can_create_wing(client):
    h = login(client, "SYSADMIN2026")
    r = client.post("/api/wings", headers=h, json={
        "code": "9WG", "name": "9 Wing"
    })
    assert r.status_code == 200, r.text


def test_wing_admin_cannot_create_wing(client):
    h = login(client, "ADMIN7WG")
    r = client.post("/api/wings", headers=h, json={
        "code": "10WG", "name": "10 Wing"
    })
    assert r.status_code == 403, r.text


def test_sqn_admin_cannot_create_wing(client):
    h = login(client, "ADMIN703")
    r = client.post("/api/wings", headers=h, json={
        "code": "11WG", "name": "11 Wing"
    })
    assert r.status_code == 403, r.text


def test_duplicate_wing_code_rejected(client):
    h = login(client, "ADMINNATIONAL")
    # 7WG already exists in seeds
    r = client.post("/api/wings", headers=h, json={
        "code": "7WG", "name": "Duplicate Wing"
    })
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "code_exists"


def test_wing_creation_audited(client):
    h = login(client, "ADMINNATIONAL")
    r = client.post("/api/wings", headers=h, json={"code": "12WG", "name": "12 Wing"})
    assert r.status_code == 200
    wing_id = r.json()["wing_id"]
    audit = client.get("/api/audit", headers=h).json()
    found = any(a.get("object_id") == wing_id and a.get("action") == "create" for a in audit)
    assert found, "Wing creation not audited"


# ── Squadron / Specialist Unit creation ──

def test_nat_admin_can_create_standard_squadron(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": wid, "code": "TEST703A", "name": "Test Squadron A",
        "unit_type": "standard_squadron"
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["unit_type"] == "standard_squadron"


def test_nat_admin_can_create_specialist_squadron(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": wid, "code": "SPCSQ01", "name": "Specialist Squadron 1",
        "unit_type": "specialist_squadron"
    })
    assert r.status_code == 200, r.text
    assert r.json()["unit_type"] == "specialist_squadron"


def test_nat_admin_can_create_specialist_flight(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": wid, "code": "SPECFL01", "name": "Specialist Flight Alpha",
        "unit_type": "specialist_flight"
    })
    assert r.status_code == 200, r.text
    assert r.json()["unit_type"] == "specialist_flight"


def test_nat_admin_can_create_support_unit(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": wid, "code": "SUPUNIT1", "name": "Support Unit 1",
        "unit_type": "support_unit"
    })
    assert r.status_code == 200, r.text
    assert r.json()["unit_type"] == "support_unit"


def test_wing_admin_can_create_squadron_own_wing(client):
    h = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h)
    r = client.post("/api/squadrons", headers=h, json={
        "wing_id": wid, "code": "WGOWNSQ1", "name": "Wing Own Squadron",
        "unit_type": "standard_squadron"
    })
    assert r.status_code == 200, r.text


def test_wing_admin_cannot_create_squadron_another_wing(client):
    """Wing admin cannot create a unit under a different wing."""
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    # Create a second wing
    r2 = client.post("/api/wings", headers=h_nat, json={"code": "13WG", "name": "13 Wing"})
    assert r2.status_code == 200
    other_wid = r2.json()["wing_id"]
    # Wing admin tries to create squadron under 13WG
    r = client.post("/api/squadrons", headers=h_wg, json={
        "wing_id": other_wid, "code": "WRONGWG1", "name": "Wrong Wing Squadron"
    })
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "out_of_scope"


def test_sqn_admin_cannot_create_squadron(client):
    h = login(client, "ADMIN703")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h, json={
        "wing_id": wid, "code": "SQNADMIN1", "name": "SQN Admin Cannot Create"
    })
    assert r.status_code == 403, r.text


def test_duplicate_squadron_code_rejected(client):
    h = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h, json={
        "wing_id": wid, "code": "703", "name": "Duplicate"
    })
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "code_exists"


def test_squadron_creation_audited(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": wid, "code": "AUDSQ01", "name": "Audit Test Squadron"
    })
    assert r.status_code == 200
    sqn_id = r.json()["squadron_id"]
    audit = client.get("/api/audit", headers=h_nat).json()
    found = any(a.get("object_id") == sqn_id and a.get("action") == "create" for a in audit)
    assert found, "Squadron creation not audited"


def test_invalid_unit_type_falls_back_to_standard(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": wid, "code": "INVSQ01", "name": "Invalid Unit Type Sqn",
        "unit_type": "flying_circus"
    })
    assert r.status_code == 200, r.text
    assert r.json()["unit_type"] == "standard_squadron"


def test_list_squadrons_includes_unit_type(client):
    h = login(client, "ADMIN7WG")
    sqns = client.get("/api/squadrons", headers=h).json()
    for s in sqns:
        assert "unit_type" in s, f"Squadron {s.get('code')} missing unit_type"


def test_create_squadron_returns_unit_number(client):
    """REM-107: unit_number was accepted on create and stored, but never
    echoed back by _sqn() -- so it never round-tripped to any UI. Regression
    guard for both the create response and the list endpoint."""
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": wid, "code": "UNITNO01", "name": "Unit Number Test Sqn",
        "unit_type": "specialist_flight", "unit_number": "12A"
    })
    assert r.status_code == 200, r.text
    assert r.json()["unit_number"] == "12A"
    sqns = client.get("/api/squadrons", headers=h_wg).json()
    s = next((x for x in sqns if x["code"] == "UNITNO01"), None)
    assert s is not None
    assert s["unit_number"] == "12A"


def test_patch_squadron_unit_type(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"unit_type": "specialist_squadron"})
    assert r.status_code == 200, r.text
    sqns = client.get("/api/squadrons", headers=h).json()
    s = next((x for x in sqns if x["squadron_id"] == sqn_id), None)
    assert s is not None
    assert s["unit_type"] == "specialist_squadron"
    # Restore
    client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"unit_type": "standard_squadron"})


# ── Wing rename ──

def test_nat_admin_can_rename_wing(client):
    h = login(client, "ADMINNATIONAL")
    wing_id = _get_wing_id(client, h)
    original = client.get("/api/wings", headers=h).json()
    orig_name = next(w["name"] for w in original if w["wing_id"] == wing_id)
    r = client.patch(f"/api/wings/{wing_id}", headers=h, json={"name": "7 Wing AAFC (Renamed)"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "7 Wing AAFC (Renamed)"
    # Restore
    client.patch(f"/api/wings/{wing_id}", headers=h, json={"name": orig_name})


def test_wing_rename_requires_nat_admin(client):
    h = login(client, "ADMIN7WG")
    wing_id = _get_wing_id(client, h)
    r = client.patch(f"/api/wings/{wing_id}", headers=h, json={"name": "Attempt"})
    assert r.status_code == 403


def test_wing_rename_unauthenticated(client):
    # Auth check fires before DB lookup — dummy ID is sufficient
    r = client.patch("/api/wings/00000000-0000-0000-0000-000000000000", json={"name": "Attempt"})
    assert r.status_code == 401


def test_wing_rename_empty_name_rejected(client):
    h = login(client, "ADMINNATIONAL")
    wing_id = _get_wing_id(client, h)
    r = client.patch(f"/api/wings/{wing_id}", headers=h, json={"name": "  "})
    assert r.status_code == 422


def test_wing_rename_audited(client):
    h = login(client, "ADMINNATIONAL")
    wing_id = _get_wing_id(client, h)
    original = client.get("/api/wings", headers=h).json()
    orig_name = next(w["name"] for w in original if w["wing_id"] == wing_id)
    client.patch(f"/api/wings/{wing_id}", headers=h, json={"name": "7 Wing AAFC (Audit Test)"})
    audit = client.get("/api/audit", headers=h).json()
    assert any(e.get("action") == "rename" and e.get("object_type") == "wing" for e in audit)
    # Restore
    client.patch(f"/api/wings/{wing_id}", headers=h, json={"name": orig_name})


# ── Squadron rename ──

def test_sqn_admin_can_rename_squadron(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"name": "703 Squadron AAFC (Renamed)"})
    assert r.status_code == 200, r.text
    sqns = client.get("/api/squadrons", headers=h).json()
    s = next((x for x in sqns if x["squadron_id"] == sqn_id), None)
    assert s["name"] == "703 Squadron AAFC (Renamed)"
    # Restore
    client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"name": "703 Squadron AAFC"})


def test_squadron_rename_empty_name_rejected(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"name": ""})
    assert r.status_code == 422


def test_squadron_rename_unauthenticated(client):
    r = client.patch("/api/squadrons/00000000-0000-0000-0000-000000000000", json={"name": "Attempt"})
    assert r.status_code == 401


# ── Curriculum publication scope ──

def test_wing_curriculum_visible_to_sqn_in_wing(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    h_sqn = login(client, "ADMIN703")
    # Create wing-level curriculum item
    r = client.post("/api/curriculum/wing", headers=h_wg, json={
        "code": "WC-TEST-01", "title": "Wing Test Curriculum",
        "phase": "B. Initial", "duration_minutes": 60
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    # SQN admin in same wing should see it
    curr = client.get("/api/curriculum", headers=h_sqn).json()
    ids = [i["curriculum_id"] for i in curr["items"]]
    assert cid in ids, "Wing curriculum not visible to SQN in same wing"
    # Clean up
    client.delete(f"/api/curriculum/{cid}", headers=h_wg)


def test_national_curriculum_visible_to_all(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_sqn = login(client, "ADMIN703")
    r = client.post("/api/curriculum/national", headers=h_nat, json={
        "code": "NAT-TEST-01", "title": "National Test Curriculum",
        "phase": "B. Initial", "duration_minutes": 90
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    curr = client.get("/api/curriculum", headers=h_sqn).json()
    ids = [i["curriculum_id"] for i in curr["items"]]
    assert cid in ids, "National curriculum not visible to SQN"
    # Check owning_level
    item = next(i for i in curr["items"] if i["curriculum_id"] == cid)
    assert item["owning_level"] == "national"
    client.delete(f"/api/curriculum/{cid}", headers=h_nat)


def test_wing_admin_cannot_create_national_curriculum(client):
    h = login(client, "ADMIN7WG")
    r = client.post("/api/curriculum/national", headers=h, json={
        "code": "WG-NAT-DENIED", "title": "Wing Admin Cannot Create National"
    })
    assert r.status_code == 403, r.text


def test_sqn_admin_cannot_create_wing_curriculum(client):
    h = login(client, "ADMIN703")
    r = client.post("/api/curriculum/wing", headers=h, json={
        "code": "SQN-WING-DENIED", "title": "SQN Cannot Create Wing Curriculum"
    })
    assert r.status_code == 403, r.text


def test_sqn_cannot_edit_national_curriculum(client):
    h_nat = login(client, "ADMINNATIONAL")
    h_sqn = login(client, "ADMIN703")
    r = client.post("/api/curriculum/national", headers=h_nat, json={
        "code": "NAT-READONLY-01", "title": "National Read Only"
    })
    assert r.status_code == 200
    cid = r.json()["curriculum_id"]
    edit = client.patch(f"/api/curriculum/{cid}", headers=h_sqn, json={"title": "Hacked"})
    assert edit.status_code == 403, edit.text
    delete = client.delete(f"/api/curriculum/{cid}", headers=h_sqn)
    assert delete.status_code == 403, delete.text
    client.delete(f"/api/curriculum/{cid}", headers=h_nat)


def test_sqn_cannot_edit_wing_curriculum(client):
    h_wg = login(client, "ADMIN7WG")
    h_sqn = login(client, "ADMIN703")
    r = client.post("/api/curriculum/wing", headers=h_wg, json={
        "code": "WC-READONLY-01", "title": "Wing Read Only"
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    edit = client.patch(f"/api/curriculum/{cid}", headers=h_sqn, json={"title": "Hacked"})
    assert edit.status_code == 403, edit.text
    delete = client.delete(f"/api/curriculum/{cid}", headers=h_sqn)
    assert delete.status_code == 403, delete.text
    client.delete(f"/api/curriculum/{cid}", headers=h_wg)


def test_curriculum_list_includes_owning_level_and_wing_id(client):
    h = login(client, "ADMIN703")
    curr = client.get("/api/curriculum", headers=h).json()
    for item in curr["items"]:
        assert "owning_level" in item
        assert "wing_id" in item


def test_nat_admin_can_edit_national_curriculum(client):
    h = login(client, "ADMINNATIONAL")
    r = client.post("/api/curriculum/national", headers=h, json={
        "code": "NAT-EDITABLE-01", "title": "National Editable"
    })
    assert r.status_code == 200
    cid = r.json()["curriculum_id"]
    edit = client.patch(f"/api/curriculum/{cid}", headers=h, json={"title": "National Edited"})
    assert edit.status_code == 200, edit.text
    client.delete(f"/api/curriculum/{cid}", headers=h)


def test_wing_admin_can_edit_own_wing_curriculum(client):
    h = login(client, "ADMIN7WG")
    r = client.post("/api/curriculum/wing", headers=h, json={
        "code": "WC-EDITABLE-01", "title": "Wing Editable"
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    edit = client.patch(f"/api/curriculum/{cid}", headers=h, json={"title": "Wing Edited"})
    assert edit.status_code == 200, edit.text
    client.delete(f"/api/curriculum/{cid}", headers=h)


def test_nat_admin_sees_all_wing_curriculum_without_proxy(client):
    """National admin with no proxy/DI scope sees national + all-wing items."""
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    # Create a wing-level item as wing admin
    r = client.post("/api/curriculum/wing", headers=h_wg, json={
        "code": "WC-NAT-VISIBLE-01", "title": "Wing Item Nat Should See"
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    # National admin (no proxy) should see it
    curr = client.get("/api/curriculum", headers=h_nat).json()
    ids = [i["curriculum_id"] for i in curr["items"]]
    assert cid in ids, "National admin cannot see wing curriculum without proxy"
    client.delete(f"/api/curriculum/{cid}", headers=h_nat)


def test_nat_admin_can_create_wing_curriculum_with_wing_id(client):
    """National admin must supply wing_id in the body; backend uses it for ownership."""
    h_nat = login(client, "ADMINNATIONAL")
    wing_id = _get_wing_id(client, h_nat, "7WG")
    r = client.post("/api/curriculum/wing", headers=h_nat, json={
        "code": "WC-NAT-CREATED-01", "title": "NAT Creates Wing Curriculum",
        "phase": "B. Initial", "duration_minutes": 60,
        "wing_id": wing_id
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    # SQN in that wing should see it
    h_sqn = login(client, "ADMIN703")
    curr = client.get("/api/curriculum", headers=h_sqn).json()
    ids = [i["curriculum_id"] for i in curr["items"]]
    assert cid in ids, "Wing curriculum created by nat_admin not visible to SQN"
    client.delete(f"/api/curriculum/{cid}", headers=h_nat)


def test_nat_admin_wing_curriculum_without_wing_id_returns_400(client):
    """National admin without wing_id in body and no proxy context gets 400."""
    h = login(client, "ADMINNATIONAL")
    r = client.post("/api/curriculum/wing", headers=h, json={
        "code": "WC-NO-WING", "title": "Should Fail"
    })
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "no_wing_scope"


# ── JWT Secret Production Safety ──

def test_production_mode_fails_with_short_jwt_secret():
    """Settings.validate_for_production raises an error for a short JWT secret."""
    from app.config import Settings
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        JWT_SECRET="tooshort",
        COOKIE_SECURE=True,
        CORS_ALLOWED_ORIGINS="https://example.com",
        DATABASE_URL="postgresql://user:pass@host/db"
    )
    problems = s.validate_for_production()
    assert any("JWT_SECRET" in p for p in problems), \
        f"Expected JWT_SECRET validation error, got: {problems}"


def test_production_mode_fails_with_dev_jwt_secret():
    from app.config import Settings
    # "dev-only" marker in the value should be rejected even if length >= 32
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        JWT_SECRET="dev-only-change-me-in-production-aafc",  # contains "dev-only-change-me"
        COOKIE_SECURE=True,
        CORS_ALLOWED_ORIGINS="https://example.com",
        DATABASE_URL="postgresql://user:pass@host/db"
    )
    problems = s.validate_for_production()
    # Should fail because the value matches a dev_marker
    assert any("JWT_SECRET" in p for p in problems), \
        f"Dev JWT_SECRET should be rejected in production: {problems}"


def test_production_mode_passes_with_strong_jwt_secret():
    from app.config import Settings
    import secrets
    strong = secrets.token_hex(32)   # 64 hex chars, clearly not a dev marker
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=secrets.token_hex(32),
        JWT_SECRET=strong,
        COOKIE_SECURE=True,
        CORS_ALLOWED_ORIGINS="https://aafc.example.com",
        DATABASE_URL="postgresql://user:pass@host/db"
    )
    problems = s.validate_for_production()
    jwt_problems = [p for p in problems if "JWT" in p]
    assert not jwt_problems, f"Unexpected JWT problems: {jwt_problems}"


def test_dev_jwt_secret_default_is_32_bytes_or_more():
    """The hardcoded class default is ≥32 bytes to suppress InsecureKeyLengthWarning."""
    from app.config import Settings
    # Read the default directly from the model_fields, bypassing env overrides
    default_val = Settings.model_fields["JWT_SECRET"].default
    assert len(default_val.encode()) >= 32, \
        f"Default JWT_SECRET is only {len(default_val.encode())} bytes, need ≥32"


# ── Session Structure (PATCH /api/squadrons) ──

def test_sqn_admin_can_patch_own_squadron_settings(client):
    """SQN admin can update address, parade day, start/end time, and session count."""
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={
        "address": "123 Test Street",
        "default_parade_day": "Thursday",
        "default_start_time": "18:30",
        "default_end_time": "22:00",
        "default_session_count": 4,
    })
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    # Verify the values were persisted
    sqn = client.get(f"/api/squadrons/{sqn_id}", headers=h).json()
    assert sqn["address"] == "123 Test Street"
    assert sqn["default_parade_day"] == "Thursday"
    assert sqn["default_session_count"] == 4


def test_sqn_admin_can_set_and_clear_crest_url(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={
        "crest_url": "https://example.org/crests/703.png",
    })
    assert r.status_code == 200, r.text
    sqn = client.get(f"/api/squadrons/{sqn_id}", headers=h).json()
    assert sqn["crest_url"] == "https://example.org/crests/703.png"

    # Clearing with an empty string sets it back to null.
    r2 = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"crest_url": ""})
    assert r2.status_code == 200, r2.text
    sqn2 = client.get(f"/api/squadrons/{sqn_id}", headers=h).json()
    assert sqn2["crest_url"] is None


def test_crest_url_rejects_non_http_scheme(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={
        "crest_url": "javascript:alert(1)",
    })
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == "invalid_crest_url"


def test_crest_url_rejects_too_long(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={
        "crest_url": "https://example.org/" + ("x" * 500),
    })
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == "crest_url_too_long"


def test_sqn_admin_patch_settings_is_audited(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h)
    client.patch(f"/api/squadrons/{sqn_id}", headers=h, json={"address": "Audit Test Addr"})
    audit = client.get("/api/audit", headers=h).json()
    found = any(
        a.get("object_id") == sqn_id and a.get("action") == "update_settings"
        for a in audit
    )
    assert found, "Squadron settings update not audited"


def test_wing_admin_cannot_patch_squadron_without_proxy(client):
    """Wing admin must enter proxy mode before patching squadron data."""
    h_wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h_wg)
    r = client.patch(f"/api/squadrons/{sqn_id}", headers=h_wg, json={"address": "No Proxy"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


def test_sqn_admin_cannot_patch_other_squadron(client):
    """SQN admin is blocked from patching a squadron they do not own."""
    h_sqn = login(client, "ADMIN703")
    h_wg = login(client, "ADMIN7WG")
    wid = _get_wing_id(client, h_wg)
    # Create a second squadron for this test
    r2 = client.post("/api/squadrons", headers=h_wg, json={
        "wing_id": wid, "code": "PATCHTEST1", "name": "Patch Test SQN 1"
    })
    assert r2.status_code == 200
    other_sqn_id = r2.json()["squadron_id"]
    r = client.patch(f"/api/squadrons/{other_sqn_id}", headers=h_sqn, json={"address": "Hacked"})
    assert r.status_code == 403, r.text


# ── Wing account creation ──

def test_wing_admin_can_create_sqn_admin_account(client):
    """Wing admin can create a sqn_admin account for a squadron in their own wing."""
    h_wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h_wg, "703")
    wing_id = _get_wing_id(client, h_wg, "7WG")
    r = client.post("/api/accounts", headers=h_wg, json={
        "display_name": "New SQN Admin",
        "role": "sqn_admin",
        "wing_id": wing_id,
        "squadron_id": sqn_id,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "user_id" in data
    assert data["role"] == "sqn_admin"


def test_wing_admin_create_sqn_admin_without_squadron_returns_422(client):
    """Wing admin creating sqn_admin without squadron_id must get 422."""
    h_wg = login(client, "ADMIN7WG")
    wing_id = _get_wing_id(client, h_wg, "7WG")
    r = client.post("/api/accounts", headers=h_wg, json={
        "display_name": "Missing SQN",
        "role": "sqn_admin",
        "wing_id": wing_id,
    })
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == "squadron_id_required"


def test_wing_admin_can_create_wing_viewer_account(client):
    """Wing admin can create a wing_viewer account for their own wing."""
    h_wg = login(client, "ADMIN7WG")
    wing_id = _get_wing_id(client, h_wg, "7WG")
    r = client.post("/api/accounts", headers=h_wg, json={
        "display_name": "New Wing Viewer",
        "role": "wing_viewer",
        "wing_id": wing_id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "wing_viewer"


# ── Nat admin wing curriculum PATCH/DELETE (no proxy) ──

def test_nat_admin_can_patch_wing_curriculum_without_proxy(client):
    """National admin can edit wing curriculum without proxy mode."""
    h_nat = login(client, "ADMINNATIONAL")
    h_wg = login(client, "ADMIN7WG")
    wing_id = _get_wing_id(client, h_nat, "7WG")
    r = client.post("/api/curriculum/wing", headers=h_nat, json={
        "code": "WC-NAT-PATCH-01", "title": "Wing Curr For Nat Patch",
        "wing_id": wing_id,
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    patch = client.patch(f"/api/curriculum/{cid}", headers=h_nat, json={"title": "Updated by Nat"})
    assert patch.status_code == 200, patch.text
    client.delete(f"/api/curriculum/{cid}", headers=h_nat)


def test_nat_admin_can_delete_wing_curriculum_without_proxy(client):
    """National admin can delete wing curriculum without proxy mode."""
    h_nat = login(client, "ADMINNATIONAL")
    wing_id = _get_wing_id(client, h_nat, "7WG")
    r = client.post("/api/curriculum/wing", headers=h_nat, json={
        "code": "WC-NAT-DEL-01", "title": "Wing Curr For Nat Delete",
        "wing_id": wing_id,
    })
    assert r.status_code == 200, r.text
    cid = r.json()["curriculum_id"]
    delete = client.delete(f"/api/curriculum/{cid}", headers=h_nat)
    assert delete.status_code == 200, delete.text


def test_national_viewer_can_read_audit_log(client):
    """F-FUNC-01 regression: national_viewer must get 200 from GET /api/audit (not 403)."""
    h = login(client, "NATIONAL2026")
    r = client.get("/api/audit", headers=h)
    assert r.status_code == 200, f"national_viewer got {r.status_code}: {r.text}"
    assert isinstance(r.json(), list)


def test_national_viewer_audit_is_read_only(client):
    """national_viewer must not be able to call write endpoints (confirmation that access is read-only)."""
    h = login(client, "NATIONAL2026")
    # Attempt to create a wing (write operation) — must still be denied
    r = client.post("/api/wings", headers=h, json={"code": "TEST", "name": "Test Wing"})
    assert r.status_code == 403
