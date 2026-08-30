"""Part 36 — the plan review is derived on read, and writes nothing.

"Run All Checks" makes the system's knowledge of its own state depend on the
user remembering to press a button. GET /plan-review answers the same question
on read.

It does NOT replace the persisted conflicts. A PlanningConflict carries a user's
override and the reason they typed; a derived view has nowhere to put that, so
removing persistence would delete an auditable decision. The review reports
which findings are already overridden instead.

Both come from one detector (_detect_conflicts), so the review and the recorded
conflicts cannot disagree about what counts as a conflict.
"""
from conftest import login, next_test_year


def _year_with_date(client, hdr):
    year = next_test_year()
    r = client.post("/api/planning/years",
                    json={"year": year, "name": f"{year} Year"}, headers=hdr)
    if r.status_code == 409:
        yr_id = r.json()["detail"]["existing_id"]
    else:
        assert r.status_code == 200, r.text
        yr_id = r.json()["planning_year_id"]
    existing = client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr)
    assert existing.status_code == 200, existing.text
    if existing.json():
        return yr_id, existing.json()[0]["parade_date_id"]
    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": f"{year}-09-04"}, headers=hdr)
    assert rp.status_code == 200, rp.text
    return yr_id, rp.json()["parade_date_id"]


def test_plan_review_returns_findings_without_pressing_anything(client):
    hdr = login(client, "ADMIN703")
    yr_id, _ = _year_with_date(client, hdr)
    r = client.get(f"/api/planning/years/{yr_id}/plan-review", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["planning_year_id"] == yr_id
    assert d["parade_dates_reviewed"] >= 1
    assert set(d["counts"]) == {"critical", "warning", "overridden"}
    assert d["findings"], (
        "a parade date with no sessions should raise empty_session findings; "
        "an empty review proves nothing about the endpoint"
    )


def test_plan_review_writes_nothing(client):
    """A GET must not create conflict rows -- that is the whole point."""
    hdr = login(client, "ADMIN703")
    yr_id, _ = _year_with_date(client, hdr)
    before = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr)
    assert before.status_code == 200, before.text
    n_before = len(before.json()["conflicts"])

    for _ in range(3):
        assert client.get(f"/api/planning/years/{yr_id}/plan-review",
                          headers=hdr).status_code == 200

    after = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr)
    n_after = len(after.json()["conflicts"])
    assert n_after == n_before, f"plan-review created {n_after - n_before} conflict row(s)"


def test_plan_review_agrees_with_run_checks(client):
    """One detector, so the derived review and the recorded conflicts match."""
    hdr = login(client, "ADMIN703")
    yr_id, _ = _year_with_date(client, hdr)

    review = client.get(f"/api/planning/years/{yr_id}/plan-review", headers=hdr).json()
    # GET /conflicts lists UNRESOLVED conflicts only, so compare like with like.
    derived = sorted({(f["parade_date_id"], f["conflict_type"])
                      for f in review["findings"] if not f["is_overridden"]})

    assert client.post(f"/api/planning/years/{yr_id}/run-checks",
                       headers=hdr).status_code == 200
    recorded_resp = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr)
    recorded = sorted({(c["parade_date_id"], c["conflict_type"])
                       for c in recorded_resp.json()["conflicts"]})
    assert derived == recorded, (
        f"derived review and recorded conflicts disagree:\n"
        f"  only derived : {sorted(set(derived) - set(recorded))}\n"
        f"  only recorded: {sorted(set(recorded) - set(derived))}"
    )


def test_plan_review_reports_an_override_instead_of_hiding_it(client):
    """An overridden conflict still appears, flagged, with its reason."""
    hdr = login(client, "ADMIN703")
    yr_id, _ = _year_with_date(client, hdr)
    assert client.post(f"/api/planning/years/{yr_id}/run-checks",
                       headers=hdr).status_code == 200
    conflicts = client.get(f"/api/planning/years/{yr_id}/conflicts",
                           headers=hdr).json()["conflicts"]
    assert conflicts, "no conflicts to override"
    target = conflicts[0]

    ov = client.post(f"/api/planning/conflicts/{target['conflict_id']}/override",
                     headers=hdr, json={"override_reason": "Accepted by the CO"})
    assert ov.status_code == 200, ov.text

    review = client.get(f"/api/planning/years/{yr_id}/plan-review", headers=hdr).json()
    match = [f for f in review["findings"]
             if f["parade_date_id"] == target["parade_date_id"]
             and f["conflict_type"] == target["conflict_type"]]
    assert match, "the overridden finding vanished from the review"
    assert match[0]["is_overridden"] is True
    assert match[0]["override_reason"] == "Accepted by the CO"
    assert review["counts"]["overridden"] >= 1


def test_viewer_can_read_the_review(client):
    """A review is a read. It must not require write access."""
    hdr = login(client, "ADMIN703")
    yr_id, _ = _year_with_date(client, hdr)
    r = client.get(f"/api/planning/years/{yr_id}/plan-review",
                   headers=login(client, "703SQN2026"))
    assert r.status_code == 200, r.text
