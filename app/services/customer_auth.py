import random
from datetime import datetime, timedelta

from flask import current_app
from flask_mail import Message

from app.extensions import mail

OTP_TTL_MINUTES = 10


def generate_otp():
    return "".join(random.choices("0123456789", k=6))


def send_email_otp(customer, code):
    """Emails a 6-digit verification code to the customer.

    Runs in suppressed mode (composed but not actually sent) until
    MAIL_USERNAME is configured with real SMTP credentials - same pattern
    as the receipt emails in services/receipts.py.
    """
    store_name = current_app.config["STORE_NAME"]
    msg = Message(
        subject=f"Verify your email - {store_name}",
        recipients=[customer.email],
        body=f"Your {store_name} email verification code is {code}. It expires in {OTP_TTL_MINUTES} minutes.",
    )
    mail.send(msg)
    return {"live": not current_app.config["MAIL_SUPPRESS_SEND"], "code": code}


def send_phone_otp(customer, code):
    """Sends a 6-digit verification code via SMS.

    Runs in demo mode (composed but not sent) until HUBTEL_SMS_CLIENT_ID is
    configured - same pattern as services/sms.py.
    """
    store_name = current_app.config["STORE_NAME"]
    message = f"{store_name}: your phone verification code is {code}. It expires in {OTP_TTL_MINUTES} minutes."

    if not current_app.config["HUBTEL_SMS_CLIENT_ID"]:
        return {"live": False, "message": message, "code": code}

    raise NotImplementedError("Live Hubtel SMS integration not yet wired up")


def issue_email_otp(customer):
    code = generate_otp()
    customer.email_otp_code = code
    customer.email_otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    return send_email_otp(customer, code)


def issue_phone_otp(customer):
    code = generate_otp()
    customer.phone_otp_code = code
    customer.phone_otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)
    return send_phone_otp(customer, code)


def check_email_otp(customer, submitted_code):
    if not customer.email_otp_code or not customer.email_otp_expires_at:
        return False
    if datetime.utcnow() > customer.email_otp_expires_at:
        return False
    return submitted_code.strip() == customer.email_otp_code


def check_phone_otp(customer, submitted_code):
    if not customer.phone_otp_code or not customer.phone_otp_expires_at:
        return False
    if datetime.utcnow() > customer.phone_otp_expires_at:
        return False
    return submitted_code.strip() == customer.phone_otp_code
