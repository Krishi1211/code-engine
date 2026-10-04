from celery import Celery
import json
import os
import shutil
import subprocess
import tempfile
import threading

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery('tasks', broker=REDIS_URL, backend=REDIS_URL)
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

DOCKER = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"

TIMEOUT_SECONDS = 60
MAX_OUTPUT_BYTES = 1_000_000  # per job, across stdout and stderr
EVENTS_TTL = 3600

LANGUAGE_CONFIG = {
    "python": {
        "image": "python:3.11-slim",
        "filename": "solution.py",
        "cmd": ["python", "-u", "/code/solution.py"]
    },
    "javascript": {
        "image": "node:18-slim",
        "filename": "solution.js",
        "cmd": ["node", "/code/solution.js"]
    },
    "cpp": {
        "image": "frolvlad/alpine-gxx",
        "filename": "solution.cpp",
        "cmd": ["sh", "-c", "g++ /code/solution.cpp -o /tmp/solution && /tmp/solution"]
    }
}


def events_key(job_id):
    return f"job:{job_id}:events"


def active_key(user):
    return f"user:{user}:active"


def publish(job_id, event):
    key = events_key(job_id)
    r.rpush(key, json.dumps(event))
    r.expire(key, EVENTS_TTL)


@app.task(bind=True)
def execute_code(self, language, code, user=None):
    job_id = self.request.id
    try:
        result = _run(job_id, language, code)
    except Exception as e:
        result = {"error": str(e)}
    finally:
        if user:
            # release the per-user concurrency slot taken at submit time
            if r.decr(active_key(user)) < 0:
                r.set(active_key(user), 0)
    publish(job_id, {"event": "done", **{k: v for k, v in result.items() if k in ("exit_code", "error")}})
    return result


def _run(job_id, language, code):
    if language not in LANGUAGE_CONFIG:
        return {"error": "unsupported language"}

    config = LANGUAGE_CONFIG[language]

    with tempfile.NamedTemporaryFile(
        suffix=f".{config['filename'].split('.')[-1]}",
        delete=False, mode="w"
    ) as f:
        f.write(code)
        tmp_path = f.name
    os.chmod(tmp_path, 0o644)

    container = f"job-{job_id}"
    output = {"stdout": [], "stderr": []}
    budget = {"left": MAX_OUTPUT_BYTES, "truncated": False}
    lock = threading.Lock()

    def pump(stream, name):
        for line in stream:
            with lock:
                if budget["left"] <= 0:
                    budget["truncated"] = True
                    continue
                line = line[:budget["left"]]
                budget["left"] -= len(line)
            output[name].append(line)
            publish(job_id, {"event": "output", "stream": name, "data": line})

    try:
        proc = subprocess.Popen(
            [
                DOCKER, "run", "--rm",
                "--name", container,
                "--memory", "128m",
                "--memory-swap", "128m",  # same as --memory: no swap, so the cap is hard
                "--cpus", "0.5",
                "--pids-limit", "64",
                "--network", "none",
                "-v", f"{tmp_path}:/code/{config['filename']}:ro",
                config["image"]
            ] + config["cmd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        threads = [
            threading.Thread(target=pump, args=(proc.stdout, "stdout"), daemon=True),
            threading.Thread(target=pump, args=(proc.stderr, "stderr"), daemon=True),
        ]
        for t in threads:
            t.start()
        try:
            proc.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            subprocess.run([DOCKER, "kill", container], capture_output=True)
            proc.kill()
            return {"error": "execution timed out"}
        for t in threads:
            t.join(timeout=2)
        return {
            "language": language,
            "stdout": "".join(output["stdout"]),
            "stderr": "".join(output["stderr"]),
            "exit_code": proc.returncode,
            "truncated": budget["truncated"]
        }
    finally:
        os.unlink(tmp_path)
