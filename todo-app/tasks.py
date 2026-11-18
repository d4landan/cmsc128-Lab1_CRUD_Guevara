from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

import models
from validators import validate_task

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@tasks_bp.before_request
@login_required
def require_login():
    """Runs before EVERY route in this blueprint. Not logged in -> JSON 401
    (the handler is in app.py); logged in -> returns None and the route runs."""


def current_user_id():
    return int(current_user.id)   # Flask-Login keeps the id as a string


def not_found():
    return jsonify({"error": "Not found."}), 404


def invalid(errors):
    return jsonify({"errors": errors}), 400


@tasks_bp.route("", methods=["GET"])
def list_tasks():
    tasks = models.list_tasks(
        current_user_id(),
        tag=request.args.get("tag"),
        priority=request.args.get("priority"),
        sort_by=request.args.get("sort_by", "created_at"),
    )
    return jsonify(tasks)


@tasks_bp.route("", methods=["POST"])
def create_task():
    task, errors = validate_task(request.get_json(silent=True) or {})
    if errors:
        return invalid(errors)
    # The owner is the logged-in user. A "user_id" in the request body is never read.
    task_id = models.create_task(current_user_id(), **task)
    return jsonify({"status": "created", "id": task_id}), 201


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task, errors = validate_task(request.get_json(silent=True) or {})
    if errors:
        return invalid(errors)
    if not models.update_task(current_user_id(), task_id, **task):
        return not_found()
    return jsonify({"status": "updated"})


@tasks_bp.route("/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    if not models.toggle_task(current_user_id(), task_id):
        return not_found()
    return jsonify({"status": "toggled"})


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    if not models.delete_task(current_user_id(), task_id):
        return not_found()
    return jsonify({"status": "deleted"})
