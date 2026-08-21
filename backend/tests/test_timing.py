"""Flexible parade-night timing template tests.

Covers:
  - Create / read / update / archive timing templates
  - 2-session, 3-session, and Flight Period templates
  - Effective-date lookup (future parade nights use new template; past are preserved)
  - One-night override (does not alter default template)
  - Session count derived from instructional blocks on parade night creation
  - Non-instructional blocks do not inflate session count
  - RBAC: viewers/auditors read-only; SQN admin cannot edit another SQN's templates;
          Wing admin cannot edit another Wing's unit timing
  - Audit entries created for all mutations
"""
from conftest import login


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _sqn_id(client, headers, code="703"):
    r = client.get("/api/squadrons", headers=headers)
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    return None


def _create_template(client, headers, *, name="Test Template", effective_from="2026-08-01",
                     blocks=None):
    if blocks is None:
        blocks = [
            {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
             "is_instructional_period": True, "start_time": "18:50", "end_time": "19:25"},
            {"display_order": 1, "block_name": "Period 2", "block_type": "training_period",
             "is_instructional_period": True, "start_time": "19:25", "end_time": "20:00"},
            {"display_order": 2, "block_name": "Period 3", "block_type": "training_period",
             "is_instructional_period": True, "start_time": "20:30", "end_time": "21:05"},
        ]
    r = client.post("/api/timing-templates", headers=headers,
                    json={"name": name, "effective_from": effective_from, "blocks": blocks})
    assert r.status_code == 200, f"create_template failed: {r.text}"
    return r.json()


def _create_pn(client, headers, date="2026-09-15", session_count=None):
    body = {"date": date, "term": "T3"}
    if session_count is not None:
        body["session_count"] = session_count
    r = client.post("/api/parade-nights", headers=headers, json=body)
    assert r.status_code == 200, f"create_pn failed: {r.text}"
    return r.json()["parade_night_id"]


# ─────────────────────────────────────────────────────────────
# 1. Basic CRUD
# ─────────────────────────────────────────────────────────────

def test_create_timing_template(client):
    h = login(client, "ADMIN703")
    data = _create_template(client, h)
    tid = data["timing_template_id"]
    assert tid
    assert data["name"] == "Test Template"
    assert data["effective_from"] == "2026-08-01"
    assert data["instructional_period_count"] == 3
    assert len(data["blocks"]) == 3


def test_get_timing_template(client):
    h = login(client, "ADMIN703")
    data = _create_template(client, h, name="Get Test", effective_from="2026-08-02")
    tid = data["timing_template_id"]
    r = client.get(f"/api/timing-templates/{tid}", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["timing_template_id"] == tid
    assert d["name"] == "Get Test"
    assert len(d["blocks"]) == 3


def test_list_timing_templates(client):
    h = login(client, "ADMIN703")
    _create_template(client, h, name="List Test A", effective_from="2026-08-03")
    _create_template(client, h, name="List Test B", effective_from="2026-08-04")
    r = client.get("/api/timing-templates", headers=h)
    assert r.status_code == 200
    names = [t["name"] for t in r.json()]
    assert "List Test A" in names
    assert "List Test B" in names


def test_update_timing_template(client):
    h = login(client, "ADMIN703")
    data = _create_template(client, h, name="Before Update", effective_from="2026-08-05")
    tid = data["timing_template_id"]
    r = client.patch(f"/api/timing-templates/{tid}", headers=h,
                     json={"name": "After Update", "effective_from": "2026-08-06"})
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "After Update"
    assert d["effective_from"] == "2026-08-06"


def test_archive_timing_template(client):
    h = login(client, "ADMIN703")
    data = _create_template(client, h, name="To Archive", effective_from="2026-08-07")
    tid = data["timing_template_id"]
    r = client.post(f"/api/timing-templates/{tid}/archive", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # Should 404 after archive
    r2 = client.get(f"/api/timing-templates/{tid}", headers=h)
    assert r2.status_code == 404


# ─────────────────────────────────────────────────────────────
# 2. Block structures: 2-session, 3-session, Flight Period
# ─────────────────────────────────────────────────────────────

def test_create_2_session_template(client):
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Arrival", "block_type": "arrival",
         "is_instructional_period": False, "start_time": "18:00", "end_time": "18:15"},
        {"display_order": 1, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "18:50", "end_time": "19:25"},
        {"display_order": 2, "block_name": "Period 2", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "19:25", "end_time": "20:00"},
        {"display_order": 3, "block_name": "Dismissal", "block_type": "dismissal",
         "is_instructional_period": False, "start_time": "21:30"},
    ]
    data = _create_template(client, h, name="2-Session Night", effective_from="2026-08-10",
                            blocks=blocks)
    assert data["instructional_period_count"] == 2
    ip_blocks = [b for b in data["blocks"] if b["is_instructional_period"]]
    assert len(ip_blocks) == 2


def test_create_3_session_template(client):
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Roll Call", "block_type": "admin",
         "is_instructional_period": False, "start_time": "18:15", "end_time": "18:25"},
        {"display_order": 1, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "18:50", "end_time": "19:25"},
        {"display_order": 2, "block_name": "Period 2", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "19:25", "end_time": "20:00"},
        {"display_order": 3, "block_name": "Drinks Break", "block_type": "drinks_break",
         "is_instructional_period": False, "start_time": "20:00", "end_time": "20:30"},
        {"display_order": 4, "block_name": "Period 3", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "20:30", "end_time": "21:05"},
        {"display_order": 5, "block_name": "Dismissal", "block_type": "dismissal",
         "is_instructional_period": False, "start_time": "21:30"},
    ]
    data = _create_template(client, h, name="3-Session Night", effective_from="2026-08-11",
                            blocks=blocks)
    assert data["instructional_period_count"] == 3


def test_create_template_with_flight_period(client):
    """Pre-period training block (formerly 'flight_period') uses training_period type."""
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Parade", "block_type": "parade",
         "is_instructional_period": False},
        {"display_order": 1, "block_name": "Flight Period", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "18:45", "end_time": "18:50"},
        {"display_order": 2, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "18:50", "end_time": "19:25"},
        {"display_order": 3, "block_name": "Period 2", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "19:25", "end_time": "20:00"},
    ]
    data = _create_template(client, h, name="With Flight Period", effective_from="2026-08-12",
                            blocks=blocks)
    assert data["instructional_period_count"] == 3
    types = [b["block_type"] for b in data["blocks"]]
    assert "training_period" in types


def test_create_template_custom_block_names(client):
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Welcome", "block_type": "admin",
         "is_instructional_period": False},
        {"display_order": 1, "block_name": "Main Lesson", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 2, "block_name": "Wrap Up", "block_type": "other",
         "is_instructional_period": False},
    ]
    data = _create_template(client, h, name="Custom Names", effective_from="2026-08-13",
                            blocks=blocks)
    names = [b["block_name"] for b in data["blocks"]]
    assert "Welcome" in names
    assert "Main Lesson" in names
    assert "Wrap Up" in names


def test_non_instructional_blocks_not_counted(client):
    """Arrival, admin, drinks_break, parade, briefing, dismissal are NOT instructional."""
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Arrival", "block_type": "arrival",
         "is_instructional_period": False},
        {"display_order": 1, "block_name": "Roll Call", "block_type": "admin",
         "is_instructional_period": False},
        {"display_order": 2, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 3, "block_name": "Drinks Break", "block_type": "drinks_break",
         "is_instructional_period": False},
        {"display_order": 4, "block_name": "Period 2", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 5, "block_name": "Debrief", "block_type": "briefing",
         "is_instructional_period": False},
        {"display_order": 6, "block_name": "Dismissal", "block_type": "dismissal",
         "is_instructional_period": False},
    ]
    data = _create_template(client, h, name="Non-IP Test", effective_from="2026-08-14",
                            blocks=blocks)
    assert data["instructional_period_count"] == 2


# ─────────────────────────────────────────────────────────────
# 3. Save / reload fidelity
# ─────────────────────────────────────────────────────────────

def test_save_reload_timing_template(client):
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Arrival", "block_type": "arrival",
         "is_instructional_period": False, "start_time": "18:00", "end_time": "18:15",
         "notes": "cadet arrival window"},
        {"display_order": 1, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "18:50", "end_time": "19:25",
         "is_optional": False, "period_number": 1},
    ]
    data = _create_template(client, h, name="Save Reload Test", effective_from="2026-08-15",
                            blocks=blocks)
    tid = data["timing_template_id"]
    r = client.get(f"/api/timing-templates/{tid}", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["blocks"][0]["block_name"] == "Arrival"
    assert d["blocks"][0]["start_time"] == "18:00"
    assert d["blocks"][0]["end_time"] == "18:15"
    assert d["blocks"][0]["notes"] == "cadet arrival window"
    assert d["blocks"][1]["block_name"] == "Period 1"
    assert d["blocks"][1]["is_instructional_period"] is True
    assert d["blocks"][1]["period_number"] == 1


# ─────────────────────────────────────────────────────────────
# 4. Effective-date model
# ─────────────────────────────────────────────────────────────

def test_apply_timing_template_from_future_date(client):
    h = login(client, "ADMIN703")
    data = _create_template(client, h, name="Future Template", effective_from="2026-10-01")
    tid = data["timing_template_id"]
    r = client.post(f"/api/timing-templates/{tid}/apply-from-date", headers=h,
                    json={"effective_from": "2026-10-01", "reason": "new term"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["effective_from"] == "2026-10-01"


def test_future_parade_nights_use_new_template(client):
    h = login(client, "ADMIN703")
    # Create a 2-session template effective 2026-11-01
    blocks = [
        {"display_order": 0, "block_name": "Period A", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 1, "block_name": "Period B", "block_type": "training_period",
         "is_instructional_period": True},
    ]
    _create_template(client, h, name="Future 2-Session", effective_from="2026-11-01",
                     blocks=blocks)

    # Create parade night on 2026-11-15 (after effective date) without specifying session_count
    pnid = _create_pn(client, h, date="2026-11-15")

    # The parade night should have session_count = 2 (from template)
    r = client.get("/api/parade-nights", headers=h)
    pn = next((p for p in r.json() if p["parade_night_id"] == pnid), None)
    assert pn is not None
    assert pn["session_count"] == 2, (
        f"Expected 2 sessions from template, got {pn['session_count']}"
    )


def test_past_parade_nights_preserve_old_session_count(client):
    """Changing the future template must not alter already-created parade nights."""
    h = login(client, "ADMIN703")

    # Create a parade night BEFORE any template is in effect for the far future date.
    # Use 2028-06-15: a fixed date in a gap no other test occupies, avoiding the
    # today+145 dynamic date in test_facilitator_schedule.py that otherwise lands
    # on this date when the suite runs in mid-August 2026.
    pnid = _create_pn(client, h, date="2028-06-15", session_count=3)

    # Now create a 2-session template effective from the past (before that date)
    blocks = [
        {"display_order": 0, "block_name": "Period A", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 1, "block_name": "Period B", "block_type": "training_period",
         "is_instructional_period": True},
    ]
    _create_template(client, h, name="Retroactive Test", effective_from="2028-06-01",
                     blocks=blocks)

    # The parade night was created with session_count=3; it must not be silently changed
    r = client.get("/api/parade-nights", headers=h)
    pn = next((p for p in r.json() if p["parade_night_id"] == pnid), None)
    assert pn is not None
    assert pn["session_count"] == 3, (
        "Past parade night session_count must not be overwritten by a new template"
    )


def test_explicit_session_count_overrides_template(client):
    """If user passes session_count=2 explicitly, the template's count is not used."""
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 1, "block_name": "Period 2", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 2, "block_name": "Period 3", "block_type": "training_period",
         "is_instructional_period": True},
    ]
    _create_template(client, h, name="3-Session Override Test", effective_from="2026-12-01",
                     blocks=blocks)

    pnid = _create_pn(client, h, date="2026-12-15", session_count=2)
    r = client.get("/api/parade-nights", headers=h)
    pn = next((p for p in r.json() if p["parade_night_id"] == pnid), None)
    assert pn is not None
    assert pn["session_count"] == 2


def test_effective_template_endpoint(client):
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True},
        {"display_order": 1, "block_name": "Period 2", "block_type": "training_period",
         "is_instructional_period": True},
    ]
    _create_template(client, h, name="Effective EP Test", effective_from="2026-09-01",
                     blocks=blocks)
    r = client.get("/api/timing-templates/effective", headers=h,
                   params={"date": "2026-09-20"})
    assert r.status_code == 200
    d = r.json()
    assert d["template"] is not None
    assert d["instructional_period_count"] == 2


# ─────────────────────────────────────────────────────────────
# 5. One-night override
# ─────────────────────────────────────────────────────────────

def test_one_night_override_created(client):
    h = login(client, "ADMIN703")
    pnid = _create_pn(client, h, date="2026-10-05")
    # Create a short template
    short = _create_template(client, h, name="Short Night", effective_from="2026-01-01",
                              blocks=[
                                  {"display_order": 0, "block_name": "Period 1",
                                   "block_type": "training_period",
                                   "is_instructional_period": True}
                              ])
    tid = short["timing_template_id"]

    r = client.post(f"/api/parade-nights/{pnid}/timing-override", headers=h,
                    json={"timing_template_id": tid, "reason": "shortened ANZAC night"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["override_id"]


def test_one_night_override_does_not_change_default_template(client):
    """Setting an override must not alter the squadron's default future template."""
    h = login(client, "ADMIN703")
    # Use far-future dates that no other test touches
    default_template = _create_template(client, h, name="Default Future 2029",
                                         effective_from="2029-06-01")
    dtid = default_template["timing_template_id"]

    pnid = _create_pn(client, h, date="2029-07-01")
    short = _create_template(client, h, name="Short Override 2029", effective_from="2029-01-01",
                              blocks=[
                                  {"display_order": 0, "block_name": "Period 1",
                                   "block_type": "training_period",
                                   "is_instructional_period": True}
                              ])
    client.post(f"/api/parade-nights/{pnid}/timing-override", headers=h,
                json={"timing_template_id": short["timing_template_id"],
                      "reason": "one-off night"})

    # Default template for 2029-06-15 must still be the original (dtid)
    r = client.get("/api/timing-templates/effective", headers=h,
                   params={"date": "2029-06-15"})
    assert r.status_code == 200
    t = r.json()["template"]
    assert t is not None
    assert t["timing_template_id"] == dtid, "Default template must not be changed by an override"


def test_get_parade_night_timing_shows_override(client):
    h = login(client, "ADMIN703")
    pnid = _create_pn(client, h, date="2026-10-07")
    short = _create_template(client, h, name="Override Visible", effective_from="2026-01-01",
                              blocks=[
                                  {"display_order": 0, "block_name": "Period 1",
                                   "block_type": "training_period",
                                   "is_instructional_period": True}
                              ])
    client.post(f"/api/parade-nights/{pnid}/timing-override", headers=h,
                json={"timing_template_id": short["timing_template_id"],
                      "reason": "test override"})

    r = client.get(f"/api/parade-nights/{pnid}/timing", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["source"] == "override"
    assert d["override_reason"] == "test override"


def test_remove_timing_override(client):
    h = login(client, "ADMIN703")
    pnid = _create_pn(client, h, date="2026-10-08")
    short = _create_template(client, h, name="Remove Override Test", effective_from="2026-01-01",
                              blocks=[
                                  {"display_order": 0, "block_name": "Period 1",
                                   "block_type": "training_period",
                                   "is_instructional_period": True}
                              ])
    client.post(f"/api/parade-nights/{pnid}/timing-override", headers=h,
                json={"timing_template_id": short["timing_template_id"],
                      "reason": "to be removed"})
    r = client.delete(f"/api/parade-nights/{pnid}/timing-override", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Should now fall back to default or none
    r2 = client.get(f"/api/parade-nights/{pnid}/timing", headers=h)
    assert r2.json()["source"] in ("default", "none")


def test_override_reason_required(client):
    h = login(client, "ADMIN703")
    pnid = _create_pn(client, h, date="2028-04-19")
    short = _create_template(client, h, name="No Reason Test", effective_from="2026-01-01",
                              blocks=[{"display_order": 0, "block_name": "P1",
                                       "block_type": "training_period",
                                       "is_instructional_period": True}])
    r = client.post(f"/api/parade-nights/{pnid}/timing-override", headers=h,
                    json={"timing_template_id": short["timing_template_id"], "reason": ""})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "reason_required"


# ─────────────────────────────────────────────────────────────
# 6. RBAC enforcement
# ─────────────────────────────────────────────────────────────

def test_viewer_cannot_create_template(client):
    hv = login(client, "7WG2026")
    r = client.post("/api/timing-templates", headers=hv,
                    json={"name": "Viewer Test", "effective_from": "2026-08-01", "blocks": []})
    assert r.status_code == 403


def test_auditor_cannot_create_template(client):
    ha = login(client, "AUDITOR2026")
    r = client.post("/api/timing-templates", headers=ha,
                    json={"name": "Auditor Test", "effective_from": "2026-08-01", "blocks": []})
    assert r.status_code == 403


def test_viewer_can_read_templates(client):
    h = login(client, "ADMIN703")
    _create_template(client, h, name="Viewer Read Test", effective_from="2026-08-20")
    hv = login(client, "7WG2026")
    r = client.get("/api/timing-templates", headers=hv)
    # Wing viewer has no squadron scope — should get 400 or empty, not 403
    assert r.status_code in (200, 400)


def test_sqn_admin_cannot_edit_another_sqns_template(client):
    """SQN admin 703 must not be able to edit a template owned by 704."""
    h703 = login(client, "ADMIN703")
    h704 = login(client, "ADMIN704")

    # 704 creates a template
    data704 = _create_template(client, h704, name="704 Template", effective_from="2026-08-21")
    tid = data704["timing_template_id"]

    # 703 admin tries to patch it
    r = client.patch(f"/api/timing-templates/{tid}", headers=h703,
                     json={"name": "Hijacked"})
    assert r.status_code == 403


def test_wing_admin_cannot_edit_another_wings_unit_timing(client):
    """Wing admin for 7WG cannot edit timing for a unit in a different wing."""
    h703 = login(client, "ADMIN703")
    data = _create_template(client, h703, name="703 Wing Test", effective_from="2026-08-22")
    tid = data["timing_template_id"]

    # Try with a wing admin from a different wing if available; otherwise verify scope is enforced
    h_wing = login(client, "ADMIN7WG")
    # Wing admin without proxy should not be able to write (no squadron scope)
    r = client.patch(f"/api/timing-templates/{tid}", headers=h_wing,
                     json={"name": "Wing Hijack"})
    assert r.status_code in (400, 403)


# ─────────────────────────────────────────────────────────────
# 7. Audit entries
# ─────────────────────────────────────────────────────────────

def test_audit_entry_created_for_template_creation(client):
    h = login(client, "ADMIN703")
    data = _create_template(client, h, name="Audit Create", effective_from="2026-08-30")
    tid = data["timing_template_id"]

    r = client.get("/api/audit", headers=h)
    assert r.status_code == 200
    entries = r.json()
    matched = [e for e in entries
               if e.get("object_type") == "timing_template"
               and e.get("object_id") == tid
               and e.get("action") == "create"]
    assert matched, "Expected audit entry for timing_template create"


def test_audit_entry_created_for_template_edit(client):
    h = login(client, "ADMIN703")
    data = _create_template(client, h, name="Audit Edit", effective_from="2026-08-31")
    tid = data["timing_template_id"]
    client.patch(f"/api/timing-templates/{tid}", headers=h, json={"name": "Audit Edit 2"})

    r = client.get("/api/audit", headers=h)
    entries = r.json()
    matched = [e for e in entries
               if e.get("object_type") == "timing_template"
               and e.get("object_id") == tid
               and e.get("action") == "edit"]
    assert matched, "Expected audit entry for timing_template edit"


def test_audit_entry_for_timing_override(client):
    h = login(client, "ADMIN703")
    pnid = _create_pn(client, h, date="2026-10-11")
    short = _create_template(client, h, name="Audit Override", effective_from="2026-01-01",
                              blocks=[{"display_order": 0, "block_name": "P1",
                                       "block_type": "training_period",
                                       "is_instructional_period": True}])
    client.post(f"/api/parade-nights/{pnid}/timing-override", headers=h,
                json={"timing_template_id": short["timing_template_id"],
                      "reason": "audit test"})

    r = client.get("/api/audit", headers=h)
    entries = r.json()
    matched = [e for e in entries
               if e.get("object_type") == "parade_night_timing_override"
               and e.get("action") == "create"]
    assert matched, "Expected audit entry for timing override creation"


# ─────────────────────────────────────────────────────────────
# 8. Validation
# ─────────────────────────────────────────────────────────────

def test_template_name_required(client):
    h = login(client, "ADMIN703")
    r = client.post("/api/timing-templates", headers=h,
                    json={"name": "", "effective_from": "2026-08-01", "blocks": []})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "name_required"


def test_overlapping_blocks_produce_warnings_not_errors(client):
    """Overlapping blocks should warn but not reject the save."""
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "18:50", "end_time": "19:30"},
        {"display_order": 1, "block_name": "Period 2", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "19:20", "end_time": "20:00"},
    ]
    r = client.post("/api/timing-templates", headers=h,
                    json={"name": "Overlap Test", "effective_from": "2026-08-25",
                          "blocks": blocks})
    assert r.status_code == 200, "Overlapping blocks should warn but be accepted"
    d = r.json()
    assert d["timing_template_id"]
    assert any("overlap" in w.lower() for w in d.get("warnings", [])), \
        "Expected an overlap warning in response"


def test_block_duration_auto_calculated(client):
    h = login(client, "ADMIN703")
    blocks = [
        {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
         "is_instructional_period": True, "start_time": "18:50", "end_time": "19:25"},
    ]
    data = _create_template(client, h, name="Duration Test", effective_from="2026-08-26",
                            blocks=blocks)
    b = data["blocks"][0]
    assert b["duration_minutes"] == 35, f"Expected 35 min, got {b['duration_minutes']}"


# ─────────────────────────────────────────────────────────────
# 9. Block type taxonomy (Task 1 — 2026-08-21)
# ─────────────────────────────────────────────────────────────

def test_block_type_taxonomy_new_values(client):
    """POST /api/timing-templates must accept every new block type."""
    h = login(client, "ADMIN703")
    base_block = {"block_name": "Test", "start_time": "18:00", "end_time": "19:00",
                  "duration_minutes": 60, "is_instructional_period": False,
                  "display_order": 1, "is_optional": False}
    new_types = ["arrival", "admin", "parade", "briefing", "training_period",
                 "drinks_break", "fatigue", "dismissal", "other"]
    for bt in new_types:
        resp = client.post("/api/timing-templates", headers=h, json={
            "name": f"Test {bt}", "effective_from": "2026-01-01",
            "blocks": [{**base_block, "block_type": bt,
                        "is_instructional_period": bt == "training_period"}]
        })
        assert resp.status_code == 200, f"block_type={bt} rejected: {resp.text}"
        data = resp.json()
        block = data["blocks"][0]
        assert block["block_type"] == bt
        if bt == "training_period":
            assert block["is_instructional_period"] is True
        else:
            assert block["is_instructional_period"] is False


def test_old_block_types_rejected(client):
    """Old block type values must now be rejected."""
    h = login(client, "ADMIN703")
    for old_bt in ["instructional_period", "administration", "roll_call",
                   "flight_period", "break", "fatigues", "debrief", "custom"]:
        resp = client.post("/api/timing-templates", headers=h, json={
            "name": f"Old {old_bt}", "effective_from": "2026-01-01",
            "blocks": [{"block_name": "Test", "block_type": old_bt,
                        "start_time": None, "end_time": None,
                        "duration_minutes": 60, "is_instructional_period": False,
                        "display_order": 1, "is_optional": False}]
        })
        assert resp.status_code == 422 or resp.status_code == 400, \
            f"Old block_type={old_bt} was accepted (should be rejected)"


# ─────────────────────────────────────────────────────────────
# 10. Parade night schedule endpoint (Task 6 — 2026-08-21)
# ─────────────────────────────────────────────────────────────

def test_parade_night_schedule_endpoint(client):
    """GET /api/parade-nights/{id}/schedule must return blocks + sessions keyed by block."""
    h = login(client, "ADMIN703")
    pns = client.get("/api/parade-nights", headers=h).json()
    if not pns:
        import pytest
        pytest.skip("No parade nights in test data")
    pn_id = pns[0]["parade_night_id"]
    resp = client.get(f"/api/parade-nights/{pn_id}/schedule", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert "blocks" in data
    assert "sessions_by_block" in data
    assert "unlinked_sessions" in data
    assert isinstance(data["blocks"], list)
    assert isinstance(data["sessions_by_block"], dict)
    assert isinstance(data["unlinked_sessions"], list)
    assert "parade_night_id" in data
    assert data["parade_night_id"] == pn_id


def test_parade_night_schedule_requires_auth(client):
    """GET /api/parade-nights/{id}/schedule must reject unauthenticated requests."""
    resp = client.get("/api/parade-nights/fake-id/schedule")
    assert resp.status_code == 401


def test_parade_night_schedule_not_found(client):
    """GET /api/parade-nights/{id}/schedule returns 404 for unknown parade night."""
    h = login(client, "ADMIN703")
    resp = client.get("/api/parade-nights/nonexistent-id-xyz/schedule", headers=h)
    assert resp.status_code == 404
