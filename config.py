import os

from celery.schedules import crontab

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalize_db_url(url):
    # Render (and some other hosts) hand out "postgres://" URLs, but
    # SQLAlchemy 2.x only accepts the "postgresql://" scheme.
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.environ.get("DATABASE_URL")) or \
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'grocery.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STORE_NAME = os.environ.get("STORE_NAME", "isAndrews Grocery")
    STORE_TIN = os.environ.get("STORE_TIN", "")
    CURRENCY = "GHS"

    VAT_RATE = float(os.environ.get("VAT_RATE", 15.0))
    NHIL_RATE = float(os.environ.get("NHIL_RATE", 2.5))
    GETFUND_RATE = float(os.environ.get("GETFUND_RATE", 2.5))

    MTN_MOMO_API_KEY = os.environ.get("MTN_MOMO_API_KEY", "")
    MTN_MOMO_SUBSCRIPTION_KEY = os.environ.get("MTN_MOMO_SUBSCRIPTION_KEY", "")
    MTN_MOMO_ENVIRONMENT = os.environ.get("MTN_MOMO_ENVIRONMENT", "sandbox")
    VODAFONE_API_KEY = os.environ.get("VODAFONE_API_KEY", "")
    VODAFONE_API_SECRET = os.environ.get("VODAFONE_API_SECRET", "")
    PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
    PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME", "receipts@isandrewsgrocery.gh")
    MAIL_SUPPRESS_SEND = not bool(os.environ.get("MAIL_USERNAME"))

    PRINTER_TYPE = os.environ.get("PRINTER_TYPE", "")  # "usb", "network", or blank for demo mode
    PRINTER_USB_VENDOR_ID = os.environ.get("PRINTER_USB_VENDOR_ID", "")
    PRINTER_USB_PRODUCT_ID = os.environ.get("PRINTER_USB_PRODUCT_ID", "")
    PRINTER_NETWORK_IP = os.environ.get("PRINTER_NETWORK_IP", "")

    HUBTEL_SMS_CLIENT_ID = os.environ.get("HUBTEL_SMS_CLIENT_ID", "")
    HUBTEL_SMS_CLIENT_SECRET = os.environ.get("HUBTEL_SMS_CLIENT_SECRET", "")
    HUBTEL_SMS_SENDER_ID = os.environ.get("HUBTEL_SMS_SENDER_ID", "isAndrewsGro")

    GRA_EFD_ENDPOINT = os.environ.get("GRA_EFD_ENDPOINT", "")
    GRA_EFD_API_KEY = os.environ.get("GRA_EFD_API_KEY", "")
    GRA_EFD_DEVICE_NUMBER = os.environ.get("GRA_EFD_DEVICE_NUMBER", "")

    # DB index 3 - Memurai is a shared local instance; other projects on this
    # machine use db 0, so a dedicated index avoids cross-project task collisions.
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/3")

    # If no REDIS_URL is set in the environment (e.g. a lean Render deployment
    # with no Redis add-on / worker service), tasks run synchronously in-process
    # instead of being queued - same behavior as before Celery existed, so the
    # app never breaks from an unreachable broker. Set REDIS_URL to get real
    # background processing (needs a Redis instance + a running worker).
    _HAS_REAL_REDIS = bool(os.environ.get("REDIS_URL"))
    CELERY = {
        "broker_url": REDIS_URL,
        "result_backend": REDIS_URL,
        "task_ignore_result": True,
        "task_always_eager": not _HAS_REAL_REDIS,
        "task_eager_propagates": True,
        "timezone": "UTC",
        "beat_schedule": {
            "check-low-stock-daily": {
                "task": "app.tasks.check_low_stock",
                "schedule": crontab(hour=6, minute=0),  # 06:00 daily - Ghana is UTC+0, no offset needed
            },
        },
    }
