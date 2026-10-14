"""SMTP email notification service for Service Desk tickets.

If SMTP_HOST is not configured, notifications are logged but not sent.
Email failure never prevents ticket creation.
"""
import logging
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import settings

logger = logging.getLogger(__name__)

_CATEGORY_LABELS = {
    "account_access": "Account Access",
    "training_data": "Training Data",
    "technical_error": "Technical Error",
    "feature_request": "Feature Request",
    "other": "Other",
}


def send_ticket_notification(ticket_data: dict, recipients: list[str]) -> None:
    """Send a ticket-submitted notification to all recipients.

    Silently logs and returns when SMTP is unconfigured or on any SMTP error,
    so ticket creation always succeeds regardless of email availability.
    """
    if not recipients:
        return

    if not settings.SMTP_HOST:
        logger.info(
            "SMTP not configured — skipping notification email for ticket %s (%d recipient(s))",
            ticket_data.get("ticket_id"),
            len(recipients),
        )
        return

    category_label = _CATEGORY_LABELS.get(ticket_data.get("category", ""), "Other")
    submitter = (
        f"{ticket_data.get('rank', '')} {ticket_data.get('first_name', '')} "
        f"{ticket_data.get('last_name', '')}"
    ).strip()

    subject = f"[AAFC TMS] New Support Ticket — {category_label}"
    body = (
        f"A new support ticket has been submitted.\n\n"
        f"Category:    {category_label}\n"
        f"Submitted:   {ticket_data.get('created_at', '')}\n"
        f"Submitted by:{submitter}\n"
        f"Unit:        {ticket_data.get('unit_name', '')}\n"
        f"Email:       {ticket_data.get('email', '')}\n\n"
        f"Description:\n{ticket_data.get('description', '')}\n\n"
        f"---\n"
        f"Log in to the AAFC TMS to view and action this ticket.\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    # Configured system/national/wing support addresses are operational
    # configuration and should not be disclosed to one another. Keep them off
    # the visible To/Cc headers and use only the SMTP envelope for delivery.
    msg["To"] = settings.SMTP_FROM
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.ehlo()
            # Service Desk content contains submitter PII and free text. Match
            # account-recovery transport semantics: always negotiate TLS when
            # SMTP is configured, regardless of whether authentication is used.
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
            smtp.sendmail(settings.SMTP_FROM, recipients, msg.as_string())
        logger.info("Ticket notification sent to %d recipients", len(recipients))
    except Exception as exc:
        logger.error("Failed to send ticket notification: %s", exc)


def send_ticket_update_notification(ticket_data: dict, changed: dict) -> bool:
    """Notify the ticket submitter about externally meaningful workflow changes.

    Admin-only notes are intentionally never included. The submitter address is
    collected on ticket creation and is the only recipient of this message.
    """
    to = (ticket_data.get("email") or "").strip()
    if not to:
        return False

    status = ticket_data.get("status") or "open"
    assignee = ticket_data.get("assigned_to_name")
    change_lines: list[str] = []
    if "status" in changed:
        change_lines.append(f"Status: {status.replace('_', ' ').title()}")
    if "assigned_to_name" in changed:
        change_lines.append(f"Assigned to: {assignee or 'Unassigned'}")
    if not change_lines:
        return True

    ticket_id = ticket_data.get("ticket_id") or ""
    subject = f"[AAFC TMS] Support Ticket Updated — {ticket_id}"
    body = (
        "Your AAFC TMS support ticket has been updated.\n\n"
        + "\n".join(change_lines)
        + "\n\nLog in to the AAFC TMS if you need to review the current ticket state.\n"
    )
    return send_mail(to, subject, body)


def send_mail(to: str, subject: str, body: str) -> bool:
    """Send one plain-text message. Returns success rather than raising.

    Callers use the boolean to decide whether to keep a freshly minted recovery
    token: a token nobody can receive is worse than no token, because it sits
    valid and unusable until it expires.

    Never logs the message body. A recovery mail body contains the token.
    """
    if not settings.SMTP_HOST:
        # Local and staging default. The address is logged (it is operational
        # data an operator needs) but the body -- which carries the token -- is
        # not, and nothing is transmitted.
        logger.info("SMTP not configured — not sending %r to %s", subject, to)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
            smtp.send_message(msg)
        return True
    except Exception as exc:                      # noqa: BLE001 - report, never raise
        logger.error("SMTP send failed for %s: %s", to, exc)
        return False
