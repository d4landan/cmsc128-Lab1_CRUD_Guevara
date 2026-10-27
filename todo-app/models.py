import secrets
import hashlib
from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db


class User(UserMixin):
    """Flask-Login just needs .id (via get_id) and an is_authenticated flag,
    which UserMixin provides defaults for. We attach the extra fields we
    actually use in templates."""

    def __init__(self, row):
        self.id = str(row["id"])
        self.email = row["email"]
        self.display_name = row["display_name"]
        self.password_hash = row["password_hash"]


# Lookups

def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return User(row) if row else None


def get_user_by_email(email):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return User(row) if row else None


# Mutations

def create_user(email, display_name, password):
    email = email.lower().strip()
    password_hash = generate_password_hash(password)
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, display_name, password_hash) VALUES (?, ?, ?)",
            (email, display_name.strip(), password_hash),
        )
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()
    return get_user_by_id(new_id)


def verify_credentials(email, password):
    # Returns a User if the email/password are correct, else None
    user = get_user_by_email(email)
    if user is None:
        return None
    if not check_password_hash(user.password_hash, password):
        return None
    return user


def email_in_use(email, exclude_user_id=None):
    conn = get_db()
    if exclude_user_id is None:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ? AND id != ?",
            (email.lower().strip(), exclude_user_id),
        ).fetchone()
    conn.close()
    return row is not None


def update_profile(user_id, email, display_name, new_password=None):
    conn = get_db()
    if new_password:
        conn.execute(
            "UPDATE users SET email = ?, display_name = ?, password_hash = ? WHERE id = ?",
            (email.lower().strip(), display_name.strip(), generate_password_hash(new_password), user_id),
        )
    else:
        conn.execute(
            "UPDATE users SET email = ?, display_name = ? WHERE id = ?",
            (email.lower().strip(), display_name.strip(), user_id),
        )
    conn.commit()
    conn.close()


# Password reset flow
# We never email a raw token to the DB and never store it in plaintext.
# Flow: generate random token -> show/"send" the raw token to the user ->
# store only sha256(token) with an expiry -> on redemption, hash whatever
# the user submits and look for a matching, unused, unexpired row.

def create_password_reset(user_id, max_age_minutes):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=max_age_minutes)

    conn = get_db()
    # invalidate any older unused tokens for this user first
    conn.execute(
        "UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, token_hash, expires_at.isoformat()),
    )
    conn.commit()
    conn.close()
    return token  # the raw token is only ever returned here, never stored


def consume_password_reset(token):
    """If the token is valid, marks it used and returns the user_id.
    Otherwise returns None. One-shot: calling this twice with the same
    token the second time will fail, because `used` is now 1."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM password_resets WHERE token_hash = ? AND used = 0",
        (token_hash,),
    ).fetchone()

    if row is None:
        conn.close()
        return None

    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        conn.close()
        return None

    conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return row["user_id"]
