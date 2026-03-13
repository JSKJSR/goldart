"""Tests for multi-user authentication."""
from unittest.mock import patch
from werkzeug.security import generate_password_hash


# ── Registration ──────────────────────────────────────────────────────────────

@patch("goldart.blueprints.auth.get_user_by_email", return_value=None)
@patch("goldart.blueprints.auth.get_user_by_username", return_value=None)
@patch("goldart.blueprints.auth.create_user", return_value=1)
def test_register_success(mock_create, mock_by_user, mock_by_email, client):
    resp = client.post("/auth/register", data={
        "username": "newuser",
        "email": "new@example.com",
        "password": "securepass123",
        "confirm": "securepass123",
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]
    mock_create.assert_called_once()


def test_register_short_username(client):
    resp = client.post("/auth/register", data={
        "username": "ab",
        "email": "x@y.com",
        "password": "securepass123",
        "confirm": "securepass123",
    })
    assert resp.status_code == 400


def test_register_invalid_email(client):
    resp = client.post("/auth/register", data={
        "username": "goodname",
        "email": "bademail",
        "password": "securepass123",
        "confirm": "securepass123",
    })
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post("/auth/register", data={
        "username": "goodname",
        "email": "x@y.com",
        "password": "short",
        "confirm": "short",
    })
    assert resp.status_code == 400


def test_register_password_mismatch(client):
    resp = client.post("/auth/register", data={
        "username": "goodname",
        "email": "x@y.com",
        "password": "securepass123",
        "confirm": "differentpass",
    })
    assert resp.status_code == 400


@patch("goldart.blueprints.auth.get_user_by_username", return_value={"id": 1})
def test_register_duplicate_username(mock_by_user, client):
    resp = client.post("/auth/register", data={
        "username": "taken",
        "email": "x@y.com",
        "password": "securepass123",
        "confirm": "securepass123",
    })
    assert resp.status_code == 400


# ── Login ─────────────────────────────────────────────────────────────────────

@patch("goldart.blueprints.auth.get_user_by_username")
def test_login_success(mock_get, client):
    mock_get.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": generate_password_hash("correctpass"),
    }
    resp = client.post("/auth/login", data={
        "username": "testuser",
        "password": "correctpass",
    }, follow_redirects=False)
    assert resp.status_code == 302


@patch("goldart.blueprints.auth.get_user_by_username", return_value=None)
def test_login_wrong_user(mock_get, client):
    resp = client.post("/auth/login", data={
        "username": "noone",
        "password": "whatever",
    })
    assert resp.status_code == 401


@patch("goldart.blueprints.auth.get_user_by_username")
def test_login_wrong_password(mock_get, client):
    mock_get.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": generate_password_hash("correctpass"),
    }
    resp = client.post("/auth/login", data={
        "username": "testuser",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

def test_logout_clears_session(auth_client):
    resp = auth_client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    # After logout, accessing protected route should redirect to login
    resp2 = auth_client.get("/", follow_redirects=False)
    assert resp2.status_code == 302
    assert "/auth/login" in resp2.headers["Location"]


# ── Protected routes ──────────────────────────────────────────────────────────

def test_dashboard_requires_login(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_trades_requires_login(client):
    resp = client.get("/trades/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_analysis_requires_login(client):
    resp = client.get("/analysis/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_health_is_public(client):
    resp = client.get("/health")
    assert resp.status_code == 200
