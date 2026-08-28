"""POST /api/planning/years/copy-setup — configuration copy without rollover.

Creating a year is no longer part of the operation: the year already exists as
calendar context, so this materialises its container and seeds configuration.
"""
from tests.conftest import login, next_test_year


def _classes(client, hdr, year_id):
    r = client.get(f"/api/training-classes?training_year_id={year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_source(client, hdr):
    """A materialised source year. Creating it via the API also auto-creates the
    five standard training classes, which is the structure worth copying."""
    year = next_test_year()
    r = client.post("/api/planning/years",
                    json={"year": year, "name": f"{year} Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return year, r.json()["planning_year_id"]


def test_copy_setup_copies_class_structure_into_a_derived_year(client):
    hdr = login(client, "ADMIN703")
    src, src_id = _make_source(client, hdr)
    tgt = src + 1
    source_names = sorted(c["display_name"] for c in _classes(client, hdr, src_id))
    assert source_names, "the source year must have classes to copy"

    r = client.post("/api/planning/years/copy-setup", headers=hdr, json={
        "source_year": src, "target_year": tgt,
        "copy_classes": True, "copy_parade_pattern": False})
    assert r.status_code == 200, r.text
    tgt_id = r.json()["planning_year_id"]

    rows = client.get("/api/planning/years", headers=hdr).json()
    tgt_row = next(y for y in rows if y["year"] == tgt)
    assert tgt_row["materialised"] is True
    assert tgt_row["name"] == f"{tgt} Training Year"   # derived
    assert "→" not in tgt_row["name"], "no arrowed rollover name"

    copied = _classes(client, hdr, tgt_id)
    assert sorted(c["display_name"] for c in copied) == source_names
    assert all(c["training_year_id"] == tgt_id for c in copied)
    src_ids = {c["training_class_id"] for c in _classes(client, hdr, src_id)}
    assert not ({c["training_class_id"] for c in copied} & src_ids), "must be new rows, not moved"


def test_copy_setup_never_copies_sessions(client):
    hdr = login(client, "ADMIN703")
    src, _ = _make_source(client, hdr)
    r = client.post("/api/planning/years/copy-setup", headers=hdr, json={
        "source_year": src, "target_year": src + 1,
        "copy_classes": True, "copy_parade_pattern": True})
    assert r.status_code == 200, r.text
    assert r.json()["sessions_copied"] == 0


def test_copy_setup_is_idempotent_and_creates_no_second_container(client):
    hdr = login(client, "ADMIN703")
    src, _ = _make_source(client, hdr)
    tgt = src + 1
    a = client.post("/api/planning/years/copy-setup", headers=hdr, json={
        "source_year": src, "target_year": tgt, "copy_classes": False}).json()
    b = client.post("/api/planning/years/copy-setup", headers=hdr, json={
        "source_year": src, "target_year": tgt, "copy_classes": False}).json()
    assert a["planning_year_id"] == b["planning_year_id"]
    rows = client.get("/api/planning/years", headers=hdr).json()
    assert len([y for y in rows if y["year"] == tgt]) == 1


def test_copy_setup_rejects_an_unconfigured_source(client):
    hdr = login(client, "ADMIN703")
    unused = next_test_year()
    r = client.post("/api/planning/years/copy-setup", headers=hdr, json={
        "source_year": unused, "target_year": unused + 1, "copy_classes": True})
    assert r.status_code == 404, r.text


def test_rollover_no_longer_arrows_the_year_name(client):
    """Regression for the production defect: rollover named the new year
    "2026 Training Year -> 2027". A year's name is not a provenance record."""
    hdr = login(client, "ADMIN703")
    src, src_id = _make_source(client, hdr)
    r = client.post(f"/api/planning/years/{src_id}/rollover", headers=hdr,
                    json={"target_year": src + 1})
    assert r.status_code == 200, r.text
    rows = client.get("/api/planning/years", headers=hdr).json()
    new_row = next(y for y in rows if y["year"] == src + 1)
    assert new_row["name"] == f"{src + 1} Training Year"
    assert "→" not in new_row["name"]
