"""Cadet CSV import rollback (import audit, brief §46-49). Proven defects:
- Planning Workspace's Imports page sends POST /api/import/rollback with a JSON
  body {import_id}; the endpoint read import_id only from the query string, so
  every PW rollback failed with 422 "missing query import_id".
- Rollback archived EVERY cadet the importing user had created in that squadron
  since the import started (created_by + created_at >= log time, no upper
  bound) -- including cadets added by hand or by a later import.
- A rolled-back import could be rolled back again.
"""
from app.database import SessionLocal
from app.models import Cadet
from tests.conftest import login, next_test_year


def _import(client, h, *names):
    rows = "\n".join(f"{next_test_year()},{n},Imported{n}" for n in names)
    r = client.post("/api/import/commit", headers=h,
                    json={"import_type": "cadets", "csv_text": "service_number,first_name,last_name\n" + rows})
    assert r.status_code == 200, r.text
    return r.json()["import_id"]


def _active(last_name):
    db = SessionLocal()
    try:
        return [c.id for c in db.query(Cadet).filter(Cadet.last_name == last_name,
                                                     Cadet.is_archived == False).all()]  # noqa: E712
    finally:
        db.close()


def test_rollback_accepts_the_json_body_the_planning_workspace_sends(client):
    h = login(client, "ADMIN703")
    tag = f"Rb{next_test_year()}"
    iid = _import(client, h, tag)
    r = client.post("/api/import/rollback", headers=h, json={"import_id": iid})
    assert r.status_code == 200, r.text
    assert r.json()["archived"] == 1
    assert _active(f"Imported{tag}") == []


def test_rollback_archives_only_this_imports_cadets(client):
    h = login(client, "ADMIN703")
    a, b = f"Ra{next_test_year()}", f"Rc{next_test_year()}"
    first = _import(client, h, a)
    manual = client.post("/api/cadets", headers=h, json={"first_name": "Hand", "last_name": f"Manual{a}"})
    assert manual.status_code == 201, manual.text
    _import(client, h, b)                                             # a later import

    r = client.post("/api/import/rollback", headers=h, json={"import_id": first})
    assert r.status_code == 200, r.text
    assert r.json()["archived"] == 1, r.json()
    assert _active(f"Imported{a}") == []
    assert len(_active(f"Manual{a}")) == 1, "a cadet added by hand afterwards must survive"
    assert len(_active(f"Imported{b}")) == 1, "a later import's cadets must survive"


def test_a_rolled_back_import_cannot_be_rolled_back_again(client):
    h = login(client, "ADMIN703")
    iid = _import(client, h, f"Rr{next_test_year()}")
    assert client.post(f"/api/import/rollback?import_id={iid}", headers=h).status_code == 200  # query form kept
    r = client.post("/api/import/rollback", headers=h, json={"import_id": iid})
    assert r.status_code == 409, r.text
