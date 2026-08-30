"""The curriculum export, after ProgramItem was retired (Part 41).

program-items was the ONLY export type the CSV/XLSX/PDF endpoints supported, so
retiring ProgramItem could not simply delete it -- all three would have been left
unable to export anything. The export now serves curriculum items, and
"program-items" survives as an alias so existing links do not start 400ing.

The scope assertion is the one that matters: an export that applied looser rules
than the page it exports would be a quiet disclosure channel.
"""
from conftest import login


def _csv(client, headers, export_type):
    r = client.get(f"/api/export/{export_type}.csv", headers=headers)
    assert r.status_code == 200, f"{export_type}: {r.status_code} {r.text[:200]}"
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    return lines[0], lines[1:]


def test_curriculum_export_returns_rows(client):
    header, rows = _csv(client, login(client, "ADMIN703"), "curriculum-items")
    assert header.startswith("identifier,code,title,owning_level")
    assert rows, "curriculum export produced no rows"


def test_program_items_alias_still_works(client):
    """An existing link must not start returning 400."""
    h = login(client, "ADMIN703")
    alias_header, alias_rows = _csv(client, h, "program-items")
    canon_header, canon_rows = _csv(client, h, "curriculum-items")
    assert alias_header == canon_header
    assert len(alias_rows) == len(canon_rows)


def test_unknown_export_type_still_rejected(client):
    r = client.get("/api/export/not-a-thing.csv", headers=login(client, "ADMIN703"))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "unsupported_export_type"


def test_export_does_not_leak_another_squadrons_local_item(client):
    """The export must apply the same scope rules as GET /api/curriculum."""
    from app.database import SessionLocal
    from app.models import CurriculumItem, Squadron

    db = SessionLocal()
    try:
        s703 = db.query(Squadron).filter(Squadron.code == "703").first()
        if not db.query(CurriculumItem).filter(
                CurriculumItem.identifier == "P41-EXPORT-LOCAL").first():
            db.add(CurriculumItem(
                owning_level="squadron", squadron_id=s703.id, wing_id=s703.wing_id,
                identifier="P41-EXPORT-LOCAL", code="P41-EXP", part_number=1,
                title="703 Local Export Probe", phase="A. Orientation"))
            db.commit()
    finally:
        db.close()

    _, rows_703 = _csv(client, login(client, "ADMIN703"), "curriculum-items")
    assert any("P41-EXPORT-LOCAL" in r for r in rows_703), "703 cannot see its own item"

    _, rows_704 = _csv(client, login(client, "ADMIN704"), "curriculum-items")
    assert not any("P41-EXPORT-LOCAL" in r for r in rows_704), (
        "the export leaked 703's squadron-local item to 704"
    )


def test_retired_program_endpoints_are_gone(client):
    """The duplicate entity is no longer reachable."""
    h = login(client, "ADMIN703")
    for path in ("/api/program-items", "/api/program-packages", "/api/phases",
                 "/api/learning-hub-resources", "/api/program-coverage/squadron"):
        assert client.get(path, headers=h).status_code == 404, f"{path} still served"
