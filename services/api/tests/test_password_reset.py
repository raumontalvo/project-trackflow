from datetime import datetime, timedelta, timezone

from services.api.routes.auth_routes import hash_reset_token
from services.api.database import users_table


def test_forgot_password_existing_user_returns_safe_message(client, test_user):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "user@example.com"},
    )

    assert response.status_code == 200
    assert "receive a password reset link" in response.json()["message"]


def test_forgot_password_unknown_user_returns_safe_message(client):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "unknown@example.com"},
    )

    assert response.status_code == 200
    assert "receive a password reset link" in response.json()["message"]


def test_reset_password_invalid_token_rejected(client):
    response = client.post(
        "/auth/reset-password",
        json={
            "token": "this-is-a-long-invalid-token",
            "new_password": "NewPassword123",
        },
    )

    assert response.status_code == 400


def test_reset_password_expired_token_rejected(client, test_user):
    raw_token = "this-is-a-valid-length-token"
    user = users_table.get(doc_id=test_user["id"])

    users_table.update(
        {
            "reset_token_hash": hash_reset_token(raw_token),
            "reset_token_expires_at": (
                datetime.now(timezone.utc) - timedelta(minutes=1)
            ).isoformat(),
            "reset_token_used": False,
        },
        doc_ids=[user.doc_id],
    )

    response = client.post(
        "/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword123"},
    )

    assert response.status_code == 400