from datetime import timedelta

from flask import Flask, render_template, request, jsonify
from flask_login import LoginManager, current_user, login_required

from config import Config
from database import get_db, init_db
from models import get_user_by_id
from auth import auth_bp

app = Flask(__name__)
app.config.from_object(Config)

app.permanent_session_lifetime = timedelta(days=7)

init_db()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    # Called on every request for a logged-in user: Flask-Login decodes the
    # signed session cookie to get this id, then we re-fetch the fresh row
    # from the DB rather than trusting any user data cached in the cookie.
    return get_user_by_id(user_id)


app.register_blueprint(auth_bp)


#  To-Do List (Activity 1) 

@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html")
    return render_template("index.html")


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    sort_by = request.args.get("sort_by", "created_at")
    tag = request.args.get("tag")
    priority = request.args.get("priority")

    allowed_sorts = {"created_at", "due_date", "priority", "tag"}
    if sort_by not in allowed_sorts:
        sort_by = "created_at"

    query = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if tag:
        query += " AND tag = ?"
        params.append(tag)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    query += f" ORDER BY {sort_by}"

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "INSERT INTO tasks (title, due_date, priority, tag) VALUES (?, ?, ?, ?)",
        (data["title"], data["due_date"], data["priority"], data["tag"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "UPDATE tasks SET title=?, due_date=?, priority=?, tag=? WHERE id=?",
        (data["title"], data["due_date"], data["priority"], data["tag"], task_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})


@app.route("/api/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    conn = get_db()
    conn.execute("UPDATE tasks SET done = NOT done WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "toggled"})


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    app.run(debug=True)
