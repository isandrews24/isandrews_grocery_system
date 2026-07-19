import logging

from flask import current_app

from app.extensions import mail

logger = logging.getLogger(__name__)


def safe_send(msg):
    """Sends via Flask-Mail, swallowing any transport/auth failure so a
    broken or misconfigured mail server never crashes the request that
    triggered it (e.g. wrong Gmail app password, network blip).

    Returns True if the message actually went out live, False if it was
    demo-mode-suppressed or the send failed.
    """
    try:
        mail.send(msg)
    except Exception:
        logger.exception("Failed to send email: %s", msg.subject)
        return False
    return not current_app.config["MAIL_SUPPRESS_SEND"]
