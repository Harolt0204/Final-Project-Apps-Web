"""Shared FastAPI dependencies: database session, current user and role checks."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        issued_at = int(payload["iat"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise CREDENTIALS_ERROR from None

    user = db.get(User, user_id)
    # A deactivated account loses access immediately, even with a valid token.
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR
    # Tokens issued before the last password change are revoked.
    if user.password_changed_at and issued_at < int(user.password_changed_at.timestamp()):
        raise CREDENTIALS_ERROR
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """Global-role check. Per-thesis permissions are checked in app.services.access."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enough permissions")
        return user

    return checker
