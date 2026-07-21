import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

from fastapi.testclient import TestClient
from services.api.main import app
from services.api.database import users_table


@pytest.fixture(autouse=True)
def clear_users():
    users_table.truncate()
    yield
    users_table.truncate()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user(client):
    response = client.post(
        "/auth/register",
        params={"email": "user@example.com", "password": "Password123"},
    )
    assert response.status_code == 201
    return response.json()
