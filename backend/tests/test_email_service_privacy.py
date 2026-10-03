"""Service Desk email transport/privacy regressions from the post-PR65 audit."""
from app import email_service


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls = False
        self.logged_in = False
        self.sent = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return 250

    def starttls(self):
        self.tls = True
        return 220

    def login(self, user, password):
        self.logged_in = True
        return 235

    def sendmail(self, sender, recipients, message):
        self.sent.append((sender, list(recipients), message))


def test_service_desk_notification_uses_tls_and_hides_support_recipient_headers(monkeypatch):
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(email_service.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service.settings, "SMTP_USER", "")
    monkeypatch.setattr(email_service.settings, "SMTP_PASS", "")
    monkeypatch.setattr(email_service.settings, "SMTP_FROM", "no-reply@example.test")

    recipients = ["system-support@example.test", "wing-support@example.test"]
    email_service.send_ticket_notification({
        "ticket_id": "ticket-1",
        "rank": "FLTLT",
        "first_name": "Test",
        "last_name": "Reporter",
        "email": "reporter@example.test",
        "unit_name": "7 Wing",
        "category": "technical_error",
        "description": "Synthetic support ticket.",
        "created_at": "2026-09-29T12:00:00Z",
    }, recipients)

    assert len(_FakeSMTP.instances) == 1
    smtp = _FakeSMTP.instances[0]
    assert smtp.tls is True, "TLS must be negotiated even when SMTP auth is not used"
    assert smtp.logged_in is False
    assert len(smtp.sent) == 1
    sender, envelope_recipients, raw = smtp.sent[0]
    assert sender == "no-reply@example.test"
    assert envelope_recipients == recipients
    # Delivery addresses remain in the SMTP envelope, not visible message headers.
    assert "To: no-reply@example.test" in raw
    assert "system-support@example.test" not in raw
    assert "wing-support@example.test" not in raw


def test_service_desk_update_email_goes_only_to_submitter_and_excludes_admin_notes(monkeypatch):
    sent = []

    def fake_send_mail(to, subject, body):
        sent.append((to, subject, body))
        return True

    monkeypatch.setattr(email_service, "send_mail", fake_send_mail)
    ticket = {
        "ticket_id": "ticket-2",
        "email": "reporter@example.test",
        "status": "in_progress",
        "assigned_to_name": "Wing Support",
    }

    assert email_service.send_ticket_update_notification(
        ticket,
        {"status": "in_progress", "assigned_to_name": "Wing Support"},
    ) is True
    assert len(sent) == 1
    to, _subject, body = sent[0]
    assert to == "reporter@example.test"
    assert "In Progress" in body
    assert "Wing Support" in body
    assert "admin_notes" not in body

    sent.clear()
    assert email_service.send_ticket_update_notification(
        ticket,
        {"admin_notes": "Internal-only investigation details"},
    ) is True
    assert sent == []
