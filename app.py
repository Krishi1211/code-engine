from flask import Flask, request, jsonify
import subprocess
import tempfile
import os

app = Flask(__name__)

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
},
}

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    if not data or "code" not in data:
        return jsonify({"error": "code required"}), 400

    language = data.get("language", "python")
    code = data["code"]

    if language not in LANGUAGE_CONFIG:
        return jsonify({"error": f"unsupported language. choose from: {list(LANGUAGE_CONFIG.keys())}"}), 400

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
                "docker", "run", "--rm",
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
        return jsonify({
            "language": language,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "execution timed out"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(tmp_path)

@app.route("/languages", methods=["GET"])
def get_languages():
    return jsonify({"supported": list(LANGUAGE_CONFIG.keys())})

if __name__ == "__main__":
    app.run(port=5001, debug=True)