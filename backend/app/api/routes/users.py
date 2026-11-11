"""User account administration (administrators only)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.security import hash_password, now_local
from app.db import get_db
from app.models import Professor, Student, User, UserRole
from app.schemas.users import UserCreate, UserOut, UserUpdate

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.role, User.email)))


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db)) -> User:
    if data.student_id is not None and db.get(Student, data.student_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Student not found")
    if data.professor_id is not None and db.get(Professor, data.professor_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Professor not found")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        role=data.role,
        student_id=data.student_id,
        professor_id=data.professor_id,
    )
    db.add(user)
    db.commit()  # duplicates raise IntegrityError -> 409 (see app.main)
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if data.is_active is False and user.user_id == current.user_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot deactivate your own account")

    if data.is_active is not None:
        user.is_active = data.is_active
    if data.password is not None:
        # An admin reset also closes the user's open sessions.
        user.password_hash = hash_password(data.password)
        user.password_changed_at = now_local()
    db.commit()
    db.refresh(user)
    return user
