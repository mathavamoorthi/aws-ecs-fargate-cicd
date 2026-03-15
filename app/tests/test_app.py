import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


def test_home():
    client = app.test_client()
    r = client.get("/")
    assert r.status_code == 200
    assert b"Northwind" in r.data


def test_api():
    client = app.test_client()
    r = client.get("/api")
    assert r.status_code == 200
    assert r.get_json()["message"].startswith("Hello")


def test_health():
    client = app.test_client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"
