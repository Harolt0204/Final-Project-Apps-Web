"""Login, current user and password change."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.ratelimit import LoginLimiter
from app.core.security import create_access_token, hash_password, now_local, verify_password
from app.db import get_db
from app.models import User
from app.schemas.users import PasswordChange, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_settings = get_settings()
limiter = LoginLimiter(_settings.login_max_failures, _settings.login_window_seconds)

INVALID_LOGIN = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "Incorrect user name or password",
    headers={"WWW-Authenticate": "Bearer"},
)


def _client_ip(request: Request) -> str:
    # Behind a reverse proxy, uvicorn --proxy-headers sets this from X-Forwarded-For.
    return request.client.host if request.client else "unknown"


def _token_for(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.user_id, user.role.value),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenOut:
    """Exchange user name (name.lastname, OAuth2 form field `username`) and password for
    a JWT. Repeated failures for the same user name and IP are throttled with HTTP 429."""
    ip, username = _client_ip(request), form.username.strip().lower()
    wait = limiter.retry_after(ip, username)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Try again later.",
            headers={"Retry-After": str(wait)},
        )

    user = db.scalars(select(User).where(func.lower(User.username) == username)).first()
    # Same message for unknown user name, wrong password or disabled account, so the
    # endpoint does not reveal which accounts exist.
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        limiter.failed(ip, username)
        raise INVALID_LOGIN

    limiter.succeeded(ip, username)
    user.last_login_at = now_local()
    db.commit()
    return _token_for(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/password", response_model=TokenOut)
def change_password(
    data: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenOut:
    """Change your own password. Other sessions are closed; this one gets a new token."""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The current password is incorrect")
    if data.new_password == data.current_password:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The new password must be different"
        )
    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = now_local()
    db.commit()
    return _token_for(user)
