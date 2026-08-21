"""SMTP email notification service for Service Desk tickets.

If SMTP_HOST is not configured, notifications are logged but not sent.
Email failure never prevents ticket creation.
"""
import logging
import smtplib
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
            "SMTP not configured — skipping notification email for ticket %s (would notify: %s)",
            ticket_data.get("ticket_id"),
            ", ".join(recipients),
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
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.ehlo()
            if settings.SMTP_USER:
                smtp.starttls()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
            smtp.sendmail(settings.SMTP_FROM, recipients, msg.as_string())
        logger.info("Ticket notification sent to %d recipients", len(recipients))
    except Exception as exc:
        logger.error("Failed to send ticket notification: %s", exc)
