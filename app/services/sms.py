import logging

from flask import current_app

logger = logging.getLogger(__name__)


def is_live_configured():
    return bool(current_app.config["HUBTEL_SMS_CLIENT_ID"])


def send_receipt_sms(phone_number, txn):
    """Sends a concise SMS receipt summary via the Hubtel SMS API.

    Runs in demo mode (message composed but not actually sent) until
    HUBTEL_SMS_CLIENT_ID/SECRET are configured - see config.py. Swap in
    the real requests.post(...) call to Hubtel's SMS endpoint once
    credentials are issued.
    """
    store_name = current_app.config["STORE_NAME"]
    message = (
        f"{store_name}: {txn.transaction_number} | GHS {float(txn.total_amount):.2f} | "
        f"{(txn.payment_method or '').replace('_', ' ').upper()} confirmed. "
        f"Items: {len(txn.items)} | {txn.created_at.strftime('%d/%m/%Y %H:%M')}. Thank you!"
    )[:160]

    if not is_live_configured():
        return {"live": False, "message": message}

    # TODO: real Hubtel SMS API integration
    # requests.post(
    #     "https://sms.hubtel.com/v1/messages/send",
    #     params={
    #         "clientid": current_app.config["HUBTEL_SMS_CLIENT_ID"],
    #         "clientsecret": current_app.config["HUBTEL_SMS_CLIENT_SECRET"],
    #         "from": current_app.config["HUBTEL_SMS_SENDER_ID"],
    #         "to": phone_number,
    #         "content": message,
    #     },
    # )
    logger.warning("HUBTEL_SMS_CLIENT_ID is configured but live SMS sending isn't implemented yet - falling back to demo mode.")
    return {"live": False, "message": message}


def send_order_status_sms(order):
    """Notifies the customer of an online order status change via SMS.

    Same demo-mode pattern as send_receipt_sms - composed but not sent
    until Hubtel credentials are configured.
    """
    store_name = current_app.config["STORE_NAME"]
    status_label = order.status.replace("_", " ").title()
    message = (
        f"{store_name}: Order {order.order_number} is now {status_label}. "
        f"Total GHS {float(order.total_amount):.2f}. Thank you for shopping with us!"
    )[:160]

    if not is_live_configured():
        return {"live": False, "message": message}

    logger.warning("HUBTEL_SMS_CLIENT_ID is configured but live SMS sending isn't implemented yet - falling back to demo mode.")
    return {"live": False, "message": message}
