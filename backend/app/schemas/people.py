"""Students and professors (FR-01, FR-02)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.schemas.catalog import SchoolOut
from app.schemas.users import PASSWORD_MAX, PASSWORD_MIN

PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
# Ecuadorian cédula (10 digits) or a passport number for foreign students/professors.
NationalId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9-]{5,20}$")
]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9 +()-]{6,20}$")]
Institution = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class PersonCreate(BaseModel):
    national_id: NationalId | None = None
    first_name: PersonName
    last_name: PersonName
    email: EmailStr
    school_id: int | None = None
    institution: Institution | None = "Yachay Tech"
    # When set, a login account is created at the same time; its user name is the
    # local part of the e-mail (name.lastname).
    account_password: str | None = Field(
        default=None, min_length=PASSWORD_MIN, max_length=PASSWORD_MAX
    )


class PersonUpdate(BaseModel):
    national_id: NationalId | None = None
    first_name: PersonName | None = None
    last_name: PersonName | None = None
    email: EmailStr | None = None
    school_id: int | None = None
    institution: Institution | None = None


class StudentCreate(PersonCreate):
    phone: Phone | None = None


class StudentUpdate(PersonUpdate):
    phone: Phone | None = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    national_id: str | None
    first_name: str
    last_name: str
    full_name: str
    email: str
    institution: str | None
    school: SchoolOut | None
    has_account: bool


class StudentOut(PersonOut):
    student_id: int
    phone: str | None
    has_thesis: bool


class ProfessorOut(PersonOut):
    professor_id: int
