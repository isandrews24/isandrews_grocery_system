import secrets

from flask import current_app, url_for
from flask_mail import Message

from app.extensions import mail

INVITE_TTL_DAYS = 7


def generate_invite_token():
    return secrets.token_urlsafe(32)


def send_staff_invite_email(invite):
    """Emails a signup link to a newly invited staff member.

    Runs in suppressed mode (composed but not sent) until MAIL_USERNAME is
    configured with real SMTP credentials - same pattern as every other
    email in this app.
    """
    store_name = current_app.config["STORE_NAME"]
    accept_url = url_for("auth.accept_invite", token=invite.token, _external=True)
    msg = Message(
        subject=f"You're invited to join {store_name}",
        recipients=[invite.email],
        body=(
            f"You've been invited to join {store_name} as a {invite.role.replace('_', ' ')}.\n\n"
            f"Set up your account here: {accept_url}\n\n"
            f"This link expires in {INVITE_TTL_DAYS} days."
        ),
    )
    mail.send(msg)
    return {"live": not current_app.config["MAIL_SUPPRESS_SEND"], "accept_url": accept_url}
