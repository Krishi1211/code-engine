import json
import time

from flask import Flask, request, jsonify, g, send_from_directory
from flask_sock import Sock

from tasks import execute_code, r, events_key, LANGUAGE_CONFIG
from auth import register_user, check_login, make_token, user_from_token, require_auth
from limits import check_rate, acquire_slot, release_slot, MAX_CODE_BYTES

app = Flask(__name__, static_folder="static")
sock = Sock(app)

OWNER_TTL = 3600


def owner_key(job_id):
    return f"job:{job_id}:owner"


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    error = register_user(data.get("username"), data.get("password"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"token": make_token(data["username"])}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    if not check_login(data.get("username"), data.get("password")):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": make_token(data["username"])})


@app.route("/submit", methods=["POST"])
@require_auth
def submit():
    data = request.json
    if not data or "code" not in data:
        return jsonify({"error": "code required"}), 400

    language = data.get("language", "python")
    code = data["code"]

    if language not in LANGUAGE_CONFIG:
        return jsonify({"error": "unsupported language"}), 400
    if not isinstance(code, str) or len(code.encode()) > MAX_CODE_BYTES:
        return jsonify({"error": f"code must be a string of at most {MAX_CODE_BYTES} bytes"}), 413

    retry_after = check_rate(g.user)
    if retry_after:
        resp = jsonify({"error": "rate limit exceeded", "retry_after": retry_after})
        resp.headers["Retry-After"] = str(retry_after)
        return resp, 429
    if not acquire_slot(g.user):
        return jsonify({"error": "too many jobs running, wait for one to finish"}), 429

    try:
        task = execute_code.delay(language, code, user=g.user)
    except Exception:
        release_slot(g.user)
        raise
    r.set(owner_key(task.id), g.user, ex=OWNER_TTL)
    return jsonify({"job_id": task.id}), 202


@app.route("/result/<job_id>", methods=["GET"])
@require_auth
def result(job_id):
    if r.get(owner_key(job_id)) != g.user:
        return jsonify({"error": "job not found"}), 404
    task = execute_code.AsyncResult(job_id)
    if task.state == "PENDING":
        return jsonify({"status": "pending"})
    elif task.state == "SUCCESS":
        return jsonify({"status": "done", "result": task.result})
    elif task.state == "FAILURE":
        return jsonify({"status": "failed", "error": str(task.info)})
    return jsonify({"status": task.state})


@app.route("/languages", methods=["GET"])
def get_languages():
    return jsonify({"supported": list(LANGUAGE_CONFIG)})


@sock.route("/ws/<job_id>")
def stream(ws, job_id):
    """Streams a job's output line by line. The first message must be the auth token."""
    user = user_from_token(ws.receive(timeout=10) or "")
    if not user or r.get(owner_key(job_id)) != user:
        ws.send(json.dumps({"event": "error", "error": "not authorized for this job"}))
        return

    key = events_key(job_id)
    offset = 0
    deadline = time.time() + 180
    while time.time() < deadline:
        events = r.lrange(key, offset, -1)
        offset += len(events)
        for raw in events:
            ws.send(raw)
            if json.loads(raw).get("event") == "done":
                return
        if not events:
            time.sleep(0.1)
    ws.send(json.dumps({"event": "error", "error": "stream timed out"}))


if __name__ == "__main__":
    app.run(port=5001, debug=True)
