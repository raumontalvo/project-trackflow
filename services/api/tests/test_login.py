def test_login_happy_path_returns_token(client, test_user):
    response = client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": "Password123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


def test_login_wrong_password_rejected(client, test_user):
    response = client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": "WrongPassword"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_unknown_user_rejected(client):
    response = client.post(
        "/auth/login",
        data={"username": "nobody@example.com", "password": "Password123"},
    )

    assert response.status_code == 401
