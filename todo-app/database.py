import sqlite3

from flask import g, has_app_context

from config import Config

DB_PATH = Config.DATABASE_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row            # rows can be read by column name
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless asked
    return conn


def get_db():
    """The connection for this request. (Outside a request, e.g. a script, you
    get a fresh connection and must close it yourself.)"""
    if not has_app_context():
        return _connect()
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(exception=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# Every task belongs to one user. ON DELETE CASCADE: deleting an account deletes
# that account's tasks (PRAGMA foreign_keys = ON above makes SQLite enforce it).
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


def init_db():
    """Create missing tables/indexes and upgrade an older database. Safe to run on every start."""
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT NOT NULL UNIQUE,
                display_name  TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # A hash of the reset token is stored, never the token itself.
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

        _upgrade_tasks_table(conn)   # a database from before Activity 3 has tasks with no owner
        conn.execute(CREATE_TASKS)   # does nothing if the table already exists

        # --- indexes -------------------------------------------------------
        # Every task query starts with WHERE user_id = ? and by default sorts by
        # created_at, so one index on (user_id, created_at) finds the user's rows
        # AND hands them back already sorted. It also covers lookups by user_id
        # alone, so the older single-column index is redundant and is dropped.
        conn.execute("DROP INDEX IF EXISTS idx_tasks_user")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks(user_id, created_at)")
        # Redeeming a reset link looks the token up by its hash.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_resets_token ON password_resets(token_hash)")

        conn.commit()
    finally:
        conn.close()


def _upgrade_tasks_table(conn):
    """One-time upgrade for a database created before Activity 3.

    Old `tasks` rows have no owner, and SQLite can't add a NOT NULL foreign key
    to an existing table, so the table is rebuilt: rename the old one, create the
    new one, copy the rows across, drop the old one. The old tasks go to the
    earliest-registered account. If no accounts exist there is nobody to give
    them to, so the old table is kept as `tasks_old` instead of being deleted.
    """
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
    if not columns or "user_id" in columns:
        return  # brand-new database, or already upgraded

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
