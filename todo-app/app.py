from datetime import timedelta

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, current_user, login_required

from config import Config
from database import get_db, init_db
from models import get_user_by_id
from auth import auth_bp

app = Flask(__name__)
app.config.from_object(Config)

# The session cookie is signed with the SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)

init_db()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"
login_manager.init_app(app)


@login_manager.unauthorized_handler
def unauthorized():
    # Runs when @login_required fails
    # API calls get a JSON 401, while page requests get redirected to the login page
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not logged in."}), 401
    flash(login_manager.login_message, login_manager.login_message_category)
    return redirect(url_for("auth.login", next=request.path))


@login_manager.user_loader
def load_user(user_id):
    # Called on every request for a logged-in user: Flask-Login decodes the
    # signed session cookie to get this id, then we re-fetch the fresh row
    # from the DB rather than trusting any user data cached in the cookie.
    return get_user_by_id(user_id)


app.register_blueprint(auth_bp)


#  To-Do List  

def current_user_id():
    return int(current_user.id)


def not_found():
    return jsonify({"error": "Not found."}), 404


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    sort_by = request.args.get("sort_by", "created_at")
    tag = request.args.get("tag")
    priority = request.args.get("priority")

    allowed_sorts = {"created_at", "due_date", "priority", "tag"}
    if sort_by not in allowed_sorts:
        sort_by = "created_at"

    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [current_user_id()]
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
@login_required
def create_task():
    data = request.get_json()
    conn = get_db()
    # user_id is NOT read from the request: the new task is owned by whoever is logged in
    conn.execute(
        "INSERT INTO tasks (title, due_date, priority, tag, user_id) VALUES (?, ?, ?, ?, ?)",
        (data["title"], data["due_date"], data["priority"], data["tag"], current_user_id()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    data = request.get_json()
    conn = get_db()
    # "AND user_id = ?" is the ownership check
    cur = conn.execute(
        "UPDATE tasks SET title=?, due_date=?, priority=?, tag=? WHERE id=? AND user_id=?",
        (data["title"], data["due_date"], data["priority"], data["tag"], task_id, current_user_id()),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed == 0:
        return not_found()
    return jsonify({"status": "updated"})


@app.route("/api/tasks/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id):
    conn = get_db()
    cur = conn.execute(
        "UPDATE tasks SET done = NOT done WHERE id=? AND user_id=?",
        (task_id, current_user_id()),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed == 0:
        return not_found()
    return jsonify({"status": "toggled"})


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM tasks WHERE id=? AND user_id=?",
        (task_id, current_user_id()),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed == 0:
        return not_found()
    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    app.run(debug=True)
