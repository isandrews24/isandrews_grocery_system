from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, session, flash, g

from app.extensions import db
from app.models import Customer, OnlineOrder
from app.services.customer_auth import (
    issue_email_otp, issue_phone_otp, check_email_otp, check_phone_otp,
)

account_bp = Blueprint("account", __name__, url_prefix="/account", template_folder="../../templates/account")


def get_current_customer():
    if "customer" not in g:
        customer_id = session.get("customer_id")
        g.customer = db.session.get(Customer, customer_id) if customer_id else None
    return g.customer


def customer_login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not get_current_customer():
            return redirect(url_for("account.login", next=request.path))
        return f(*args, **kwargs)
    return wrapped


def _flash_otp(label, result):
    if result["live"]:
        flash(f"{label} sent.", "success")
    else:
        flash(f"Demo mode: {label.lower()} code is {result['code']} (real {label.lower()} not sent - "
              f"configure real credentials in config.py to send for real).", "info")


@account_bp.route("/register", methods=["GET", "POST"])
def register():
    if get_current_customer():
        return redirect(url_for("account.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not name or not phone or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("account.register"))
        if password != confirm:
            flash("Passwords don't match.", "danger")
            return redirect(url_for("account.register"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return redirect(url_for("account.register"))
        if Customer.query.filter_by(phone=phone).first():
            flash("An account with that phone number already exists.", "danger")
            return redirect(url_for("account.register"))
        if Customer.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("account.register"))

        customer = Customer(name=name, phone=phone, email=email)
        customer.set_password(password)
        db.session.add(customer)
        db.session.flush()

        email_result = issue_email_otp(customer)
        phone_result = issue_phone_otp(customer)
        db.session.commit()

        session["pending_customer_id"] = customer.id
        _flash_otp("Email verification code", email_result)
        _flash_otp("SMS verification code", phone_result)
        return redirect(url_for("account.verify"))

    return render_template("account/register.html")


@account_bp.route("/verify", methods=["GET", "POST"])
def verify():
    customer_id = session.get("pending_customer_id") or session.get("customer_id")
    customer = db.session.get(Customer, customer_id) if customer_id else None
    if not customer:
        flash("Start by creating an account.", "warning")
        return redirect(url_for("account.register"))

    if customer.is_fully_verified:
        session["customer_id"] = customer.id
        session.pop("pending_customer_id", None)
        return redirect(url_for("account.dashboard"))

    if request.method == "POST":
        email_code = request.form.get("email_code", "").strip()
        phone_code = request.form.get("phone_code", "").strip()

        if not customer.email_verified and email_code:
            if check_email_otp(customer, email_code):
                customer.email_verified = True
            else:
                flash("That email code is incorrect or expired.", "danger")

        if not customer.phone_verified and phone_code:
            if check_phone_otp(customer, phone_code):
                customer.phone_verified = True
            else:
                flash("That SMS code is incorrect or expired.", "danger")

        db.session.commit()

        if customer.is_fully_verified:
            session["customer_id"] = customer.id
            session.pop("pending_customer_id", None)
            flash("Your account is verified!", "success")
            next_url = request.args.get("next") or url_for("account.dashboard")
            return redirect(next_url)

        return redirect(url_for("account.verify"))

    return render_template("account/verify.html", customer=customer)


@account_bp.route("/verify/resend-email", methods=["POST"])
def resend_email_otp():
    customer_id = session.get("pending_customer_id") or session.get("customer_id")
    customer = db.session.get(Customer, customer_id) if customer_id else None
    if not customer:
        return redirect(url_for("account.register"))
    result = issue_email_otp(customer)
    db.session.commit()
    _flash_otp("Email verification code", result)
    return redirect(url_for("account.verify"))


@account_bp.route("/verify/resend-phone", methods=["POST"])
def resend_phone_otp():
    customer_id = session.get("pending_customer_id") or session.get("customer_id")
    customer = db.session.get(Customer, customer_id) if customer_id else None
    if not customer:
        return redirect(url_for("account.register"))
    result = issue_phone_otp(customer)
    db.session.commit()
    _flash_otp("SMS verification code", result)
    return redirect(url_for("account.verify"))


@account_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_customer():
        return redirect(url_for("account.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        customer = Customer.query.filter(
            (Customer.phone == identifier) | (Customer.email == identifier)
        ).first()

        if not customer or not customer.check_password(password):
            flash("Incorrect phone/email or password.", "danger")
            return redirect(url_for("account.login"))

        if not customer.is_fully_verified:
            session["pending_customer_id"] = customer.id
            flash("Please finish verifying your account.", "warning")
            return redirect(url_for("account.verify"))

        session["customer_id"] = customer.id
        next_url = request.args.get("next") or url_for("account.dashboard")
        return redirect(next_url)

    return render_template("account/login.html")


@account_bp.route("/logout")
def logout():
    session.pop("customer_id", None)
    session.pop("pending_customer_id", None)
    return redirect(url_for("storefront.home"))


@account_bp.route("/")
@customer_login_required
def dashboard():
    customer = get_current_customer()
    orders = OnlineOrder.query.filter_by(customer_id=customer.id).order_by(OnlineOrder.placed_at.desc()).all()
    return render_template("account/dashboard.html", customer=customer, orders=orders)
