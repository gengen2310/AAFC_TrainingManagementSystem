"""Part 41 — CurriculumItem and ProgramItem answer the same question differently.

The installation carries two models for one concept:

  CurriculumItem  curriculum_items  ~117 router references, the model the whole
                  scheduling flow actually uses.
  ProgramItem     program_items     14 endpoints, its own service layer, tests
                  and seed data -- and essentially no UI (one CSV export link).

Both implement National -> Wing -> Squadron ownership. They do NOT agree on
upward visibility, and both are live:

  services_program._can_see (spec §7, quoted in its own docstring):
      "Squadron-local items ... visible UPWARD to its Wing and to National for
       oversight."
  routers/training.py's curriculum filter:
      a wing user sees national + own-wing items. Squadron-local items appear
      only if the caller names a squadron via ?squadron_id=.

These are characterisation tests. They lock the CURRENT behaviour of each so the
divergence is visible and cannot drift further while the canonical doctrine is
being decided. When one doctrine wins, the losing test here is the one to
change -- deliberately, not by accident.

Neither behaviour is a security fault. _view_squadron_id enforces
require_can_view_squadron, so a squadron user cannot read a peer's items through
either surface; the disagreement is about how much OVERSIGHT a wing gets by
default.
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


def test_program_items_show_squadron_local_to_the_wing_by_default(client):
    """Current ProgramItem doctrine: upward oversight, no selection needed."""
    r = client.get("/api/program-items", headers=login(client, "ADMIN7WG"))
    assert r.status_code == 200, r.text
    body = r.json()
    items = body if isinstance(body, list) else body.get("items", [])
    assert [i for i in items if i.get("owning_scope") == "squadron"], (
        "program-items no longer shows squadron-local items to the wing -- "
        "that is the CurriculumItem doctrine. See the note above."
    )


def test_a_squadron_cannot_read_a_peers_curriculum(client, local_curriculum_item):
    """Whichever doctrine wins, this must never change."""
    _, sqn_703 = local_curriculum_item
    r = client.get(f"/api/curriculum?squadron_id={sqn_703}",
                   headers=login(client, "ADMIN704"))
    assert r.status_code in (403, 404), (
        f"704 read 703's curriculum scope: {r.status_code} {r.text[:200]}"
    )
