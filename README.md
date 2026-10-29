# CMSC 128 Lab 3 - User-Based Access Control (UBAC)

# How Lab 1 and 2 were merged:
    act3-ubac was created from merging act2-accounts with lab 1 which was in main it was merged with git merge.

    git checkout act2-accounts
    git checkout -b act3-ubac
    git merge main    

    there was no merge conflicts

After merging, the task table and routes were still shared by everyone

# What changed:
 `database.py`  `tasks` gets a `user_id` column (foreign key to `users.id`, `NOT NULL`, `ON DELETE CASCADE`). `init_db()` upgrades an older database automatically 

 `app.py`  Every task route gets `@login_required` and filters by the logged-in user's id. `/` now requires login. Unauthenticated API calls get a JSON 401 

 `static/script.js` Task requests go through `apiFetch()`: a 401 sends the user to the login page, and a failed save shows an error instead of "Task updated" 

 `templates/`  A "My tasks" link was added to the navigation

 Tasks had no owner
 On startup `init_db()` rebuilds the `tasks` table with the new column and gives
 the old tasks to the earliest-registered account. If no account exists yet, the
 old table is kept as `tasks_old` instead of being deleted.


# Schema

One user has many tasks, each task has exactly one owner.

Users and tasks are in separate tabkes. Nothing about the user (name, email) is copied into `tasks`, so the schema stays normalized.

`PRAGMA foreign_keys = ON` is set on every connection so SQLite enforces the foreign key


# How ownership is checked

The user id always comes from the session (`current_user`), never from the request body or URL. Every task query includes it

"SELECT * FROM tasks WHERE user_id = ?"

"INSERT INTO tasks (title, due_date, priority, tag, user_id) VALUES (?, ?, ?, ?, ?)"

"UPDATE tasks SET title=?, due_date=?, priority=?, tag=? WHERE id=? AND user_id=?"
"UPDATE tasks SET done = NOT done WHERE id=? AND user_id=?"
"DELETE FROM tasks WHERE id=? AND user_id=?"


# How to Run the App: 

(Requires Python 3.9+)

1. git checkout act3-ubac

2. python -m venv venv     #Windows
3. venv\Scripts\activate   #Windows
4. pip install -r requirements.txt

5. python app.py

6. Open http://127.0.0.1:5000

