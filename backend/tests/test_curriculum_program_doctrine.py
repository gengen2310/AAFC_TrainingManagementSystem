"""Part 41 — curriculum scope, after CurriculumItem became canonical.

ProgramItem was retired on 2026-08-30 (user decision): its 14 endpoints, service
layer and seed data are gone, and CurriculumItem is the single curriculum entity.

Before that, the two disagreed about upward visibility, and both were live:

  services_program._can_see (spec §7, quoted in its own docstring):
      "Squadron-local items ... visible UPWARD to its Wing and to National for
       oversight."
  routers/training.py's curriculum filter:
      a wing user sees national + own-wing items. Squadron-local items appear
      only if the caller names a squadron via ?squadron_id=.

CurriculumItem's rule survived, so **spec §7's upward oversight is currently
unimplemented**. That is a live question, not a settled one: retiring the model
that implemented a doctrine does not decide the doctrine. It is recorded in
docs/final/10-curriculum-vs-program.md and P41's traceability row.

These tests pin the surviving behaviour. If upward oversight is later adopted,
test_curriculum_hides_squadron_local_from_the_wing_by_default is the one to
change -- deliberately, not by accident.

Neither behaviour was ever a security fault. _view_squadron_id enforces
require_can_view_squadron, so a squadron account cannot read a peer's items;
that is pinned below and must never change.
"""
import pytest
from conftest import login


@pytest.fixture()
def local_curriculum_item(client):
    """A squadron-local CurriculumItem owned by 703."""
    from app.database import SessionLocal
    from app.models import CurriculumItem, Squadron

    db = SessionLocal()
    try:
        existing = (db.query(CurriculumItem)
                    .filter(CurriculumItem.identifier == "P41-LOCAL-01").first())
        if existing:
            return existing.id, existing.squadron_id
        s703 = db.query(Squadron).filter(Squadron.code == "703").first()
        item = CurriculumItem(
            owning_level="squadron", squadron_id=s703.id, wing_id=s703.wing_id,
            identifier="P41-LOCAL-01", code="P41-LOCAL", part_number=1,
            title="703 Local Curriculum Item", phase="A. Orientation",
        )
        db.add(item)
        db.commit()
        return item.id, s703.id
    finally:
        db.close()


def _curriculum_ids(client, headers, squadron_id=None):
    url = "/api/curriculum" + (f"?squadron_id={squadron_id}" if squadron_id else "")
    r = client.get(url, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    return [i.get("curriculum_id") or i.get("id") for i in items]


def test_curriculum_hides_squadron_local_from_the_wing_by_default(client, local_curriculum_item):
    """Current CurriculumItem doctrine: no upward visibility without asking."""
    item_id, _ = local_curriculum_item
    assert item_id not in _curriculum_ids(client, login(client, "ADMIN7WG")), (
        "curriculum now shows squadron-local items to the wing by default -- "
        "that is the ProgramItem doctrine. If this was intended, Part 41 has "
        "been decided and this test should be updated, not deleted."
    )


def test_curriculum_shows_squadron_local_when_the_wing_names_the_squadron(client, local_curriculum_item):
    """The wing CAN see it -- it just has to select the squadron."""
    item_id, sqn_id = local_curriculum_item
    assert item_id in _curriculum_ids(client, login(client, "ADMIN7WG"), sqn_id)


def test_a_squadron_cannot_read_a_peers_curriculum(client, local_curriculum_item):
    """Whichever doctrine wins, this must never change."""
    _, sqn_703 = local_curriculum_item
    r = client.get(f"/api/curriculum?squadron_id={sqn_703}",
                   headers=login(client, "ADMIN704"))
    assert r.status_code in (403, 404), (
        f"704 read 703's curriculum scope: {r.status_code} {r.text[:200]}"
    )
