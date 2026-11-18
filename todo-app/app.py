import os

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_required
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from database import init_db, close_db
from models import get_user_by_id
from auth import auth_bp
from tasks import tasks_bp

app = Flask(__name__)
app.config.from_object(Config)

if app.config["BEHIND_PROXY"]:
    # Trust ONE proxy in front of us (ngrok / the host): use its X-Forwarded-* headers
    # for the real scheme (https), host name and client address.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.teardown_appcontext(close_db)   # close this request's database connection
init_db()


# login

login_manager = LoginManager()
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    # Runs on every request that carries a login cookie: turns the user id stored
    # in the signed cookie into a real user from the database.
    return get_user_by_id(user_id)


@login_manager.unauthorized_handler
def unauthorized():
    # A login-protected route was reached without logging in.
    # API calls get JSON 401 (the page's JavaScript handles it); pages go to the login form.
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not logged in."}), 401
    flash(login_manager.login_message, login_manager.login_message_category)
    return redirect(url_for("auth.login", next=request.path))


app.register_blueprint(auth_bp)
app.register_blueprint(tasks_bp)


@app.route("/")
@login_required
def index():
    return render_template("index.html")


# error handling 
# Visitors never see a raw error page or a stack trace. API calls get JSON,
# pages get a friendly screen with a way out. The details go to the server log.

MESSAGES = {
    404: ("Page not found", "We couldn't find that page. It may have moved, or the address may be wrong."),
    405: ("Not allowed", "That action isn't allowed on this page."),
    413: ("Request too large", "That request was too large to process."),
    429: ("Slow down a little", "Too many requests. Please wait a moment and try again."),
}


def error_response(code, title, message):
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), code
    return render_template("error.html", code=code, title=title, message=message), code


@app.errorhandler(HTTPException)
def handle_http_error(error):
    code = error.code or 500
    title, message = MESSAGES.get(code, ("Something went wrong", "Sorry, that request couldn't be completed."))
    return error_response(code, title, message)


@app.errorhandler(500)
def handle_server_error(error):
    app.logger.exception("Unhandled error on %s %s", request.method, request.path)
    return error_response(500, "Something went wrong", "Sorry, something broke on our side. Please try again in a moment.")


# response headers 

CSP = (
    "default-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "script-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


@app.after_request
def add_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"        # don't guess file types
    response.headers["X-Frame-Options"] = "DENY"                  # can't be put in someone else's <iframe>
    response.headers["Referrer-Policy"] = "same-origin"
    # Only our own scripts may run, so an injected <script> or onerror= would not execute.
    response.headers["Content-Security-Policy"] = CSP
    if request.path.startswith("/api/"):
        # Back after logout must not redisplay a cached copy of private data.
        response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    # debug=True runs an interactive debugger that lets anyone who reaches it run
    # code on your computer. It is OFF unless you ask: set FLASK_DEBUG=1 in .env.
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
