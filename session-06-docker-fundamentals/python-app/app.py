from flask import Flask
import socket

app = Flask(__name__)


@app.route("/")
def hello():
    return f"""<!DOCTYPE html>
<html>
  <head><title>Python Hello World</title></head>
  <body style="font-family: sans-serif; text-align: center; margin-top: 80px;">
    <h1>Hello World from Python (Flask) + Docker!</h1>
    <p>Served from container <b>{socket.gethostname()}</b> on port 5000</p>
  </body>
</html>"""


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
