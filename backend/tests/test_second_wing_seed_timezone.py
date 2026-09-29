"""second_wing_seed must create its Wing with a timezone.

Found by the 250-user multi-Wing load test (2026-09-29): the seed created the
Wing without a timezone, so every planning-year read for that Wing's squadrons
raised MissingTimezone (HTTP 500 x 4,910). The product API resolves a zone via
timezone_for_new_wing(); the seed must use the same resolver.
"""
from app.database import SessionLocal
from app.models import Squadron, Wing
from app.seeds.second_wing_seed import second_wing_seed
from app.services_year import current_year, wing_timezone


def test_second_wing_seed_sets_a_resolvable_wing_timezone(client, monkeypatch):
    # Unique codes so the shared test DB's own 1WG/101/102 fixtures are untouched.
    for k, v in {"ENVIRONMENT": "development", "WING2_CODE": "9TZ", "WING2_NAME": "9TZ Test Wing",
                 "SQN2A_CODE": "991", "SQN2B_CODE": "992"}.items():
        monkeypatch.setenv(k, v)
    second_wing_seed()

    db = SessionLocal()
    try:
        wing = db.query(Wing).filter(Wing.code == "9TZ").one()
        assert wing.timezone, "seeded Wing must carry a timezone"
        assert wing_timezone(db, wing.id)  # raises MissingTimezone if absent
        sqns = db.query(Squadron).filter(Squadron.wing_id == wing.id).all()
        assert {s.code for s in sqns} == {"991", "992"}
        for s in sqns:
            assert current_year(db, s.id)  # the exact call that 500'd under load
    finally:
        db.close()
