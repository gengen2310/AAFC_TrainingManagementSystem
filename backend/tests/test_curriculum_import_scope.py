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


def test_squadron_scoped_import_does_not_crash_on_facilitator_prefetch(client):
    """Any import naming a squadron pre-fetches that squadron's facilitators
    for schedule linking. It read Facilitator.display_name, which does not
    exist, so EVERY squadron-scoped import (CSV squadron level, and the XLSM
    path, which passes squadron_id) failed with 500 internal_error. Found when
    the Main TMS import gained a Squadron picker."""
    h = login(client, "ADMINNATIONAL")
    db = SessionLocal()
    try:
        from app.models import Squadron
        sqn = db.query(Squadron).filter(Squadron.code == "703").one().id
    finally:
        db.close()
    code = f"SQF{next_test_year()}"
    r = client.post(f"/api/curriculum/import-csv?owning_level=squadron&squadron_id={sqn}&preview=true",
                    files={"file": ("c.csv", _csv(code, "Squadron Prefetch"), "text/csv")}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1


def test_facilitator_name_index_uses_real_name_fields_and_skips_ambiguous_names():
    from types import SimpleNamespace as F
    from app.routers.training import _facilitator_name_index
    a = F(id="a", current_rank="FLTLT", first_name="Sam", last_name="Lee")
    b = F(id="b", current_rank=None, first_name="Kim", last_name="Ng")
    c = F(id="c", current_rank="CPL", first_name="Kim", last_name="Ng")   # same first+last as b
    idx = _facilitator_name_index([a, b, c])
    assert idx["fltlt sam lee"] == "a" and idx["sam lee"] == "a"
    assert idx["cpl kim ng"] == "c"
    assert "kim ng" not in idx, "a name two facilitators share must not link either of them"
