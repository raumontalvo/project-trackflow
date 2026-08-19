from datetime import datetime, timedelta, timezone

from jose import jwt

from services.api.auth import ALGORITHM, SECRET_KEY, create_access_token


def test_me_happy_path_with_valid_token(client, test_user):
    token = create_access_token({"sub": str(test_user["id"])})

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert "hashed_password" not in response.json()


def test_me_malformed_token_rejected(client):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_me_expired_token_rejected(client, test_user):
    expired_token = jwt.encode(
        {
            "sub": str(test_user["id"]),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
