from flask import Flask, request, jsonify
import subprocess
import tempfile
import os

app = Flask(__name__)

@app.route("/run", methods=["POST"])
def run_code():
    data = request.json
    if not data or "code" not in data:
        return jsonify({"error": "code required"}), 400

    language = data.get("language", "python")
    code = data["code"]

    if language != "python":
        return jsonify({"error": "only python supported right now"}), 400

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--memory", "128m",
                "--cpus", "0.5",
                "--network", "none",
                "-v", f"{tmp_path}:/code/solution.py",
                "python:3.11-slim",
                "python", "/code/solution.py"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        return jsonify({
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

if __name__ == "__main__":
    app.run(port=5001, debug=True)
