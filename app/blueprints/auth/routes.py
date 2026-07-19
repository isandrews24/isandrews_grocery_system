from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User, StaffInvite
from app.services.audit import log_activity

auth_bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="../../templates/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard") if current_user.role != "cashier" else url_for("pos.terminal"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active_user:
            login_user(user)
            log_activity(user, "LOGIN", "users", user.id)
            db.session.commit()
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for("admin.dashboard") if user.role != "cashier" else url_for("pos.terminal"))

        log_activity(None, "LOGIN_FAILED", "users", username or "unknown")
        db.session.commit()
        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_activity(current_user, "LOGOUT", "users", current_user.id)
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/accept-invite/<token>", methods=["GET", "POST"])
def accept_invite(token):
    invite = StaffInvite.query.filter_by(token=token).first()
    if not invite or not invite.is_pending:
        flash("This invite link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not full_name or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.accept_invite", token=token))
        if password != confirm:
            flash("Passwords don't match.", "danger")
            return redirect(url_for("auth.accept_invite", token=token))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return redirect(url_for("auth.accept_invite", token=token))
        if User.query.filter_by(username=username).first():
            flash("That username is already taken.", "danger")
            return redirect(url_for("auth.accept_invite", token=token))

        user = User(username=username, email=invite.email, full_name=full_name, role=invite.role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        invite.accepted_at = datetime.utcnow()
        log_activity(user, "CREATE", "users", user.id, new_values={"username": username, "role": invite.role, "via": "invite"})
        db.session.commit()
        flash("Your account is set up - you can log in now.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/accept_invite.html", invite=invite)
