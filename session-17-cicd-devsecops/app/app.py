"""DevSecOps demo application (Flask)."""
import datetime
import os
import platform
import sys

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
_start_time = datetime.datetime.now(datetime.timezone.utc)
_request_count = 0


def _count():
    global _request_count
    _request_count += 1


@app.route("/")
def home():
    _count()
    return render_template("index.html", version=APP_VERSION)


@app.route("/health")
def health():
    _count()
    uptime = (datetime.datetime.now(datetime.timezone.utc) - _start_time).total_seconds()
    return jsonify({"status": "healthy", "uptime_seconds": round(uptime, 2)})


@app.route("/api/status")
def status():
    _count()
    return jsonify(
        {
            "app": "DevSecOps Dashboard",
            "version": APP_VERSION,
            "status": "running",
            "python_version": sys.version.split()[0],
            "platform": platform.system(),
            "total_requests": _request_count,
        }
    )


@app.route("/api/greet/<name>")
def greet(name):
    _count()
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_")[:40]
    return jsonify({"message": f"Hello, {safe}! May your pipelines always pass.", "name": safe})


@app.route("/api/add", methods=["POST"])
def add_numbers():
    _count()
    data = request.get_json(silent=True) or {}
    if "number1" not in data or "number2" not in data:
        return jsonify({"error": "number1 and number2 are required"}), 400
    try:
        result = float(data["number1"]) + float(data["number2"])
    except (TypeError, ValueError):
        return jsonify({"error": "numbers must be numeric"}), 400
    return jsonify({"result": result})


if __name__ == "__main__":
    # nosec B104: binding to all interfaces is required inside a container (not exposed directly to the internet)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")))  # nosec B104
