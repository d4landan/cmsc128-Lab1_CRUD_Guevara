import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT NOT NULL UNIQUE,
            display_name  TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Store one-time tokens for password reset links
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash  TEXT NOT NULL,
            expires_at  TIMESTAMP NOT NULL,
            used        INTEGER NOT NULL DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    _upgrade_tasks_table(conn)   # a database from Activity 2 has tasks with no owner
    conn.execute(CREATE_TASKS)   # does nothing if the table already exists

    conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)")

    conn.commit()
    conn.close()


# Every task belongs to one user
# The `user_id` column is a foreign key to the `users` table, and is NOT NULL.
CREATE_TASKS = """
    CREATE TABLE IF NOT EXISTS tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        due_date    TEXT,
        priority    TEXT DEFAULT 'Med',
        tag         TEXT,
        done        INTEGER DEFAULT 0,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
    )
"""


def _upgrade_tasks_table(conn):
    # If the tasks table exists but has no user_id column, we need to migrate it
    # For the Activity 2 database with no ownership
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
    if not columns or "user_id" in columns:
        return  # new database or already upgraded

    conn.execute("ALTER TABLE tasks RENAME TO tasks_old")
    conn.execute(CREATE_TASKS)

    owner = conn.execute("SELECT MIN(id) AS id FROM users").fetchone()["id"]
    if owner is None:
        return
    conn.execute(
        """
        INSERT INTO tasks (id, title, due_date, priority, tag, done, created_at, user_id)
        SELECT id, title, due_date, priority, tag, done, created_at, ? FROM tasks_old
        """,
        (owner,),
    )
    conn.execute("DROP TABLE tasks_old")
