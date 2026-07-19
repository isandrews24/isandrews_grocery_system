from flask import current_app
from flask_mail import Message

from app.services.mailer import safe_send


def send_feedback_notification(entry):
    """Emails a submitted feedback entry to the configured FEEDBACK_EMAIL.

    Runs in suppressed mode (composed but not sent) until MAIL_USERNAME is
    configured with real SMTP credentials - same pattern as every other
    email in this app.
    """
    store_name = current_app.config["STORE_NAME"]
    msg = Message(
        subject=f"New feedback - {store_name}",
        recipients=[current_app.config["FEEDBACK_EMAIL"]],
        body=(
            f"From: {entry.name or 'Anonymous'} ({entry.email or 'no email given'})\n"
            f"Rating: {entry.rating or 'n/a'}/5\n"
            f"Submitted: {entry.submitted_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"{entry.message}"
        ),
    )
    return safe_send(msg)
