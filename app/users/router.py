from datetime import datetime, timedelta, timezone
import hmac
import os
import secrets

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.users.models import User
from app.users.schemas import (
    AccessToken,
    ForgotPassword,
    PasswordReset,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)


router = APIRouter(prefix="/users", tags=["users"])
bearer_scheme = HTTPBearer()
password_hash = PasswordHash.recommended()
secret_key = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
token_lifetime = timedelta(minutes=30)
admin_reset_token = os.getenv("ADMIN_RESET_TOKEN")


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + token_lifetime
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        secret_key,
        algorithm="HS256",
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, database: Session = Depends(get_db)) -> User:
    user = User(
        username=payload.username,
        hashed_password=password_hash.hash(payload.password),
    )
    database.add(user)
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from error
    database.refresh(user)
    return user


@router.post("/login", response_model=AccessToken)
def login_user(payload: UserLogin, database: Session = Depends(get_db)) -> AccessToken:
    user = database.scalar(select(User).where(User.username == payload.username))
    if user is None or not password_hash.verify(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return AccessToken(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    database: Session = Depends(get_db),
) -> User:
    try:
        claims = jwt.decode(credentials.credentials, secret_key, algorithms=["HS256"])
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    user = database.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.put("/me", response_model=UserRead)
def update_current_user(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> User:
    current_user.username = payload.username
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from error
    database.refresh(current_user)
    return current_user


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: PasswordReset,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> None:
    if not password_hash.verify(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = password_hash.hash(payload.new_password)
    database.commit()


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPassword,
    database: Session = Depends(get_db),
) -> dict[str, str]:
    if admin_reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin password reset is not configured",
        )
    if not hmac.compare_digest(payload.admin_token, admin_reset_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin reset token",
        )

    user = database.scalar(select(User).where(User.username == payload.username))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.hashed_password = password_hash.hash(payload.new_password)
    database.commit()
    return {"detail": "Password reset successfully"}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> None:
    database.delete(current_user)
    database.commit()