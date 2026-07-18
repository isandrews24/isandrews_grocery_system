from datetime import datetime, time

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db
from app.models import Transaction, OnlineOrder, Payment, Product, Inventory, AuditLog, Location
from app.blueprints.pos.routes import roles_required
from app.services.audit import log_activity
from app.tasks import sms_order_status

admin_bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="../../templates/admin")

ORDER_ROLES = ("admin", "superadmin", "online_manager")

STATUS_FLOW = {
    "home_delivery": ["pending", "confirmed", "processing", "ready", "out_for_delivery", "delivered"],
    "click_and_collect": ["pending", "confirmed", "processing", "ready", "delivered"],
}
STATUS_LABELS = {
    "pending": "Pending",
    "confirmed": "Confirmed",
    "processing": "Processing",
    "ready": "Ready",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}


def _next_status(order):
    flow = STATUS_FLOW[order.delivery_method]
    if order.status not in flow:
        return None
    idx = flow.index(order.status)
    return flow[idx + 1] if idx + 1 < len(flow) else None


@admin_bp.route("/")
@roles_required("admin", "superadmin", "inventory_manager", "online_manager")
def dashboard():
    today_start = datetime.combine(datetime.utcnow().date(), time.min)

    pos_sales_today = db.session.query(func.coalesce(func.sum(Transaction.total_amount), 0)).filter(
        Transaction.status == "completed", Transaction.created_at >= today_start
    ).scalar()
    online_sales_today = db.session.query(func.coalesce(func.sum(OnlineOrder.total_amount), 0)).filter(
        OnlineOrder.payment_status == "paid", OnlineOrder.placed_at >= today_start
    ).scalar()
    todays_sales = float(pos_sales_today) + float(online_sales_today)

    orders_today = Transaction.query.filter(
        Transaction.status == "completed", Transaction.created_at >= today_start
    ).count() + OnlineOrder.query.filter(OnlineOrder.placed_at >= today_start).count()

    pending_count = Payment.query.filter_by(status="pending").count()

    payments_today = Payment.query.filter(Payment.created_at >= today_start).all()
    momo_payments = [p for p in payments_today if p.payment_method != "cash"]
    if momo_payments:
        success_rate = round(
            100 * len([p for p in momo_payments if p.status == "completed"]) / len(momo_payments)
        )
    else:
        success_rate = 100

    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(8).all()

    default_location = Location.query.filter_by(is_default=True).first()
    low_stock = Product.query.join(Inventory).filter(
        Inventory.location_id == default_location.id,
        Inventory.quantity_on_hand <= Inventory.reorder_level,
        Product.is_active.is_(True),
    ).all()

    return render_template(
        "admin/dashboard.html",
        todays_sales=todays_sales,
        orders_today=orders_today,
        pending_count=pending_count,
        success_rate=success_rate,
        recent_payments=recent_payments,
        low_stock=low_stock,
    )


def _restore_inventory(txn):
    for item in txn.items:
        if item.product.inventory:
            item.product.inventory.quantity_on_hand = float(item.product.inventory.quantity_on_hand) + float(item.quantity)


@admin_bp.route("/transaction/<int:transaction_id>/void", methods=["POST"])
@roles_required("admin", "superadmin")
def void_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    reason = request.form.get("reason", "").strip()

    if txn.status != "completed":
        flash("Only completed transactions can be voided.", "warning")
        return redirect(url_for("admin.dashboard"))

    _restore_inventory(txn)
    txn.status = "voided"
    txn.voided_by = current_user.id
    txn.void_reason = reason or "No reason given"

    log_activity(
        current_user, "VOID", "transactions", txn.id,
        old_values={"status": "completed"}, new_values={"status": "voided", "reason": txn.void_reason},
    )
    db.session.commit()
    flash(f"Transaction {txn.transaction_number} voided.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/transaction/<int:transaction_id>/refund", methods=["POST"])
@roles_required("admin", "superadmin")
def refund_transaction(transaction_id):
    txn = Transaction.query.get_or_404(transaction_id)
    reason = request.form.get("reason", "").strip()

    if txn.status != "completed":
        flash("Only completed transactions can be refunded.", "warning")
        return redirect(url_for("admin.dashboard"))

    _restore_inventory(txn)
    txn.status = "refunded"
    for payment in txn.payments:
        payment.status = "refunded"

    log_activity(
        current_user, "REFUND", "transactions", txn.id,
        old_values={"status": "completed"}, new_values={"status": "refunded", "reason": reason},
    )
    db.session.commit()
    flash(
        f"Transaction {txn.transaction_number} refunded. "
        f"Money must still be sent back to the customer manually via {txn.payment_method or 'the original method'}.",
        "success",
    )
    return redirect(url_for("admin.dashboard"))


# ---------- Online order fulfillment ----------

@admin_bp.route("/orders")
@roles_required(*ORDER_ROLES)
def orders():
    status_filter = request.args.get("status", "")
    query = OnlineOrder.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    order_list = query.order_by(OnlineOrder.placed_at.desc()).all()
    return render_template(
        "admin/orders.html", orders=order_list, status_filter=status_filter,
        status_labels=STATUS_LABELS,
    )


@admin_bp.route("/orders/<int:order_id>")
@roles_required(*ORDER_ROLES)
def order_detail(order_id):
    order = OnlineOrder.query.get_or_404(order_id)
    return render_template(
        "admin/order_detail.html", order=order, next_status=_next_status(order),
        status_labels=STATUS_LABELS,
    )


@admin_bp.route("/orders/<int:order_id>/pick", methods=["GET", "POST"])
@roles_required(*ORDER_ROLES)
def pick_order(order_id):
    order = OnlineOrder.query.get_or_404(order_id)

    if request.method == "POST":
        for item in order.items:
            picked = request.form.get(f"picked_{item.id}", 0, type=float)
            item.quantity_picked = max(0, min(picked, float(item.quantity)))

        if order.is_fully_picked:
            order.picked_by = current_user.id
            order.picked_at = datetime.utcnow()
            message = "All items picked. Order is ready to be marked as ready."
        else:
            order.picked_by = None
            order.picked_at = None
            message = f"Picks saved ({order.pick_progress} items fully picked)."

        log_activity(
            current_user, "UPDATE", "online_orders", order.id,
            new_values={"pick_progress": order.pick_progress, "fully_picked": order.is_fully_picked},
        )
        db.session.commit()
        flash(message, "success")
        return redirect(url_for("admin.order_detail", order_id=order.id))

    return render_template("admin/pick_order.html", order=order)


@admin_bp.route("/orders/<int:order_id>/advance", methods=["POST"])
@roles_required(*ORDER_ROLES)
def advance_order(order_id):
    order = OnlineOrder.query.get_or_404(order_id)
    new_status = _next_status(order)
    if not new_status:
        flash("This order is already at its final status.", "warning")
        return redirect(url_for("admin.order_detail", order_id=order.id))

    if new_status == "ready" and not order.is_fully_picked:
        flash("Pick all items before marking this order as ready.", "warning")
        return redirect(url_for("admin.pick_order", order_id=order.id))

    old_status = order.status

    # Moving into 'processing' is when reserved stock actually leaves inventory.
    if new_status == "processing":
        for item in order.items:
            if item.product.inventory:
                item.product.inventory.quantity_reserved = max(
                    0, float(item.product.inventory.quantity_reserved) - float(item.quantity)
                )
                item.product.inventory.quantity_on_hand = max(
                    0, float(item.product.inventory.quantity_on_hand) - float(item.quantity)
                )

    order.status = new_status
    log_activity(
        current_user, "UPDATE", "online_orders", order.id,
        old_values={"status": old_status}, new_values={"status": new_status},
    )
    db.session.commit()

    sms_order_status.delay(order.id)
    flash(f"Order moved to '{STATUS_LABELS[new_status]}'. Customer SMS notification queued in the background.", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))


@admin_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@roles_required(*ORDER_ROLES)
def cancel_order(order_id):
    order = OnlineOrder.query.get_or_404(order_id)
    reason = request.form.get("reason", "").strip()

    if order.status in ("delivered", "cancelled"):
        flash("This order can no longer be cancelled.", "warning")
        return redirect(url_for("admin.order_detail", order_id=order.id))

    already_decremented = STATUS_FLOW[order.delivery_method].index(order.status) >= STATUS_FLOW[order.delivery_method].index("processing")

    for item in order.items:
        if item.product.inventory:
            if already_decremented:
                item.product.inventory.quantity_on_hand = float(item.product.inventory.quantity_on_hand) + float(item.quantity)
            else:
                item.product.inventory.quantity_reserved = max(
                    0, float(item.product.inventory.quantity_reserved) - float(item.quantity)
                )

    old_status = order.status
    order.status = "cancelled"
    order.notes = (order.notes + "\n" if order.notes else "") + f"Cancelled: {reason or 'No reason given'}"

    log_activity(
        current_user, "UPDATE", "online_orders", order.id,
        old_values={"status": old_status}, new_values={"status": "cancelled", "reason": reason},
    )
    db.session.commit()
    flash(f"Order {order.order_number} cancelled. Stock reservation released.", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))


@admin_bp.route("/orders/<int:order_id>/picking-slip")
@roles_required(*ORDER_ROLES)
def picking_slip(order_id):
    order = OnlineOrder.query.get_or_404(order_id)
    return render_template("admin/picking_slip.html", order=order)


@admin_bp.route("/audit-log")
@roles_required("admin", "superadmin")
def audit_log():
    entries = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template("admin/audit_log.html", entries=entries)
