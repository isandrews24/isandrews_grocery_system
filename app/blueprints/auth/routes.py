from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User
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
