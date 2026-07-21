def test_register_happy_path(client):
    response = client.post(
        "/auth/register",
        params={"email": "new@example.com", "password": "Password123"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert "id" in data
    assert "hashed_password" not in data


def test_register_duplicate_user_rejected(client):
    client.post(
        "/auth/register",
        params={"email": "dupe@example.com", "password": "Password123"},
    )

    response = client.post(
        "/auth/register",
        params={"email": "dupe@example.com", "password": "Password123"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_missing_password_rejected(client):
    response = client.post(
        "/auth/register",
        params={"email": "missing@example.com"},
    )

    assert response.status_code == 422
