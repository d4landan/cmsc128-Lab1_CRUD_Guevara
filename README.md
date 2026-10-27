# CMSC 128 Lab 1 - To-Do List CRUD App

Tech Stack:

Frontend: HTML, CSS, JavaScript 

The frontend uses JavaScript to retrieve tasks from the backend and update the task list. It also handles adding, editing, completing, and deleting tasks.

Backend: Python, Flask

I chose Flask because it is lightweight, simple to set up, and well-suited for building a small web application. The backend provides API endpoints that the frontend can use to perform task operations.

Database: SQLite

I chose SQLite because it is simple and it doesn't require a separate database server. I think it is the most convenient for a local task management application.


How to Run the App:
1. Prerequisites<br>

    Python Version 3<br>
    pip<br>
    flask<br>   

2. Clone the Project Repository

4. Run the Application<br>
    python app.py

5. Open the Application<br>
    Open a web browser and go to:
    http://127.0.0.1:5000/


API Workflow:

1. User opens the application
2. Frontend requests GET /api/tasks
3. Flask retrieves tasks from SQLite
4. Tasks are returned as JSON
5. JavaScript displays the tasks
6. User adds/edits/completes/deletes a task
7. Frontend sends the appropriate API request
8. Flask updates SQLite
9. Frontend reloads the task list

