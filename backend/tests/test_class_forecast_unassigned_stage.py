"""Class forecasts must not report an unconfigured class as complete.

Creating a squadron-scoped planning year auto-creates five Training Classes
(ORI/INI/JNR/INT/SNR) with a stage_code but a NULL training_stage_id --
see planning.py::create_year. Curriculum progress is derived from the
*stage*, so those five classes legitimately have zero requirements.

The forecast's status ladder started with `if remaining_count == 0` and so
labelled every one of them "on_track" / "All requirements delivered." on the
day the year was created. That is a green light for work nobody has scoped
yet, and it is the one state a planning forecast must never invent.

Also pins the db.get(CurriculumPhase, None) guard: SQLAlchemy emits
"fully NULL primary key identity cannot load any object" and warns the
condition may raise in a future release.
"""
import uuid
import warnings

from sqlalchemy.exc import SAWarning

from tests.conftest import login, next_test_year


def _year_with_auto_classes(client, hdr):
    yr = next_test_year()
    r = client.post("/api/planning/years",
                    json={"year": yr, "name": f"{yr} Forecast Fixture"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["planning_year_id"]


def _forecasts(client, hdr, year_id):
    r = client.get(f"/api/planning/class-forecasts?year_id={year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def test_auto_created_classes_report_not_configured_not_on_track(client):
    hdr = login(client, "ADMIN703")
    yid = _year_with_auto_classes(client, hdr)

    forecasts = _forecasts(client, hdr, yid)
    assert len(forecasts) == 5, [f["class_name"] for f in forecasts]

    for fc in forecasts:
        assert fc["stage_name"] is None, fc
        assert fc["status"] == "not_configured", fc
        # The specific falsehood this test exists to prevent.
        assert "All requirements delivered" not in fc["message"], fc
        assert "Training Stage" in fc["message"], fc


def test_forecast_does_not_query_with_a_null_primary_key(client):
    """db.get(Model, None) is a no-op that SQLAlchemy warns may become an error."""
    hdr = login(client, "ADMIN703")
    yid = _year_with_auto_classes(client, hdr)

    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        r = client.get(f"/api/planning/class-forecasts?year_id={yid}", headers=hdr)
    assert r.status_code == 200, r.text


def test_curriculum_progress_does_not_query_with_a_null_primary_key(client):
    hdr = login(client, "ADMIN703")
    yid = _year_with_auto_classes(client, hdr)
    classes = client.get(f"/api/training-classes?training_year_id={yid}", headers=hdr).json()
    cid = classes[0]["training_class_id"]

    with warnings.catch_warnings():
        warnings.simplefilter("error", SAWarning)
        r = client.get(f"/api/training-classes/{cid}/curriculum-progress", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["stage_name"] is None


def test_assigning_a_stage_restores_the_normal_status_ladder(client):
    """not_configured must be a state the class can leave, not a dead end."""
    hdr = login(client, "ADMIN703")
    me = client.get("/api/auth/me", headers=hdr).json()
    sqn_id = me.get("squadron_id") or me.get("session", {}).get("squadron_id")
    assert sqn_id, me

    name = f"FORECAST-STAGE-{uuid.uuid4().hex[:10]}"
    ph = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name,
        "scope_level": "squadron", "squadron_id": sqn_id,
    }, headers=hdr)
    assert ph.status_code == 200, ph.text
    stage_id = ph.json()["phase_id"]

    yid = _year_with_auto_classes(client, hdr)
    classes = client.get(f"/api/training-classes?training_year_id={yid}", headers=hdr).json()
    cid = classes[0]["training_class_id"]

    up = client.patch(f"/api/training-classes/{cid}",
                      json={"training_stage_id": stage_id}, headers=hdr)
    assert up.status_code == 200, up.text

    fc = next(f for f in _forecasts(client, hdr, yid) if f["class_id"] == cid)
    assert fc["status"] != "not_configured", fc
    assert fc["stage_name"] == name, fc
