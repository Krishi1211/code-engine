from flask import Flask, request, jsonify
from tasks import execute_code

app = Flask(__name__)

@app.route("/submit", methods=["POST"])
def submit():
    data = request.json
    if not data or "code" not in data:
        return jsonify({"error": "code required"}), 400

    language = data.get("language", "python")
    code = data["code"]

    task = execute_code.delay(language, code)
    return jsonify({"job_id": task.id}), 202

@app.route("/result/<job_id>", methods=["GET"])
def result(job_id):
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
    return jsonify({"supported": ["python", "javascript", "cpp"]})

if __name__ == "__main__":
    app.run(port=5001, debug=True)