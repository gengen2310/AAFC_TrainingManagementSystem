"""Every timestamp the API emits must carry a zone marker, spelled the same way.

A zone-less timestamp is parsed by browsers as LOCAL time. The AAFC TMS backend
is UTC throughout, so a bare "2026-08-22T22:55:19" was read eight hours early in
Perth, moving dates onto the wrong day either side of midnight. That shipped: the
Service Desk showed every ticket raised today as raised yesterday.

These tests guard both halves of the fix -- the column type that keeps tzinfo on
the way out of the database, and the encoder that spells it consistently.
"""

import re
from datetime import datetime, timezone

import pytest

from conftest import login

ZONED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$")
NAKED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")
# Deliberately loose, so a MALFORMED zone is caught rather than skipped. Checking
# only for a missing zone let "2026-08-22T23:04:50.478329+00:00Z" through, which
# is what four hand-built Z suffixes in service_desk.py produced once the columns
# started keeping their tzinfo.
TIMESTAMPISH = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

ENDPOINTS = [
    "/api/activities/getting-help",
    "/api/activities/faq",
    "/api/service-desk/tickets",
    "/api/setup/status",
    "/api/parade-nights",
    "/api/facilitators",
    "/api/accounts",
    "/api/audit?limit=25",
]


def _walk(node, path="$"):
    """Yield (path, value) for every string in a decoded JSON body."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


# ── the column type ──────────────────────────────────────────────────────────

def test_a_datetime_column_keeps_its_zone_across_a_database_round_trip():
    from app.database import SessionLocal, utcnow
    from app.models import FaqEntry

    db = SessionLocal()
    try:
        f = FaqEntry(category="Zone probe", question="Kept?", answer_html="<p>x</p>")
        db.add(f)
        db.commit()
        db.expire_all()          # force a genuine read back, not the cached object
        row = db.get(FaqEntry, f.id)
        assert row.created_at.tzinfo is not None, "tzinfo was dropped by the round trip"
        assert row.created_at.utcoffset().total_seconds() == 0
        assert (utcnow() - row.created_at).total_seconds() >= 0  # comparable with utcnow()
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_a_naive_value_written_directly_is_read_back_as_utc():
    # Rows written before this change are naive UTC on disk. They must come back
    # labelled, not reinterpreted as local time.
    from app.database import SessionLocal
    from app.models import FaqEntry

    db = SessionLocal()
    try:
        naive = datetime(2026, 8, 22, 22, 55, 19)
        f = FaqEntry(category="Legacy probe", question="Legacy?", answer_html="",
                     created_at=naive, updated_at=naive)
        db.add(f)
        db.commit()
        db.expire_all()
        row = db.get(FaqEntry, f.id)
        assert row.created_at == naive.replace(tzinfo=timezone.utc)
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_the_storage_format_is_unchanged_so_no_migration_is_needed():
    # The whole point of storing naive UTC is that existing rows stay readable
    # and no migration is required. If this starts failing, the change now needs
    # a migration.
    from app.database import UTCDateTime
    col = UTCDateTime()
    aware = datetime(2026, 8, 22, 22, 55, 19, tzinfo=timezone.utc)
    stored = col.process_bind_param(aware, None)
    assert stored.tzinfo is None, "values must still be written naive"
    assert stored == datetime(2026, 8, 22, 22, 55, 19)


# ── the encoder ──────────────────────────────────────────────────────────────

def test_the_encoder_spells_utc_as_z():
    import app.main  # noqa: F401  -- registering the encoder is an import side effect
    from fastapi.encoders import jsonable_encoder

    aware = datetime(2026, 8, 22, 23, 31, 12, 645879, tzinfo=timezone.utc)
    assert jsonable_encoder(aware).endswith("Z")
    # A naive value is UTC by this codebase's convention, not local time.
    assert jsonable_encoder(datetime(2026, 8, 22, 23, 31, 12, 645879)).endswith("Z")


def test_iso_z_helper_handles_none_naive_and_aware():
    from app.database import iso_z
    assert iso_z(None) is None
    assert iso_z(datetime(2026, 8, 22, 22, 55, 19)) == "2026-08-22T22:55:19Z"
    assert iso_z(datetime(2026, 8, 22, 22, 55, 19, tzinfo=timezone.utc)) == "2026-08-22T22:55:19Z"


# ── the API surface ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoints_never_return_a_bad_timestamp(client, path):
    hdr = login(client, "SYSADMIN2026")
    r = client.get(path, headers=hdr)
    if r.status_code != 200:
        pytest.skip(f"{path} returned {r.status_code} for system_admin")

    bad = []
    for p, v in _walk(r.json()):
        if not TIMESTAMPISH.match(v):
            continue
        if NAKED.match(v):
            bad.append((p, v, "no zone marker"))
        elif not ZONED.match(v):
            bad.append((p, v, "malformed zone"))
        else:
            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                bad.append((p, v, "does not parse"))
    assert not bad, f"{path} returned bad timestamps: {bad[:5]}"


def test_no_endpoint_double_stamps_the_zone(client):
    # service_desk.py hand-built its own "Z" while every other router relied on
    # the encoder. Once UTCDateTime kept tzinfo those sites emitted "+00:00Z",
    # and a check that only looked for a MISSING zone did not notice.
    hdr = login(client, "SYSADMIN2026")
    for path in ENDPOINTS:
        r = client.get(path, headers=hdr)
        if r.status_code != 200:
            continue
        for p, v in _walk(r.json()):
            if TIMESTAMPISH.match(v):
                assert "+00:00Z" not in v, f"{path} {p} has a doubled zone: {v!r}"
                assert v.count("Z") <= 1, f"{path} {p}: {v!r}"


def test_the_whole_api_spells_utc_the_same_way(client):
    # One API, one spelling. Mixed Z and +00:00 is valid ISO 8601 but makes
    # client code guess. This is what caught the audit endpoint, which formats
    # its timestamps by hand and so bypassed the encoder entirely.
    hdr = login(client, "SYSADMIN2026")
    spellings = set()
    for path in ENDPOINTS:
        r = client.get(path, headers=hdr)
        if r.status_code != 200:
            continue
        for p, v in _walk(r.json()):
            if ZONED.match(v):
                spellings.add("Z" if v.endswith("Z") else "offset")
    assert spellings, "no zoned timestamps found to compare -- the check would be vacuous"
    assert spellings == {"Z"}, f"mixed zone spellings across the API: {spellings}"


def test_a_freshly_written_timestamp_comes_back_zoned(client):
    # The end-to-end shape of the original bug: write now, read the value the
    # browser would receive.
    hdr = login(client, "SYSADMIN2026")
    original = client.get("/api/activities/getting-help", headers=hdr).json()["content"]
    try:
        r = client.put("/api/activities/getting-help", json={"content": "<p>Zone check.</p>"}, headers=hdr)
        assert r.status_code == 200, r.text
        stamp = r.json()["updated_at"]
        assert ZONED.match(stamp), f"updated_at has no zone marker: {stamp!r}"
        assert stamp.endswith("Z"), f"expected a Z suffix, got {stamp!r}"
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        assert abs((datetime.now(timezone.utc) - parsed).total_seconds()) < 120
    finally:
        client.put("/api/activities/getting-help", json={"content": original}, headers=hdr)
