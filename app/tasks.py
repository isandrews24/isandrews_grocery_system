"""Celery tasks - async email/SMS delivery and scheduled jobs.

Each task re-fetches its own data by ID rather than being passed ORM
objects directly, since task arguments have to survive being serialized
onto the Redis queue. FlaskTask (see app/extensions.py) wraps every task
in an app context, so current_app/db/mail all work normally inside them.
"""
from flask import current_app
from flask_mail import Message

from app.extensions import celery_app, db
from app.models import Transaction, OnlineOrder, Product, Inventory, Location, User
from app.services.mailer import safe_send
from app.services.receipts import generate_pos_receipt_pdf, generate_online_order_receipt_pdf, send_receipt_email
from app.services.sms import send_receipt_sms, send_order_status_sms


@celery_app.task(name="app.tasks.email_transaction_receipt")
def email_transaction_receipt(transaction_id, to_email):
    txn = db.session.get(Transaction, transaction_id)
    if not txn:
        return {"sent": False, "reason": "transaction not found"}
    buf = generate_pos_receipt_pdf(txn)
    was_live = send_receipt_email(to_email, txn.transaction_number, buf)
    return {"sent": was_live, "to": to_email, "reference": txn.transaction_number}


@celery_app.task(name="app.tasks.email_order_receipt")
def email_order_receipt(order_id, to_email):
    order = db.session.get(OnlineOrder, order_id)
    if not order:
        return {"sent": False, "reason": "order not found"}
    buf = generate_online_order_receipt_pdf(order)
    was_live = send_receipt_email(to_email, order.order_number, buf)
    return {"sent": was_live, "to": to_email, "reference": order.order_number}


@celery_app.task(name="app.tasks.sms_transaction_receipt")
def sms_transaction_receipt(transaction_id, phone):
    txn = db.session.get(Transaction, transaction_id)
    if not txn:
        return {"sent": False, "reason": "transaction not found"}
    result = send_receipt_sms(phone, txn)
    return {"sent": result["live"], "to": phone, "reference": txn.transaction_number}


@celery_app.task(name="app.tasks.sms_order_status")
def sms_order_status(order_id):
    order = db.session.get(OnlineOrder, order_id)
    if not order:
        return {"sent": False, "reason": "order not found"}
    result = send_order_status_sms(order)
    return {"sent": result["live"], "reference": order.order_number, "status": order.status}


@celery_app.task(name="app.tasks.check_low_stock")
def check_low_stock():
    """Daily 06:00 job (see config.py CELERY beat_schedule): emails
    admin/inventory_manager users when stock falls at or below reorder
    level at the default location.
    """
    default_location = Location.query.filter_by(is_default=True).first()
    if not default_location:
        return {"sent": False, "reason": "no default location"}

    low_stock = Product.query.join(Inventory).filter(
        Inventory.location_id == default_location.id,
        Inventory.quantity_on_hand <= Inventory.reorder_level,
        Product.is_active.is_(True),
    ).all()

    if not low_stock:
        return {"sent": False, "reason": "no low stock items"}

    recipients = [u.email for u in User.query.filter(User.role.in_(["admin", "superadmin", "inventory_manager"])).all()]
    if not recipients:
        return {"sent": False, "reason": "no recipients"}

    lines = "\n".join(
        f"- {p.name}: {p.in_stock_qty:g} left (reorder level {float(p.inventory.reorder_level):g}, "
        f"suggest reordering {float(p.inventory.reorder_quantity):g})"
        for p in low_stock
    )
    msg = Message(
        subject=f"Low stock alert - {current_app.config['STORE_NAME']}",
        recipients=recipients,
        body=f"The following products are at or below their reorder level:\n\n{lines}",
    )
    sent = safe_send(msg)
    return {"sent": sent, "count": len(low_stock), "recipients": recipients}
