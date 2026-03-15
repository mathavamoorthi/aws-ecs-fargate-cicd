import os
import socket
import psycopg2
from flask import Flask, jsonify, render_template

app = Flask(__name__)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASS = os.getenv("DB_PASS", "changeme")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        connect_timeout=3,
    )


@app.route("/")
def home():
    return render_template(
        "index.html",
        message="Hello from ECS Fargate",
        version=os.getenv("APP_VERSION", "dev"),
        hostname=socket.gethostname(),
    )


@app.route("/api")
def api():
    return jsonify(
        message="Hello from ECS Fargate",
        version=os.getenv("APP_VERSION", "dev"),
        hostname=socket.gethostname(),
    )


@app.route("/health")
def health():
    return jsonify(status="ok"), 200


@app.route("/db")
def db():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT NOW();")
            now = cur.fetchone()[0]
        return jsonify(db="up", now=now.isoformat())
    except Exception as e:
        return jsonify(db="down", error=str(e)), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
