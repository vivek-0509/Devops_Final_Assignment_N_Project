import pytest

from app.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_home(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"DevSecOps Dashboard" in r.data


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "healthy"


def test_status(client):
    data = client.get("/api/status").get_json()
    assert data["status"] == "running"
    assert data["version"]


def test_greet(client):
    data = client.get("/api/greet/Vivek").get_json()
    assert "Vivek" in data["message"]


def test_add_numbers(client):
    r = client.post("/api/add", json={"number1": 10, "number2": 20})
    assert r.status_code == 200
    assert r.get_json()["result"] == 30


def test_add_numbers_missing_fields(client):
    r = client.post("/api/add", json={"number1": 5})
    assert r.status_code == 400
