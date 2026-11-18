import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db


class User(UserMixin):
    """What Flask-Login needs to know about the logged-in person. UserMixin
    supplies is_authenticated etc.; get_id() returns self.id."""

    def __init__(self, row):
        self.id = str(row["id"])
        self.email = row["email"]
        self.display_name = row["display_name"]
        self.password_hash = row["password_hash"]


def _norm(email):
    return email.lower().strip()


def _now():
    return datetime.now(timezone.utc)


# ================================================================== users ==

def get_user_by_id(user_id):
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return User(row) if row else None


def get_user_by_email(email):
    row = get_db().execute("SELECT * FROM users WHERE email = ?", (_norm(email),)).fetchone()
    return User(row) if row else None


def create_user(email, display_name, password):
    """Hash the password and insert the account. Raises sqlite3.IntegrityError if
    the email is taken (the UNIQUE constraint is the real guard against duplicates,
    even when two sign-ups arrive at the same moment)."""
    row = {
        "email": _norm(email),
        "display_name": display_name.strip(),
        "password_hash": generate_password_hash(password),
    }
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (email, display_name, password_hash) VALUES (?, ?, ?)",
        (row["email"], row["display_name"], row["password_hash"]),
    )
    conn.commit()
    return User({"id": cur.lastrowid, **row})   # no second SELECT needed


def verify_credentials(email, password):
    """The User if email + password are right, otherwise None. The caller gives the
    same message for both failures so the form can't be used to find which emails exist."""
    user = get_user_by_email(email)
    if user is None or not check_password_hash(user.password_hash, password):
        return None
    return user


def email_in_use(email, exclude_user_id=None):
    row = get_db().execute(
        "SELECT 1 FROM users WHERE email = ? AND id != ?",
        (_norm(email), exclude_user_id if exclude_user_id is not None else -1),
    ).fetchone()
    return row is not None


def update_profile(user_id, email, display_name, new_password=None):
    """Raises sqlite3.IntegrityError if the new email belongs to someone else."""
    conn = get_db()
    if new_password:
        conn.execute(
            "UPDATE users SET email = ?, display_name = ?, password_hash = ? WHERE id = ?",
            (_norm(email), display_name.strip(), generate_password_hash(new_password), user_id),
        )
    else:
        conn.execute(
            "UPDATE users SET email = ?, display_name = ? WHERE id = ?",
            (_norm(email), display_name.strip(), user_id),
        )
    conn.commit()


def update_password(user_id, new_password):
    """Change ONLY the password. (Resetting used to re-write the email and name too.)"""
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id),
    )
    conn.commit()


# ========================================================== password reset ==
# A reset link is a random token. Only its SHA-256 hash is stored, so a leaked
# database can't be used to reset anyone's password. The token expires and works once.

def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _parse_utc(value):
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)   # older rows have no timezone


def create_password_reset(user_id, max_age_minutes):
    """Returns the raw token (the only time it exists in readable form)."""
    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(minutes=max_age_minutes)

    conn = get_db()
    # Forget this user's earlier links (so only the newest works) and any expired
    # ones, so the table doesn't grow forever.
    conn.execute(
        "DELETE FROM password_resets WHERE user_id = ? OR expires_at < ?",
        (user_id, _now().isoformat(timespec="seconds")),
    )
    conn.execute(
        "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, _hash_token(token), expires_at.isoformat(timespec="seconds")),
    )
    conn.commit()
    return token


def reset_token_is_valid(token):
    """Read-only check, so the reset page can warn about a dead link BEFORE the user types."""
    row = get_db().execute(
        "SELECT expires_at FROM password_resets WHERE token_hash = ? AND used = 0",
        (_hash_token(token),),
    ).fetchone()
    return row is not None and _parse_utc(row["expires_at"]) > _now()


def consume_password_reset(token):
    """user_id if the token is valid (unused and unexpired) -- and mark it used. Else None."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, user_id, expires_at FROM password_resets WHERE token_hash = ? AND used = 0",
        (_hash_token(token),),
    ).fetchone()
    if row is None or _parse_utc(row["expires_at"]) <= _now():
        return None

    # "AND used = 0" makes this single-use even if the link is submitted twice at once.
    cur = conn.execute("UPDATE password_resets SET used = 1 WHERE id = ? AND used = 0", (row["id"],))
    conn.commit()
    return row["user_id"] if cur.rowcount == 1 else None


# ================================================================== tasks ==
# UBAC (Activity 3): every function takes the logged-in user's id and puts it in
# the WHERE clause. Someone else's task id matches no rows, so it behaves exactly
# like an id that doesn't exist.

# The sort order is chosen from this fixed list -- the user's text is never put in the SQL.
SORT_ORDERS = {
    "created_at": "created_at, id",
    "due_date": "due_date, id",
    "priority": "CASE priority WHEN 'High' THEN 0 WHEN 'Med' THEN 1 ELSE 2 END, id",
    "tag": "tag, id",
}

# Only what the page actually shows. user_id and created_at stay on the server.
TASK_COLUMNS = "id, title, due_date, priority, tag, done"


def list_tasks(user_id, tag=None, priority=None, sort_by="created_at"):
    sql = f"SELECT {TASK_COLUMNS} FROM tasks WHERE user_id = ?"
    params = [user_id]
    if tag:
        sql += " AND tag = ?"
        params.append(tag)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    sql += " ORDER BY " + SORT_ORDERS.get(sort_by, SORT_ORDERS["created_at"])
    return [dict(row) for row in get_db().execute(sql, params).fetchall()]


def create_task(user_id, title, due_date, priority, tag):
    """The owner is the logged-in user -- the caller passes current_user's id,
    never a value taken from the request body."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tasks (title, due_date, priority, tag, user_id) VALUES (?, ?, ?, ?, ?)",
        (title, due_date, priority, tag, user_id),
    )
    conn.commit()
    return cur.lastrowid


# update / toggle / delete return True if a row changed and False if this user has
# no task with that id. The id test and the owner test are ONE statement.

def update_task(user_id, task_id, title, due_date, priority, tag):
    conn = get_db()
    cur = conn.execute(
        "UPDATE tasks SET title = ?, due_date = ?, priority = ?, tag = ? WHERE id = ? AND user_id = ?",
        (title, due_date, priority, tag, task_id, user_id),
    )
    conn.commit()
    return cur.rowcount == 1


def toggle_task(user_id, task_id):
    conn = get_db()
    cur = conn.execute(
        "UPDATE tasks SET done = NOT done WHERE id = ? AND user_id = ?", (task_id, user_id)
    )
    conn.commit()
    return cur.rowcount == 1


def delete_task(user_id, task_id):
    conn = get_db()
    cur = conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    return cur.rowcount == 1
