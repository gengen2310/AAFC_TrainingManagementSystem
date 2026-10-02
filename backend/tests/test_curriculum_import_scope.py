"""Curriculum import audit (brief §46-49): a unit-level import must target a unit.

The Connected CSV import offers owning_level Wing / Squadron, but
/curriculum/import(-csv) took no wing_id at all and the CSV endpoint no
squadron_id. Proven:
- a "wing" import CREATED items with wing_id NULL (owned by no Wing, so no
  Wing's curriculum shows them) and, on re-import, matched/UPDATED an existing
  wing-level item of ANY Wing with the same code -- a cross-Wing overwrite;
- a "squadron" import without squadron_id created items owned by no squadron.
"""
import io

from app.database import SessionLocal
from app.models import CurriculumItem, Wing
from tests.conftest import login, next_test_year


def _csv(code, title):
    return io.BytesIO(f"Training Phase,Experiential Code,Title\nB. Initial,{code},{title}\n".encode())


def _items(code):
    db = SessionLocal()
    try:
        return [(c.owning_level, c.wing_id, c.squadron_id, c.title)
                for c in db.query(CurriculumItem).filter(CurriculumItem.code == code).all()]
    finally:
        db.close()


def test_unit_level_import_without_a_target_unit_is_refused(client):
    h = login(client, "ADMINNATIONAL")
    code = f"SCP{next_test_year()}"
    for level in ("wing", "squadron"):
        r = client.post(f"/api/curriculum/import-csv?owning_level={level}",
                        files={"file": ("c.csv", _csv(code, "Orphan"), "text/csv")}, headers=h)
        assert r.status_code == 422, (level, r.status_code, r.text)
        r = client.post("/api/curriculum/import", headers=h, json={
            "owning_level": level, "items": [{"code": code, "title": "Orphan"}]})
        assert r.status_code == 422, (level, r.status_code, r.text)
    assert _items(code) == [], "nothing may be written"


def test_wing_import_is_scoped_to_the_named_wing(client):
    h = login(client, "ADMINNATIONAL")
    code = f"SCW{next_test_year()}"
    db = SessionLocal()
    try:
        first = db.query(Wing).filter(Wing.is_archived == False).first().id  # noqa: E712
    finally:
        db.close()
    w = client.post("/api/wings", headers=h, json={"code": code[-4:] + "W", "name": f"{code} Wing",
                                                     "timezone": "Australia/Perth"})
    assert w.status_code in (200, 201), w.text
    wings = [first, w.json()["wing_id"]]
    for wid, title in ((wings[0], "Wing A version"), (wings[1], "Wing B version")):
        r = client.post(f"/api/curriculum/import-csv?owning_level=wing&wing_id={wid}",
                        files={"file": ("c.csv", _csv(code, title), "text/csv")}, headers=h)
        assert r.status_code == 200, r.text
    got = sorted(_items(code))
    assert got == sorted([("wing", wings[0], None, "Wing A version"),
                          ("wing", wings[1], None, "Wing B version")]), got
