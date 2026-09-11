from flask import Flask, render_template, request, jsonify
from database import get_db, init_db

app = Flask(__name__)
init_db()

@app.route("/")
def index():
    return render_template("index.html")

# READ 
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

# CREATE
@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "INSERT INTO tasks (title, due_date, priority, tag) VALUES (?, ?, ?, ?)",
        (data["title"], data["due_date"], data["priority"], data["tag"])
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201

# UPDATE
@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json()
    conn = get_db()
    conn.execute(
        "UPDATE tasks SET title=?, due_date=?, priority=?, tag=? WHERE id=?",
        (data["title"], data["due_date"], data["priority"], data["tag"], task_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})

# TASK STATUS
@app.route("/api/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    conn = get_db()
    conn.execute("UPDATE tasks SET done = NOT done WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "toggled"})

# DELETE
@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    app.run(debug=True)