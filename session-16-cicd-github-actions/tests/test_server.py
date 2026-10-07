import pytest

from app.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Calculator" in r.get_json()["app"]


def test_health(client):
    assert client.get("/health").get_json() == {"status": "healthy"}


def test_calc_add(client):
    r = client.get("/calc?op=add&a=10&b=5")
    assert r.status_code == 200
    assert r.get_json()["result"] == 15


def test_calc_divide_by_zero(client):
    r = client.get("/calc?op=divide&a=1&b=0")
    assert r.status_code == 400


def test_calc_unknown_op(client):
    assert client.get("/calc?op=power&a=1&b=2").status_code == 400
