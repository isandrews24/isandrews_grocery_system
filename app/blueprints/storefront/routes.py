import random
import string
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify, send_file

from app.extensions import db
from app.models import Product, Category, Customer, OnlineOrder, OnlineOrderItem, Payment, Review, Feedback
from app.services.tax import calculate_tax_breakdown, totals_for_cart
from app.services.payments import initiate_payment, PROVIDER_LABELS
from app.services.receipts import generate_online_order_receipt_pdf
from app.services.feedback import send_feedback_notification
from app.tasks import email_order_receipt as email_order_receipt_task
from app.blueprints.account.routes import get_current_customer

storefront_bp = Blueprint(
    "storefront", __name__, template_folder="../../templates/storefront"
)

DELIVERY_FEES = {
    "Greater Accra": 20.0,
    "Ashanti": 30.0,
    "Other": 40.0,
}


def _generate_order_number():
    return "ORD-" + datetime.utcnow().strftime("%Y%m%d") + "-" + "".join(
        random.choices(string.digits, k=4)
    )


def _cart_products():
    cart = session.get("cart", {})
    if not cart:
        return [], {"subtotal": 0, "tax": 0, "total": 0}

    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids), Product.is_active.is_(True)).all()
    products_by_id = {p.id: p for p in products}

    lines = []
    tax_input = []
    for pid_str, entry in cart.items():
        product = products_by_id.get(int(pid_str))
        if not product:
            continue
        qty = entry["quantity"]
        breakdown = calculate_tax_breakdown(product.unit_price, qty, product.is_taxable)
        lines.append({"product": product, "quantity": qty, "breakdown": breakdown})
        tax_input.append({"unit_price": product.unit_price, "quantity": qty, "is_taxable": product.is_taxable})

    return lines, totals_for_cart(tax_input)


@storefront_bp.route("/")
def home():
    category_id = request.args.get("category_id", type=int)
    query = request.args.get("q", "").strip()

    products_q = Product.query.filter_by(is_active=True)
    if category_id:
        products_q = products_q.filter_by(category_id=category_id)
    if query:
        products_q = products_q.filter(Product.name.ilike(f"%{query}%"))

    products = products_q.order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True, parent_id=None).all()

    flash_products = Product.query.filter_by(is_active=True).order_by(Product.id).limit(6).all()

    return render_template(
        "storefront/home.html",
        products=products,
        categories=categories,
        selected_category=category_id,
        query=query,
        flash_products=flash_products,
    )


@storefront_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    reviews = Review.query.filter_by(product_id=product.id).order_by(Review.created_at.desc()).all()
    similar_products = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active.is_(True),
    ).limit(4).all()
    return render_template(
        "storefront/product_detail.html",
        product=product,
        reviews=reviews,
        similar_products=similar_products,
    )


@storefront_bp.route("/product/<int:product_id>/review", methods=["POST"])
def add_review(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    reviewer_name = request.form.get("reviewer_name", "").strip()
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()

    if not reviewer_name or not rating or rating < 1 or rating > 5:
        flash("Enter your name and a rating from 1 to 5 to submit a review.", "warning")
        return redirect(url_for("storefront.product_detail", product_id=product.id))

    db.session.add(Review(product_id=product.id, reviewer_name=reviewer_name, rating=rating, comment=comment or None))
    db.session.commit()
    flash("Thanks for your review!", "success")
    return redirect(url_for("storefront.product_detail", product_id=product.id) + "#reviews")


@storefront_bp.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    product = Product.query.get_or_404(product_id)
    qty = max(1, request.form.get("quantity", 1, type=int))

    cart = session.get("cart", {})
    key = str(product_id)
    existing_qty = cart.get(key, {}).get("quantity", 0)
    new_qty = existing_qty + qty

    if product.inventory and new_qty > product.inventory.quantity_on_hand:
        new_qty = int(product.inventory.quantity_on_hand)

    if new_qty <= 0:
        flash(f"{product.name} is out of stock.", "warning")
    else:
        cart[key] = {"quantity": new_qty}
        session["cart"] = cart
        flash(f"Added {product.name} to your cart.", "success")

    return redirect(request.referrer or url_for("storefront.home"))


@storefront_bp.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    cart = session.get("cart", {})
    qty = request.form.get("quantity", 0, type=int)
    key = str(product_id)

    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = {"quantity": qty}

    session["cart"] = cart
    return redirect(url_for("storefront.cart"))


@storefront_bp.route("/cart")
def cart():
    lines, totals = _cart_products()
    return render_template("storefront/cart.html", lines=lines, totals=totals)


@storefront_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    customer = get_current_customer()
    if not customer:
        flash("Create an account or log in to place an order.", "warning")
        return redirect(url_for("account.login", next=url_for("storefront.checkout")))

    lines, totals = _cart_products()
    if not lines:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("storefront.home"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip() or customer.phone
        delivery_method = request.form.get("delivery_method", "click_and_collect")
        region = request.form.get("region", "Other")
        address = request.form.get("address", "").strip() or None
        payment_method = request.form.get("payment_method", "mtn_momo")

        delivery_fee = DELIVERY_FEES.get(region, DELIVERY_FEES["Other"]) if delivery_method == "home_delivery" else 0.0

        order = OnlineOrder(
            customer_id=customer.id,
            order_number=_generate_order_number(),
            delivery_method=delivery_method,
            delivery_address=address,
            delivery_region=region if delivery_method == "home_delivery" else None,
            delivery_fee=delivery_fee,
            subtotal=totals["subtotal"],
            tax_amount=totals["tax"],
            total_amount=round(totals["total"] + delivery_fee, 2),
            payment_method=payment_method,
        )
        db.session.add(order)
        db.session.flush()

        for line in lines:
            db.session.add(
                OnlineOrderItem(
                    order_id=order.id,
                    product_id=line["product"].id,
                    quantity=line["quantity"],
                    unit_price=line["product"].unit_price,
                    line_total=line["breakdown"]["line_total"],
                )
            )
            # Reserve stock immediately; actual decrement happens once staff start processing the order.
            if line["product"].inventory:
                line["product"].inventory.quantity_reserved = float(line["product"].inventory.quantity_reserved) + float(line["quantity"])

        payment_result = initiate_payment(
            payment_method, order.total_amount, phone_number=phone, reference=order.order_number
        )
        db.session.add(
            Payment(
                online_order_id=order.id,
                payment_method=payment_method,
                amount=order.total_amount,
                phone_number=phone,
                reference_number=payment_result["reference"],
                status=payment_result["status"],
            )
        )

        db.session.commit()
        session["cart"] = {}

        return redirect(url_for("storefront.order_status", order_number=order.order_number))

    return render_template(
        "storefront/checkout.html",
        lines=lines,
        totals=totals,
        delivery_fees=DELIVERY_FEES,
        provider_labels=PROVIDER_LABELS,
    )


@storefront_bp.route("/track-order", methods=["GET", "POST"])
def track_order():
    if request.method == "POST":
        order_number = request.form.get("order_number", "").strip()
        order = OnlineOrder.query.filter_by(order_number=order_number).first()
        if not order:
            flash(f"No order found with number {order_number}.", "warning")
            return redirect(url_for("storefront.track_order"))
        return redirect(url_for("storefront.order_status", order_number=order.order_number))

    return render_template("storefront/track_order.html")


@storefront_bp.route("/order/<order_number>")
def order_status(order_number):
    order = OnlineOrder.query.filter_by(order_number=order_number).first_or_404()
    return render_template("storefront/order_status.html", order=order)


@storefront_bp.route("/order/<order_number>/status")
def order_status_json(order_number):
    order = OnlineOrder.query.filter_by(order_number=order_number).first_or_404()
    return jsonify({"payment_status": order.payment_status, "status": order.status})


@storefront_bp.route("/order/<order_number>/simulate-approve", methods=["POST"])
def simulate_approve(order_number):
    """Demo-mode only: mimics the customer approving the USSD prompt."""
    order = OnlineOrder.query.filter_by(order_number=order_number).first_or_404()
    order.payment_status = "paid"
    order.status = "confirmed"
    for payment in Payment.query.filter_by(online_order_id=order.id).all():
        payment.status = "completed"
        payment.processed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "paid"})


@storefront_bp.route("/order/<order_number>/receipt.pdf")
def order_receipt_pdf(order_number):
    order = OnlineOrder.query.filter_by(order_number=order_number).first_or_404()
    buf = generate_online_order_receipt_pdf(order)
    return send_file(buf, mimetype="application/pdf", as_attachment=False, download_name=f"{order.order_number}.pdf")


@storefront_bp.route("/order/<order_number>/email-receipt", methods=["POST"])
def email_order_receipt(order_number):
    order = OnlineOrder.query.filter_by(order_number=order_number).first_or_404()
    to_email = request.form.get("email", "").strip() or (order.customer.email if order.customer else None)
    if not to_email:
        flash("Enter an email address to send your receipt to.", "warning")
        return redirect(url_for("storefront.order_status", order_number=order_number))

    email_order_receipt_task.delay(order.id, to_email)
    flash(f"Receipt for {order.order_number} queued to send to {to_email} (processed in the background by Celery).", "success")
    return redirect(url_for("storefront.order_status", order_number=order_number))


@storefront_bp.route("/feedback", methods=["GET", "POST"])
def feedback_form():
    if request.method == "POST":
        name = request.form.get("name", "").strip() or None
        email = request.form.get("email", "").strip() or None
        message = request.form.get("message", "").strip()
        rating = request.form.get("rating", type=int)

        if not message:
            flash("Please enter your feedback message.", "danger")
            return redirect(url_for("storefront.feedback_form"))

        entry = Feedback(name=name, email=email, message=message, rating=rating)
        db.session.add(entry)
        db.session.commit()

        live = send_feedback_notification(entry)
        if live:
            flash("Thanks for your feedback!", "success")
        else:
            flash("Thanks for your feedback! (Demo mode: no real email sent - configure MAIL_USERNAME to send for real.)", "success")
        return redirect(url_for("storefront.home"))

    return render_template("storefront/feedback.html")
