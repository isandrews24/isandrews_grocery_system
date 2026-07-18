import random
import string
from datetime import datetime
from functools import wraps

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Product, Category, PosSession, Transaction, TransactionItem, Payment, Customer
from app.services.tax import calculate_tax_breakdown, totals_for_cart
from app.services.payments import initiate_payment, PROVIDER_LABELS
from app.services.audit import log_activity
from app.services.receipts import generate_pos_receipt_pdf
from app.services.thermal_printer import print_pos_receipt
from app.services.efd_service import transmit_to_efd
from app.tasks import email_transaction_receipt, sms_transaction_receipt

pos_bp = Blueprint("pos", __name__, url_prefix="/pos", template_folder="../../templates/pos")

DEFAULT_TERMINAL = "POS-01"


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role not in roles:
                flash("You don't have permission to access that.", "danger")
                return redirect(url_for("auth.login"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def _transaction_number():
    return "TXN-" + datetime.utcnow().strftime("%Y%m%d") + "-" + "".join(random.choices(string.digits, k=5))


def _get_or_open_session(cashier, terminal_id=DEFAULT_TERMINAL):
    pos_session = PosSession.query.filter_by(terminal_id=terminal_id, status="open").first()
    if not pos_session:
        pos_session = PosSession(cashier_id=cashier.id, terminal_id=terminal_id, opening_float=0)
        db.session.add(pos_session)
        db.session.commit()
    return pos_session


def _get_or_create_draft(pos_session):
    draft = Transaction.query.filter_by(session_id=pos_session.id, status="pending").order_by(
        Transaction.created_at.desc()
    ).first()
    if not draft:
        draft = Transaction(
            session_id=pos_session.id,
            transaction_number=_transaction_number(),
            status="pending",
            source="pos",
        )
        db.session.add(draft)
        db.session.commit()
    return draft


def _recalc_transaction(txn):
    tax_input = [
        {"unit_price": item.unit_price, "quantity": item.quantity, "is_taxable": item.product.is_taxable}
        for item in txn.items
    ]
    totals = totals_for_cart(tax_input) if tax_input else {"subtotal": 0, "tax": 0, "total": 0}
    txn.subtotal = totals["subtotal"]
    txn.tax_amount = totals["tax"]
    txn.total_amount = round(totals["total"] - float(txn.discount_amount or 0), 2)
    db.session.commit()
    return totals


def _cart_payload(txn):
    return {
        "transaction_number": txn.transaction_number,
        "status": txn.status,
        "items": [
            {
                "product_id": item.product_id,
                "name": item.product.name,
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "line_total": float(item.line_total),
            }
            for item in txn.items
        ],
        "subtotal": float(txn.subtotal or 0),
        "tax_amount": float(txn.tax_amount or 0),
        "total_amount": float(txn.total_amount or 0),
        "payment_method": txn.payment_method,
    }


@pos_bp.route("/")
@roles_required("cashier", "admin", "superadmin")
def terminal():
    pos_session = _get_or_open_session(current_user)
    draft = _get_or_create_draft(pos_session)
    categories = Category.query.filter_by(is_active=True, parent_id=None).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template(
        "pos/terminal.html",
        products=products,
        categories=categories,
        draft=draft,
        provider_labels=PROVIDER_LABELS,
    )


@pos_bp.route("/display")
def display():
    return render_template("pos/display.html", terminal_id=DEFAULT_TERMINAL)


@pos_bp.route("/api/cart")
@login_required
def get_cart():
    pos_session = _get_or_open_session(current_user)
    draft = _get_or_create_draft(pos_session)
    return jsonify(_cart_payload(draft))


@pos_bp.route("/api/cart/public")
def get_cart_public():
    """Read-only feed for the customer-facing display screen."""
    pos_session = PosSession.query.filter_by(terminal_id=DEFAULT_TERMINAL, status="open").first()
    if not pos_session:
        return jsonify({"items": [], "subtotal": 0, "tax_amount": 0, "total_amount": 0, "status": "idle"})
    draft = Transaction.query.filter_by(session_id=pos_session.id, status="pending").order_by(
        Transaction.created_at.desc()
    ).first()
    if not draft:
        return jsonify({"items": [], "subtotal": 0, "tax_amount": 0, "total_amount": 0, "status": "idle"})
    return jsonify(_cart_payload(draft))


@pos_bp.route("/api/product/barcode/<barcode>")
@login_required
def lookup_barcode(barcode):
    product = Product.query.filter_by(barcode_number=barcode, is_active=True).first()
    if not product:
        return jsonify({"error": "not_found"}), 404
    return jsonify({
        "id": product.id,
        "name": product.name,
        "unit_price": float(product.unit_price),
        "in_stock_qty": product.in_stock_qty,
    })


@pos_bp.route("/api/add/<int:product_id>", methods=["POST"])
@login_required
def add_item(product_id):
    product = Product.query.get_or_404(product_id)
    pos_session = _get_or_open_session(current_user)
    draft = _get_or_create_draft(pos_session)

    existing = next((i for i in draft.items if i.product_id == product_id), None)
    if existing:
        existing.quantity = float(existing.quantity) + 1
        breakdown = calculate_tax_breakdown(existing.unit_price, existing.quantity, product.is_taxable)
        existing.line_total = breakdown["line_total"]
        existing.tax_amount = breakdown["total_tax"]
    else:
        breakdown = calculate_tax_breakdown(product.unit_price, 1, product.is_taxable)
        db.session.add(
            TransactionItem(
                transaction_id=draft.id,
                product_id=product.id,
                quantity=1,
                unit_price=product.unit_price,
                tax_amount=breakdown["total_tax"],
                line_total=breakdown["line_total"],
            )
        )

    db.session.commit()
    _recalc_transaction(draft)
    return jsonify(_cart_payload(draft))


@pos_bp.route("/api/item/<int:item_id>", methods=["PATCH", "DELETE"])
@login_required
def modify_item(item_id):
    item = TransactionItem.query.get_or_404(item_id)
    draft = item.transaction

    if request.method == "DELETE":
        db.session.delete(item)
    else:
        qty = request.json.get("quantity", 1)
        if qty <= 0:
            db.session.delete(item)
        else:
            item.quantity = qty
            breakdown = calculate_tax_breakdown(item.unit_price, qty, item.product.is_taxable)
            item.line_total = breakdown["line_total"]
            item.tax_amount = breakdown["total_tax"]

    db.session.commit()
    _recalc_transaction(draft)
    return jsonify(_cart_payload(draft))


@pos_bp.route("/api/charge", methods=["POST"])
@login_required
def charge():
    pos_session = _get_or_open_session(current_user)
    draft = _get_or_create_draft(pos_session)

    if not draft.items:
        return jsonify({"error": "empty_cart"}), 400

    payload = request.json or {}
    method = payload.get("payment_method", "cash")
    phone = payload.get("phone_number")

    draft.payment_method = method
    payment_result = initiate_payment(method, draft.total_amount, phone_number=phone, reference=draft.transaction_number)

    payment = Payment(
        transaction_id=draft.id,
        payment_method=method,
        amount=draft.total_amount,
        phone_number=phone,
        reference_number=payment_result["reference"],
        status=payment_result["status"],
    )
    db.session.add(payment)

    if method == "cash" or payment_result["status"] == "completed":
        _complete_transaction(draft)
        payment.status = "completed"
        payment.processed_at = datetime.utcnow()
        log_activity(
            current_user, "CHARGE", "transactions", draft.id,
            new_values={"total_amount": float(draft.total_amount), "payment_method": method},
        )

    db.session.commit()
    return jsonify({
        "payment_status": payment.status,
        "transaction_id": draft.id,
        "transaction": _cart_payload(draft),
    })


@pos_bp.route("/api/charge/<int:transaction_id>/simulate-approve", methods=["POST"])
@login_required
def simulate_approve(transaction_id):
    """Demo-mode only: mimics the customer approving the MoMo USSD prompt."""
    draft = Transaction.query.get_or_404(transaction_id)
    for payment in draft.payments:
        if payment.status == "pending":
            payment.status = "completed"
            payment.processed_at = datetime.utcnow()
    _complete_transaction(draft)
    log_activity(
        current_user, "CHARGE", "transactions", draft.id,
        new_values={"total_amount": float(draft.total_amount), "payment_method": draft.payment_method, "demo_approved": True},
    )
    db.session.commit()
    return jsonify({"status": "completed"})


def _complete_transaction(txn):
    if txn.status == "completed":
        return
    for item in txn.items:
        if item.product.inventory:
            item.product.inventory.quantity_on_hand = max(
                0, float(item.product.inventory.quantity_on_hand) - float(item.quantity)
            )
    txn.status = "completed"


@pos_bp.route("/receipt/<int:transaction_id>.pdf")
@login_required
def receipt_pdf(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    buf = generate_pos_receipt_pdf(txn)
    return send_file(buf, mimetype="application/pdf", as_attachment=False, download_name=f"{txn.transaction_number}.pdf")


@pos_bp.route("/receipt/<int:transaction_id>/email", methods=["POST"])
@login_required
def email_receipt(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    to_email = request.form.get("email", "").strip()
    if not to_email:
        flash("Enter a customer email address to send the receipt.", "warning")
        return redirect(url_for("admin.dashboard"))

    email_transaction_receipt.delay(txn.id, to_email)
    log_activity(current_user, "EMAIL_RECEIPT", "transactions", txn.id, new_values={"to": to_email})
    db.session.commit()

    flash(f"Receipt for {txn.transaction_number} queued to send to {to_email} (processed in the background by Celery).", "success")
    return redirect(url_for("admin.dashboard"))


@pos_bp.route("/receipt/<int:transaction_id>/print", methods=["POST"])
@login_required
def print_receipt(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    result = print_pos_receipt(txn)
    log_activity(current_user, "PRINT_RECEIPT", "transactions", txn.id, new_values={"live": result["live"]})
    db.session.commit()

    if result["live"]:
        flash(f"Receipt sent to thermal printer for {txn.transaction_number}.", "success")
    else:
        flash(
            f"Demo mode: no thermal printer configured. Generated {result['raw_bytes']} bytes of ESC/POS "
            f"commands for {txn.transaction_number} without printing.",
            "warning",
        )
    return redirect(url_for("admin.dashboard"))


@pos_bp.route("/receipt/<int:transaction_id>/sms", methods=["POST"])
@login_required
def sms_receipt(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    phone = request.form.get("phone", "").strip()
    if not phone:
        flash("Enter a customer phone number to send the SMS receipt.", "warning")
        return redirect(url_for("admin.dashboard"))

    sms_transaction_receipt.delay(txn.id, phone)
    log_activity(current_user, "SMS_RECEIPT", "transactions", txn.id, new_values={"to": phone})
    db.session.commit()

    flash(f"Receipt SMS for {txn.transaction_number} queued to {phone} (processed in the background by Celery).", "success")
    return redirect(url_for("admin.dashboard"))


@pos_bp.route("/receipt/<int:transaction_id>/efd", methods=["POST"])
@login_required
def efd_transmit(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    result = transmit_to_efd(txn)
    log_activity(current_user, "EFD_TRANSMIT", "transactions", txn.id, new_values={"live": result["live"], "fiscal_code": result["fiscal_code"]})
    db.session.commit()

    if result["live"]:
        flash(f"Transmitted to GRA. Fiscal code: {result['fiscal_code']}.", "success")
    else:
        flash(
            f"Demo mode: no GRA EFD device configured. Formatted the fiscal payload for {txn.transaction_number} without transmitting.",
            "warning",
        )
    return redirect(url_for("admin.dashboard"))
