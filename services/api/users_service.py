from datetime import datetime, timezone

from tinydb import Query

from services.api.auth import hash_password
from services.api.database import users_table

UserQuery = Query()


def serialize_user(user: dict, user_id: int) -> dict:
    safe_user = user.copy()
    safe_user["id"] = user_id
    safe_user.pop("hashed_password", None)
    return safe_user


def create_user(email: str, password: str) -> dict:
    existing_user = users_table.get(UserQuery.email == email)
    if existing_user:
        raise ValueError("Email already registered")

    user_data = {
        "name": "",
        "email": email,
        "hashed_password": hash_password(password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    user_id = users_table.insert(user_data)
    return serialize_user(user_data, user_id)


def get_user_by_id(user_id: int) -> dict | None:
    user = users_table.get(doc_id=user_id)
    if not user:
        return None
    return serialize_user(user, user_id)


def get_user_by_email(email: str) -> dict | None:
    user = users_table.get(UserQuery.email == email)
    if not user:
        return None
    return serialize_user(user, user.doc_id)


def get_user_with_password_by_email(email: str) -> dict | None:
    user = users_table.get(UserQuery.email == email)
    if not user:
        return None

    result = user.copy()
    result["id"] = user.doc_id
    return result


def list_users() -> list[dict]:
    return [serialize_user(user, user.doc_id) for user in users_table.all()]


def update_user(user_id: int, data: dict) -> dict | None:
    user = users_table.get(doc_id=user_id)
    if not user:
        return None

    update_data = {}

    if "name" in data and data["name"] is not None:
        update_data["name"] = data["name"]

    if "email" in data and data["email"] is not None:
        update_data["email"] = data["email"]

    if "password" in data and data["password"] is not None:
        update_data["hashed_password"] = hash_password(data["password"])

    if "is_active" in data and data["is_active"] is not None:
        update_data["is_active"] = data["is_active"]

    users_table.update(update_data, doc_ids=[user_id])
    updated_user = users_table.get(doc_id=user_id)
    return serialize_user(updated_user, user_id)


def delete_user(user_id: int) -> bool:
    removed = users_table.remove(doc_ids=[user_id])
    return len(removed) > 0