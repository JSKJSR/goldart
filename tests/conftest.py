import pytest
from unittest.mock import patch
from goldart import create_app


@pytest.fixture
def app():
    with patch("goldart.database.models.init_db"):
        app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """A test client with a logged-in user session."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "testuser"
    return client
