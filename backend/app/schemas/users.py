"""Request/response models for authentication and user accounts."""

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import UserRole

# 12 characters minimum (OWASP ASVS); 72 is bcrypt's limit.
PASSWORD_MIN, PASSWORD_MAX = 12, 72


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    role: UserRole
    display_name: str
    student_id: int | None
    professor_id: int | None
    is_active: bool
    last_login_at: dt.datetime | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    role: UserRole
    student_id: int | None = None
    professor_id: int | None = None

    @model_validator(mode="after")
    def check_link(self) -> "UserCreate":
        # Mirrors ck_users_link in the database, to answer 422 instead of a DB error.
        expected = {
            UserRole.STUDENT: (True, False),
            UserRole.PROFESSOR: (False, True),
            UserRole.ADMIN: (False, False),
        }[self.role]
        if (self.student_id is not None, self.professor_id is not None) != expected:
            raise ValueError(
                "A student account needs student_id only, a professor account needs "
                "professor_id only, and an admin account needs neither"
            )
        return self


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class UserUpdate(BaseModel):
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
