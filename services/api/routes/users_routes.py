from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException, status

from services.api.auth import get_current_user
from services.api.users_service import (
    delete_user,
    get_user_by_id,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6)
    is_active: bool | None = None


def require_owner(user_id: int, current_user: dict):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/")
def read_users(current_user: dict = Depends(get_current_user)):
    return list_users()


@router.get("/{user_id}")
def read_user(user_id: int, current_user: dict = Depends(get_current_user)):
    require_owner(user_id, current_user)

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}")
@router.patch("/{user_id}")
def patch_user(
    user_id: int,
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
):
    require_owner(user_id, current_user)

    user = update_user(user_id, payload.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(user_id: int, current_user: dict = Depends(get_current_user)):
    require_owner(user_id, current_user)

    deleted = delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return None