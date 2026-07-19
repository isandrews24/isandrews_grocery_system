import logging
import socket

from flask import current_app

from app.extensions import mail

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 8


def safe_send(msg):
    """Sends via Flask-Mail, swallowing any transport/auth failure so a
    broken or misconfigured mail server never crashes the request that
    triggered it (e.g. wrong Gmail app password, network blip).

    Also bounds the connection attempt with a short socket timeout.
    Without this, a hanging (not immediately-rejected) SMTP connection -
    e.g. an outbound network/firewall issue reaching smtp.gmail.com - can
    block until gunicorn's worker timeout (30s default) kills the whole
    process, which happens *before* any Python exception ever reaches the
    try/except below and can't be caught here at all.

    Returns True if the message actually went out live, False if it was
    demo-mode-suppressed or the send failed.
    """
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(SMTP_TIMEOUT_SECONDS)
    try:
        mail.send(msg)
    except Exception:
        logger.exception("Failed to send email: %s", msg.subject)
        return False
    finally:
        socket.setdefaulttimeout(previous_timeout)
    return not current_app.config["MAIL_SUPPRESS_SEND"]
