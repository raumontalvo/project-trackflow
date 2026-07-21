import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import resend
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from tinydb import Query

from services.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services.api.database import users_table
from services.api.users_service import create_user, get_user_with_password_by_email

router = APIRouter(prefix="/auth", tags=["auth"])
UserQuery = Query()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "30"))
RESEND_API_KEY = os.getenv("RESEND_API_KEY")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_reset_email(email: str, reset_url: str) -> None:
    if not RESEND_API_KEY:
        print(f"[DEV] Password reset link for {email}: {reset_url}")
        return

    resend.api_key = RESEND_API_KEY
    resend.Emails.send(
        {
            "from": "onboarding@resend.dev",
            "to": [email],
            "subject": "Reset your TrackFlow password",
            "text": (
                "You requested a password reset for TrackFlow.\n\n"
                f"Reset your password here: {reset_url}\n\n"
                "This link expires soon. If you did not request this, ignore this email."
            ),
        }
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(email: str, password: str):
    try:
        return create_user(email=email, password=password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_with_password_by_email(form_data.username)

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_uuid = user.get("uuid")

    if not user_uuid:
        user_uuid = str(uuid4())
        users_table.update(
            {"uuid": user_uuid},
            doc_ids=[user["id"]],
        )

    token = create_access_token({"sub": str(user["id"])})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_uuid": user_uuid,
    }


@router.get("/me")
def read_me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    user = users_table.get(UserQuery.email == payload.email)

    response = {
        "message": "If that address is in our system, you will receive a password reset link."
    }

    if not user:
        return response

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=RESET_TOKEN_EXPIRE_MINUTES
    )

    users_table.update(
        {
            "reset_token_hash": token_hash,
            "reset_token_expires_at": expires_at.isoformat(),
            "reset_token_used": False,
        },
        doc_ids=[user.doc_id],
    )

    reset_url = f"{FRONTEND_URL}/reset-password?token={raw_token}"
    send_reset_email(payload.email, reset_url)

    return response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    token_hash = hash_reset_token(payload.token)
    user = users_table.get(UserQuery.reset_token_hash == token_hash)

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if user.get("reset_token_used"):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at_raw = user.get("reset_token_expires_at")

    if not expires_at_raw:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at = datetime.fromisoformat(expires_at_raw)

    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    users_table.update(
        {
            "hashed_password": hash_password(payload.new_password),
            "reset_token_hash": None,
            "reset_token_expires_at": None,
            "reset_token_used": True,
        },
        doc_ids=[user.doc_id],
    )

    return {"message": "Password reset successful"}