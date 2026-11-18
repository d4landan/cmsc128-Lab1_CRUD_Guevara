"""
validators.py
-------------
Input checks shared by the auth routes and the task routes. Each `check_*`
function returns an error message, or None when the value is fine. Before this
file existed, register, profile and reset-password each had their own copy of
the same rules.
"""

import re

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128   # stops absurdly long inputs being fed to the hasher

VALID_PRIORITIES = ("Low", "Med", "High")
VALID_TAGS = ("School", "Personal", "Others")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$")   # what <input type=datetime-local> sends


def check_email(email):
    if not email:
        return "Email is required."
    if len(email) > 254 or not _EMAIL_RE.match(email):
        return "Enter a valid email address, like name@example.com."


def check_display_name(name):
    if not name:
        return "Display name is required."
    if len(name) > 50:
        return "Display name must be 50 characters or fewer."


def check_password(password, label="Password"):
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"{label} must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"{label} must be {MAX_PASSWORD_LENGTH} characters or fewer."


def check_match(password, confirm, label="Passwords"):
    if password != confirm:
        return f"{label} do not match."


def validate_task(data):
    """Returns (clean_values, errors). `errors` is {field: message}."""
    def text(key):
        value = data.get(key)
        return value.strip() if isinstance(value, str) else ""

    title, due_date = text("title"), text("due_date")
    priority, tag = data.get("priority"), data.get("tag")

    errors = {}
    if not title:
        errors["title"] = "Task title is required."
    elif len(title) > 200:
        errors["title"] = "Task title must be 200 characters or fewer."
    if not due_date:
        errors["due_date"] = "Due date is required."
    elif not _DUE_RE.match(due_date):
        errors["due_date"] = "That due date isn't valid."
    if priority not in VALID_PRIORITIES:
        errors["priority"] = "Priority must be Low, Med or High."
    if tag not in VALID_TAGS:
        errors["tag"] = "Tag must be School, Personal or Others."

    return {"title": title, "due_date": due_date, "priority": priority, "tag": tag}, errors
