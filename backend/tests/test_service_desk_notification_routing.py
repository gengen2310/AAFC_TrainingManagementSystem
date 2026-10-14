"""Service Desk notification-routing regressions.

These tests pin WHO receives operational ticket mail. Credential-recovery
addresses are deliberately not part of Service Desk routing.
"""
import uuid

from app.database import SessionLocal
from app.models import ServiceDeskEmailConfig, Squadron, Wing
from tests.conftest import login


def _sqn(short_name: str) -> Squadron:
    db = SessionLocal()
    try:
        row = db.query(Squadron).filter(Squadron.short_name == short_name).first()
        assert row is not None
        # detach only the primitive values callers need by returning the row
        # after expunge, avoiding a live Session dependency.
        db.expunge(row)
        return row
    finally:
        db.close()


def test_new_ticket_routes_to_system_national_and_matching_wing_only(client, monkeypatch):
    """New-ticket operations mail is hierarchical and de-duplicated.

    A Squadron ticket goes to configured System + National + its own Wing
    support addresses. A different Wing's support address must not receive it.
    """
    import app.routers.service_desk as service_desk

    sqn = _sqn("703SQN")
    marker = uuid.uuid4().hex
    shared = f"shared-{marker}@example.com"
    matching_wing = f"matching-{marker}@example.com"
    other_wing_mail = f"other-{marker}@example.com"
    created_other_wing_id = None

    db = SessionLocal()
    try:
        other = db.query(Wing).filter(
            Wing.id != sqn.wing_id,
            Wing.is_archived == False,  # noqa: E712
        ).first()
        if other is None:
            own_wing = db.get(Wing, sqn.wing_id)
            other = Wing(
                national_id=own_wing.national_id,
                code=f"NTF{marker[:5].upper()}",
                name=f"Notification Test Wing {marker[:6]}",
                short_name=f"N{marker[:5].upper()}",
                timezone=own_wing.timezone or "Australia/Perth",
                active_status=True,
            )
            db.add(other)
            db.flush()
            created_other_wing_id = other.id

        db.add_all([
            # Same address at two higher scopes must be delivered once.
            ServiceDeskEmailConfig(scope="system", notification_email=shared),
            ServiceDeskEmailConfig(scope="national", notification_email=shared),
            ServiceDeskEmailConfig(
                scope="wing", wing_id=sqn.wing_id, notification_email=matching_wing
            ),
            ServiceDeskEmailConfig(
                scope="wing", wing_id=other.id, notification_email=other_wing_mail
            ),
        ])
        db.commit()
    finally:
        db.close()

    captured: dict = {}

    def fake_send(ticket_data, recipients):
        captured["ticket_data"] = ticket_data
        captured["recipients"] = list(recipients)

    monkeypatch.setattr(service_desk, "send_ticket_notification", fake_send)

    try:
        response = client.post("/api/service-desk/tickets", json={
            "rank": "FLTLT",
            "first_name": "Routing",
            "last_name": "Regression",
            "email": f"submitter-{marker}@example.com",
            "squadron_id": sqn.id,
            "category": "technical_error",
            "description": "Verify hierarchical Service Desk notification routing.",
        })
        assert response.status_code == 201, response.text

        recipients = captured["recipients"]
        assert recipients.count(shared) == 1
        assert matching_wing in recipients
        assert other_wing_mail not in recipients
        assert captured["ticket_data"]["email"] == f"submitter-{marker}@example.com"
    finally:
        db = SessionLocal()
        try:
            db.query(ServiceDeskEmailConfig).filter(
                ServiceDeskEmailConfig.notification_email.in_(
                    [shared, matching_wing, other_wing_mail]
                )
            ).delete(synchronize_session=False)
            if created_other_wing_id:
                db.query(Wing).filter(Wing.id == created_other_wing_id).delete(
                    synchronize_session=False
                )
            db.commit()
        finally:
            db.close()


def test_ticket_status_update_email_goes_to_submitter_not_support_config(client, monkeypatch):
    """Status/assignment workflow updates are addressed to the ticket submitter."""
    import app.routers.service_desk as service_desk

    sqn = _sqn("703SQN")
    marker = uuid.uuid4().hex
    submitter = f"submitter-{marker}@example.com"
    captured: list[tuple[dict, dict]] = []

    monkeypatch.setattr(service_desk, "send_ticket_notification", lambda *_args, **_kwargs: None)

    def fake_update(ticket_data, changed):
        captured.append((dict(ticket_data), dict(changed)))
        return True

    monkeypatch.setattr(service_desk, "send_ticket_update_notification", fake_update)

    created = client.post("/api/service-desk/tickets", json={
        "rank": "FLTLT",
        "first_name": "Update",
        "last_name": "Recipient",
        "email": submitter,
        "squadron_id": sqn.id,
        "category": "technical_error",
        "description": "Verify the submitter receives material ticket updates.",
    })
    assert created.status_code == 201, created.text

    headers = login(client, "SYSADMIN2026")
    updated = client.patch(
        f"/api/service-desk/tickets/{created.json()['ticket_id']}",
        json={"status": "in_progress"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert len(captured) == 1
    ticket_data, changed = captured[0]
    assert ticket_data["email"] == submitter
    assert changed["status"] == "in_progress"
