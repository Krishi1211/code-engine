from celery import Celery
import subprocess
import tempfile
import os

app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker"

LANGUAGE_CONFIG = {
    "python": {
        "image": "python:3.11-slim",
        "filename": "solution.py",
        "cmd": ["python", "/code/solution.py"]
    },
    "javascript": {
        "image": "node:18-slim",
        "filename": "solution.js",
        "cmd": ["node", "/code/solution.js"]
    },
    "cpp": {
        "image": "frolvlad/alpine-gxx",
        "filename": "solution.cpp",
        "cmd": ["sh", "-c", "g++ /code/solution.cpp -o /code/solution && /code/solution"]
    }
}

@app.task
def execute_code(language, code):
    if language not in LANGUAGE_CONFIG:
        return {"error": "unsupported language"}

    config = LANGUAGE_CONFIG[language]

    with tempfile.NamedTemporaryFile(
        suffix=f".{config['filename'].split('.')[-1]}",
        delete=False, mode="w"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [
                DOCKER, "run", "--rm",
                "--memory", "128m",
                "--cpus", "0.5",
                "--network", "none",
                "-v", f"{tmp_path}:/code/{config['filename']}",
                config["image"]
            ] + config["cmd"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "language": language,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "execution timed out"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.unlink(tmp_path)