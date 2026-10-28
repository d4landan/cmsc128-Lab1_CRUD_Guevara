# All authentication routes 

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user

from models import (
    create_user, verify_credentials, email_in_use, update_profile,
    get_user_by_email, create_password_reset, consume_password_reset,
    get_user_by_id,
)
from werkzeug.security import check_password_hash

auth_bp = Blueprint("auth", __name__)


def safe_next(url):
    """Only follow a "?next=" address if it is a path on THIS site, such as "/".
    Anything else ("https://evil.example", "//evil.example") is ignored, so the
    login page can't be used to bounce people to another website."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None


# Register 

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if not display_name:
            errors.append("Display name is required.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if email and email_in_use(email):
            errors.append("That email is already registered.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", email=email, display_name=display_name), 400

        user = create_user(email, display_name, password)
        login_user(user)
        flash("Account created. Welcome!", "success")
        return redirect(url_for("index"))      # Activity 3: straight to your To-Do list

    return render_template("register.html")


# Login / logout

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        user = verify_credentials(email, password)
        if user is None:
            # Same message for "no such account" and "wrong password" on
            # purpose -- doesn't tell an attacker which half was wrong.
            flash("Incorrect email or password.", "error")
            return render_template("login.html", email=email), 401

        # permanent + PERMANENT_SESSION_LIFETIME (app.py) keeps the signed
        # session cookie valid across browser restarts, not just refreshes.
        login_user(user, remember=True)
        flash(f"Welcome back, {user.display_name}.", "success")
        # Activity 3: straight to your To-Do list (or the page you were trying to open)
        return redirect(safe_next(request.args.get("next")) or url_for("index"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "success")
    return redirect(url_for("auth.login"))


# Profile

@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        display_name = request.form.get("display_name", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_new_password", "")
        current_password = request.form.get("current_password", "")

        errors = []
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if not display_name:
            errors.append("Display name is required.")
        if email_in_use(email, exclude_user_id=int(current_user.id)):
            errors.append("That email is already in use by another account.")

        if not check_password_hash(current_user.password_hash, current_password):
            errors.append("Current password is incorrect.")

        if new_password or confirm_password:
            if len(new_password) < 8:
                errors.append("New password must be at least 8 characters.")
            if new_password != confirm_password:
                errors.append("New passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("profile.html"), 400

        update_profile(
            int(current_user.id), email, display_name,
            new_password=new_password or None,
        )
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("profile.html")


# Password reset

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        user = get_user_by_email(email)

        reset_link = None
        if user is not None:
            token = create_password_reset(
                user.id, current_app.config["RESET_TOKEN_MAX_AGE_MINUTES"]
            )
            reset_link = url_for("auth.reset_password", token=token, _external=True)
            # DEMO ONLY 
            # Password recovery
            current_app.logger.info("PASSWORD RESET LINK for %s: %s", user.email, reset_link)

        # Same confirmation screen whether or not the email exists, so the
        # form can't be used to check who has an account.
        return render_template("forgot_password_sent.html", demo_link=reset_link)

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("reset_password.html", token=token), 400

        user_id = consume_password_reset(token)
        if user_id is None:
            flash("That reset link is invalid or has expired. Request a new one.", "error")
            return redirect(url_for("auth.forgot_password"))

        user = get_user_by_id(user_id)
        update_profile(int(user.id), user.email, user.display_name, new_password=password)
        flash("Password updated. You can log in with your new password now.", "success")
        return redirect(url_for("auth.login"))
    
    return render_template("reset_password.html", token=token)
