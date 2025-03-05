import uuid
from functools import wraps
from flask import Flask, render_template, url_for, request, jsonify, redirect, make_response

from api import *

flask_app = Flask(__name__)
flask_app.secret_key = "BW7aP$V#5!JSu8bz"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.cookies.get("session_id")
        client = app_state["redis_client"]
        if (not session_id) or (not client.sismember("session_id", session_id)):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@flask_app.route('/')
@flask_app.route('/<path:path>')
@login_required
def redirect_to_batch(path = None):
    return redirect(url_for("page"))

@flask_app.route("/page")
@login_required
def page():
    return render_template("page.html")

@flask_app.route("/read/<path:id>")
@login_required
def read(id):
    title = app_state["redis_client"].hget(f"doujinshi:{id}", "title")
    return render_template("reader.html", title = title)

@flask_app.route("/batch")
@login_required
def batch():
    return render_template("batch.html")

@flask_app.route("/group")
@login_required
def group():
    return render_template("group.html", token = app_state["settings"]["passwd"])

@flask_app.route("/other")
@login_required
def other():
    return render_template("other.html")

@flask_app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json()
        token = data.get("token")
        if token == app_state["settings"]["passwd"]:
            session_id = str(uuid.uuid4())
            client = app_state["redis_client"]
            client.sadd("session_id", session_id) # 储存session id
            client.expire("session_id", 60*60*24*7)
            response = make_response(jsonify(success=True))
            response.set_cookie("session_id", session_id, max_age=60*60*24*7)  # 7天
            return response
        else:
            return jsonify(success=False)
    return render_template("login.html")

@flask_app.route("/logout")
def logout():
    session_id = request.cookies.get("session_id")
    client = app_state["redis_client"]
    client.srem("session_id", session_id) # 删除session id
    response = make_response(redirect(url_for("login")))
    response.delete_cookie("session_id")
    return response