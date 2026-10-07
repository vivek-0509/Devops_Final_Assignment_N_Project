"""Tiny Flask web API around the calculator so the app can be deployed as a container."""
import os

from flask import Flask, jsonify, request

from app.calculator import OPERATIONS

app = Flask(__name__)
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")


@app.get("/")
def index():
    return jsonify(
        {
            "app": "Session 16 Calculator API",
            "version": APP_VERSION,
            "usage": "/calc?op=add&a=10&b=5  (ops: add, subtract, multiply, divide)",
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "healthy"})


@app.get("/calc")
def calc():
    op = request.args.get("op", "add")
    if op not in OPERATIONS:
        return jsonify({"error": f"unknown operation '{op}'"}), 400
    try:
        a = float(request.args.get("a", 0))
        b = float(request.args.get("b", 0))
        result = OPERATIONS[op](a, b)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"op": op, "a": a, "b": b, "result": result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
