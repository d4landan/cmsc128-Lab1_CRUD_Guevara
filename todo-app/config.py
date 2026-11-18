import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()  # reads a local .env file if there is one

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _flag(name, default=False):
    """Read an on/off environment variable: true/1/yes/on  ->  True."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in, e.g.\n"
            '  python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return value


_production = os.environ.get("APP_ENV", "development").lower() == "production"
_secure_cookies = _flag("COOKIE_SECURE")


class Config:
    # Signs the login cookies. Must be long, random and STABLE: if it changes,
    # every existing login stops working. There is deliberately NO default -- a
    # default key written in public code would let anyone forge a login cookie.
    SECRET_KEY = _required("SECRET_KEY")

    APP_ENV = "production" if _production else "development"
    DATABASE_PATH = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "app.db")

    # --- cookies -----------------------------------------------------------
    # `session` cookie: Flask's login session. Ends when the browser closes.
    SESSION_COOKIE_HTTPONLY = True       # JavaScript can't read it (limits XSS damage)
    SESSION_COOKIE_SAMESITE = "Lax"      # not sent on cross-site POSTs (CSRF defence)
    SESSION_COOKIE_SECURE = _secure_cookies   # only over HTTPS (turn on when hosted)
    # `remember_token` cookie: Flask-Login's "stay logged in" cookie. THIS is what
    # keeps you logged in after the browser is closed, for this long:
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = _secure_cookies

    # --- behind a tunnel / host proxy ----------------------------------------
    # ngrok and most hosts put a proxy in front of the app. Turn this on so Flask
    # trusts the proxy's "X-Forwarded-*" headers and knows the real public URL
    # and client address (used for reset links and rate limiting).
    BEHIND_PROXY = _flag("BEHIND_PROXY")

    # --- password recovery (no email server in this project) -----------------
    RESET_TOKEN_MAX_AGE_MINUTES = 30
    # Showing the reset link on screen is only safe on your own computer: on a
    # public site it would let ANYONE reset ANY account whose email they know.
    # So it is on in development and off in production unless you ask for it.
    SHOW_RESET_LINK = _flag("SHOW_RESET_LINK", default=not _production)

    # --- limits ---------------------------------------------------------------
    MAX_CONTENT_LENGTH = 16 * 1024       # no request body bigger than 16 KB
    # Failed logins allowed per email + IP address in the window. Setting
    # LOGIN_MAX_ATTEMPTS very high in .env switches the protection off, which is
    # how the pentest in the README shows the attack working "without" it.
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_WINDOW_SECONDS = 10 * 60
