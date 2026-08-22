"""FAQ entries on Help & Reference — system_admin authors, everyone reads."""

from conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _mk(client, hdr, **kw):
    body = {"category": "General", "question": "How do I do the thing?",
            "answer_html": "<p>Like this.</p>", "sort_order": 0, "is_published": True}
    body.update(kw)
    r = client.post("/api/activities/faq", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


# ── reading ──────────────────────────────────────────────────────────────────

def test_any_signed_in_role_can_read_the_faq(client):
    _mk(client, _sysadmin(client))
    for code in ("ADMIN703", "ADMIN7WG", "ADMINNATIONAL", "AUDITOR2026", "703SQN2026"):
        r = client.get("/api/activities/faq", headers=login(client, code))
        assert r.status_code == 200, f"{code}: {r.text}"
        assert "categories" in r.json()


def test_faq_requires_authentication(client):
    assert client.get("/api/activities/faq").status_code == 401


def test_entries_come_back_grouped_by_category(client):
    hdr = _sysadmin(client)
    _mk(client, hdr, category="Parade Nights", question="Grouping A?")
    _mk(client, hdr, category="Parade Nights", question="Grouping B?")
    _mk(client, hdr, category="Accounts", question="Grouping C?")

    body = client.get("/api/activities/faq", headers=hdr).json()
    groups = {g["category"]: g for g in body["categories"]}
    assert "Parade Nights" in groups and "Accounts" in groups
    questions = [e["question"] for e in groups["Parade Nights"]["entries"]]
    assert "Grouping A?" in questions and "Grouping B?" in questions
    # Every entry in a group carries that group's category.
    assert all(e["category"] == "Parade Nights" for e in groups["Parade Nights"]["entries"])


def test_entries_are_ordered_by_sort_order_within_a_category(client):
    hdr = _sysadmin(client)
    _mk(client, hdr, category="Ordering Check", question="Third?", sort_order=30)
    _mk(client, hdr, category="Ordering Check", question="First?", sort_order=10)
    _mk(client, hdr, category="Ordering Check", question="Second?", sort_order=20)

    body = client.get("/api/activities/faq", headers=hdr).json()
    group = next(g for g in body["categories"] if g["category"] == "Ordering Check")
    assert [e["question"] for e in group["entries"]] == ["First?", "Second?", "Third?"]


def test_unpublished_entries_are_hidden_from_everyone_but_system_admin(client):
    hdr = _sysadmin(client)
    _mk(client, hdr, category="Draft Check", question="Still being written?", is_published=False)

    admin_body = client.get("/api/activities/faq", headers=hdr).json()
    assert any(e["question"] == "Still being written?"
               for g in admin_body["categories"] for e in g["entries"])

    sqn_body = client.get("/api/activities/faq", headers=login(client, "ADMIN703")).json()
    assert not any(e["question"] == "Still being written?"
                   for g in sqn_body["categories"] for e in g["entries"])


# ── authoring is system_admin only ───────────────────────────────────────────

def test_non_system_admin_cannot_create_an_entry(client):
    for code in ("ADMIN703", "ADMIN7WG", "ADMINNATIONAL", "AUDITOR2026"):
        r = client.post("/api/activities/faq",
                        json={"category": "X", "question": "Q?", "answer_html": "<p>A</p>"},
                        headers=login(client, code))
        assert r.status_code == 403, f"{code} got {r.status_code}"


def test_creating_an_entry_requires_authentication(client):
    r = client.post("/api/activities/faq", json={"question": "Q?"})
    assert r.status_code == 401


def test_non_system_admin_cannot_update_or_delete(client):
    entry = _mk(client, _sysadmin(client), question="Protected?")
    hdr = login(client, "ADMIN703")
    assert client.put(f"/api/activities/faq/{entry['id']}",
                      json={"category": "G", "question": "Hijacked?"}, headers=hdr).status_code == 403
    assert client.delete(f"/api/activities/faq/{entry['id']}", headers=hdr).status_code == 403


def test_system_admin_can_update_and_delete(client):
    hdr = _sysadmin(client)
    entry = _mk(client, hdr, question="Before edit?")

    r = client.put(f"/api/activities/faq/{entry['id']}",
                   json={"category": "Renamed", "question": "After edit?",
                         "answer_html": "<p>Updated.</p>", "sort_order": 5, "is_published": True},
                   headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["question"] == "After edit?"
    assert r.json()["category"] == "Renamed"

    assert client.delete(f"/api/activities/faq/{entry['id']}", headers=hdr).status_code == 200
    body = client.get("/api/activities/faq", headers=hdr).json()
    assert not any(e["id"] == entry["id"] for g in body["categories"] for e in g["entries"])


def test_updating_a_missing_entry_returns_404(client):
    hdr = _sysadmin(client)
    r = client.put("/api/activities/faq/does-not-exist",
                   json={"category": "G", "question": "Q?"}, headers=hdr)
    assert r.status_code == 404


def test_a_blank_question_is_rejected(client):
    r = client.post("/api/activities/faq", json={"question": "   ", "answer_html": "<p>a</p>"},
                    headers=_sysadmin(client))
    assert r.status_code == 422


# ── stored HTML is sanitised at the endpoint, not only in the browser ────────

def test_answer_html_is_sanitised_on_create(client):
    entry = _mk(client, _sysadmin(client),
                question="Sanitised on create?",
                answer_html='<p onclick="x()">Safe</p><script>alert(1)</script>')
    assert "script" not in entry["answer_html"]
    assert "onclick" not in entry["answer_html"]
    assert entry["answer_html"] == "<p>Safe</p>"


def test_answer_html_is_sanitised_on_update(client):
    hdr = _sysadmin(client)
    entry = _mk(client, hdr, question="Sanitised on update?")
    r = client.put(f"/api/activities/faq/{entry['id']}",
                   json={"category": "General", "question": "Sanitised on update?",
                         "answer_html": '<a href="javascript:alert(1)">bad</a><p>good</p>'},
                   headers=hdr)
    assert r.status_code == 200
    assert "javascript" not in r.json()["answer_html"]
    assert "good" in r.json()["answer_html"]


def test_help_and_reference_content_is_sanitised_on_save(client):
    hdr = _sysadmin(client)
    # Help content is a single shared SystemSetting row and the suite seeds once
    # per session, so this test puts back whatever it found. test_getting_help.py
    # asserts the content starts empty, and runs after this file alphabetically.
    original = client.get("/api/activities/getting-help", headers=hdr).json()["content"]
    try:
        r = client.put("/api/activities/getting-help",
                       json={"content": '<p>Keep</p><script>alert(1)</script><img src=x onerror=alert(1)>'},
                       headers=hdr)
        assert r.status_code == 200, r.text
        stored = r.json()["content"]
        assert "script" not in stored and "onerror" not in stored and "<img" not in stored
        assert "Keep" in stored

        # And it stays sanitised when read back by an ordinary user.
        read = client.get("/api/activities/getting-help", headers=login(client, "ADMIN703")).json()
        assert "script" not in read["content"]
    finally:
        client.put("/api/activities/getting-help", json={"content": original}, headers=hdr)


def test_non_system_admin_cannot_edit_help_content(client):
    r = client.put("/api/activities/getting-help", json={"content": "<p>x</p>"},
                   headers=login(client, "ADMIN703"))
    assert r.status_code == 403


# ── audit ────────────────────────────────────────────────────────────────────

def test_authoring_actions_are_audited(client):
    hdr = _sysadmin(client)
    entry = _mk(client, hdr, question="Audited?")
    client.put(f"/api/activities/faq/{entry['id']}",
               json={"category": "General", "question": "Audited, edited?"}, headers=hdr)
    client.delete(f"/api/activities/faq/{entry['id']}", headers=hdr)

    logs = client.get("/api/audit?limit=200", headers=hdr).json()
    rows = logs if isinstance(logs, list) else logs.get("items", logs.get("logs", []))
    actions = {r.get("action") for r in rows}
    assert "faq_entry_created" in actions
    assert "faq_entry_updated" in actions
    assert "faq_entry_deleted" in actions
