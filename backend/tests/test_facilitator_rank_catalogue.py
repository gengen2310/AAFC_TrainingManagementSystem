"""DEF-04: Facilitator rank canonical catalogue — GET /api/facilitators/ranks
returns the canonical AAFC rank list; rank field is normalised (whitespace
stripped, truncated to 40 chars) on create/update; non-catalogue values are
accepted (advisory, not enforced).
"""
import pytest
from tests.conftest import login

ADM = "ADMIN703"
GEN = "703SQN2026"


def _hdr(client, code):
    return login(client, code)


def test_ranks_endpoint_returns_list(client):
    h = _hdr(client, GEN)
    r = client.get("/api/facilitators/ranks", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "ranks" in data
    ranks = data["ranks"]
    assert isinstance(ranks, list)
    assert len(ranks) > 0


def test_ranks_endpoint_each_entry_has_code_label_category(client):
    h = _hdr(client, GEN)
    ranks = client.get("/api/facilitators/ranks", headers=h).json()["ranks"]
    for r in ranks:
        assert "code" in r and r["code"]
        assert "label" in r and r["label"]
        assert "category" in r and r["category"]


def test_ranks_includes_common_aafc_officer_ranks(client):
    h = _hdr(client, GEN)
    ranks = client.get("/api/facilitators/ranks", headers=h).json()["ranks"]
    codes = {r["code"] for r in ranks}
    assert "FLTLT(AAFC)" in codes
    assert "SQNLDR(AAFC)" in codes
    assert "CIV" in codes
    assert "CUO" in codes


def test_rank_normalised_on_create_strips_whitespace(client):
    h = _hdr(client, ADM)
    r = client.post("/api/facilitators", json={"last_name": "RankNorm", "current_rank": "  FLTLT(AAFC)  "}, headers=h)
    assert r.status_code == 200, r.text
    fid = r.json()["facilitator_id"]
    fac = next(f for f in client.get("/api/facilitators", headers=h).json() if f["facilitator_id"] == fid)
    assert fac["current_rank"] == "FLTLT(AAFC)"


def test_rank_normalised_on_update_strips_whitespace(client):
    h = _hdr(client, ADM)
    fid = client.post("/api/facilitators", json={"last_name": "RankUpdateNorm"}, headers=h).json()["facilitator_id"]
    r = client.patch(f"/api/facilitators/{fid}", json={"current_rank": "  CPL(AAFC)  "}, headers=h)
    assert r.status_code == 200, r.text
    fac = next(f for f in client.get("/api/facilitators", headers=h).json() if f["facilitator_id"] == fid)
    assert fac["current_rank"] == "CPL(AAFC)"


def test_non_catalogue_rank_accepted(client):
    """Rank catalogue is advisory: non-catalogue values must not be rejected."""
    h = _hdr(client, ADM)
    r = client.post("/api/facilitators", json={"last_name": "NonCatalogueRank", "current_rank": "External Guest"}, headers=h)
    assert r.status_code == 200, r.text
    fid = r.json()["facilitator_id"]
    fac = next(f for f in client.get("/api/facilitators", headers=h).json() if f["facilitator_id"] == fid)
    assert fac["current_rank"] == "External Guest"


def test_rank_truncated_to_40_chars(client):
    """Rank longer than 40 chars is silently truncated to match DB column limit."""
    h = _hdr(client, ADM)
    long_rank = "A" * 50
    r = client.post("/api/facilitators", json={"last_name": "LongRank", "current_rank": long_rank}, headers=h)
    assert r.status_code == 200, r.text
    fid = r.json()["facilitator_id"]
    fac = next(f for f in client.get("/api/facilitators", headers=h).json() if f["facilitator_id"] == fid)
    assert len(fac["current_rank"]) == 40


def test_ranks_endpoint_unauthenticated_returns_401(client):
    r = client.get("/api/facilitators/ranks")
    assert r.status_code == 401, r.text
