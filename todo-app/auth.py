"""
auth.py
-------
Account routes: sign up, log in / out, profile, password recovery.
The rules for what counts as valid input are in validators.py; the SQL is in models.py.
This file only decides what to do with a request and what to show back.
"""

import sqlite3

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

import ratelimit
import validators as v
from models import (
    create_user, verify_credentials, email_in_use, update_profile, update_password,
    get_user_by_email, create_password_reset, consume_password_reset, reset_token_is_valid,
)

auth_bp = Blueprint("auth", __name__)

DUPLICATE_EMAIL = "That email is already registered."


def safe_next(url):
    """Only follow a "?next=" address if it is a path on THIS site, such as "/".
    Anything else ("https://evil.example", "//evil.example") is ignored, so the
    login page can't be used to bounce people to another website."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None


def collect(errors, **checks):
    """errors["field"] = message for every check that failed. Keeps the first message per field."""
    for field, message in checks.items():
        if message and field not in errors:
            errors[field] = message
    return errors


# ------------------------------------------------------------- register --

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("register.html")

    email = request.form.get("email", "").strip()
    display_name = request.form.get("display_name", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    errors = collect(
        {},
        email=v.check_email(email),
        display_name=v.check_display_name(display_name),
        password=v.check_password(password),
        confirm_password=v.check_match(password, confirm),
    )
    if "email" not in errors and email_in_use(email):
        errors["email"] = DUPLICATE_EMAIL
    if errors:
        return render_template("register.html", errors=errors, email=email, display_name=display_name), 400

    try:
        user = create_user(email, display_name, password)   # hashes the password, then INSERTs
    except sqlite3.IntegrityError:   # the same email was registered a moment ago
        return render_template("register.html", errors={"email": DUPLICATE_EMAIL},
                               email=email, display_name=display_name), 400

    login_user(user)
    flash("Account created. Welcome!", "success")
    return redirect(url_for("index"))      # straight to your To-Do list


# ---------------------------------------------------------------- login --

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    # Slow down password guessing: too many failures for this email from this address -> wait.
    limiter_key = f"{request.remote_addr}|{email.lower()}"
    max_attempts = current_app.config["LOGIN_MAX_ATTEMPTS"]
    window = current_app.config["LOGIN_WINDOW_SECONDS"]
    if ratelimit.is_blocked(limiter_key, max_attempts, window):
        minutes = max(1, window // 60)
        return render_template(
            "login.html", email=email,
            errors={"form": f"Too many failed attempts. Please wait about {minutes} minutes and try again."},
        ), 429

    user = verify_credentials(email, password)
    if user is None:
        ratelimit.record_failure(limiter_key)
        # Same message for "no such account" and "wrong password" on purpose --
        # it doesn't tell an attacker which half was wrong.
        return render_template("login.html", email=email,
                               errors={"form": "Incorrect email or password."}), 401

    ratelimit.clear(limiter_key)
    # remember=True also sets the long-lived `remember_token` cookie, which is what
    # keeps you logged in after the browser has been closed.
    login_user(user, remember=True)
    flash(f"Welcome back, {user.display_name}.", "success")
    return redirect(safe_next(request.args.get("next")) or url_for("index"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "success")
    return redirect(url_for("auth.login"))


# -------------------------------------------------------------- profile --

@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "GET":
        return render_template("profile.html", values={
            "email": current_user.email, "display_name": current_user.display_name})

    email = request.form.get("email", "").strip()
    display_name = request.form.get("display_name", "").strip()
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_new_password", "")
    current_password = request.form.get("current_password", "")
    user_id = int(current_user.id)

    errors = collect({}, email=v.check_email(email), display_name=v.check_display_name(display_name))
    if "email" not in errors and email_in_use(email, exclude_user_id=user_id):
        errors["email"] = "That email is already used by another account."
    if new_password or confirm:
        collect(errors,
                new_password=v.check_password(new_password, "New password"),
                confirm_new_password=v.check_match(new_password, confirm, "New passwords"))
    # Any change needs the current password, so someone at an unattended, already
    # logged-in computer can't quietly change the email or password.
    if not check_password_hash(current_user.password_hash, current_password):
        errors["current_password"] = "Current password is incorrect."

    if errors:
        # Show back what was typed, so nothing the user entered is silently thrown away.
        return render_template("profile.html", errors=errors,
                               values={"email": email, "display_name": display_name}), 400

    try:
        update_profile(user_id, email, display_name, new_password=new_password or None)
    except sqlite3.IntegrityError:
        return render_template("profile.html", errors={"email": "That email is already used by another account."},
                               values={"email": email, "display_name": display_name}), 400
    flash("Profile updated.", "success")
    return redirect(url_for("auth.profile"))


# ------------------------------------------------------- password reset --

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip()
    error = v.check_email(email)
    if error:
        return render_template("forgot_password.html", errors={"email": error}, email=email), 400

    user = get_user_by_email(email)
    reset_link = None
    if user is not None:
        token = create_password_reset(user.id, current_app.config["RESET_TOKEN_MAX_AGE_MINUTES"])
        link = url_for("auth.reset_password", token=token, _external=True)
        current_app.logger.info("PASSWORD RESET LINK for %s: %s", user.email, link)
        # There is no email server in this project. In development the link is shown
        # on screen; on a public site it must NOT be (see SHOW_RESET_LINK in config.py).
        if current_app.config["SHOW_RESET_LINK"]:
            reset_link = link

    # Same screen whether or not the email exists, so the form can't be used to
    # find out who has an account.
    return render_template("forgot_password_sent.html", demo_link=reset_link)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "GET":
        if not reset_token_is_valid(token):   # warn now, not after the user has typed a password
            flash("That reset link is invalid or has expired. Request a new one.", "error")
            return redirect(url_for("auth.forgot_password"))
        return render_template("reset_password.html")

    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")
    errors = collect({}, password=v.check_password(password, "New password"),
                     confirm_password=v.check_match(password, confirm))
    if errors:
        return render_template("reset_password.html", errors=errors), 400

    user_id = consume_password_reset(token)
    if user_id is None:
        flash("That reset link is invalid or has expired. Request a new one.", "error")
        return redirect(url_for("auth.forgot_password"))

    update_password(user_id, password)   # one UPDATE (was: 2 lookups + a rewrite of email and name)
    flash("Password updated. You can log in with your new password now.", "success")
    return redirect(url_for("auth.login"))
