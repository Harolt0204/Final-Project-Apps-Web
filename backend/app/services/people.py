"""Business rules shared by students and professors.

The database already guarantees unique e-mails, user names and national ids; checking first lets the
API answer 409 with a clear message instead of a generic integrity error.
"""

from fastapi import HTTPException, status
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Professor,
    ReviewerAssignment,
    School,
    Student,
    TutorAssignment,
    User,
    UserRole,
)
from app.schemas.people import PersonCreate, PersonUpdate
from app.schemas.users import username_from_email

Person = Student | Professor

REQUIRED_FIELDS = ("first_name", "last_name", "email")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def _check_school(db: Session, school_id: int | None) -> None:
    if school_id is not None and db.get(School, school_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "School not found")


def _check_unique(
    db: Session,
    model: type[Person],
    person: Person | None,
    email: str | None,
    national_id: str | None,
) -> None:
    pk = model.__mapper__.primary_key[0]
    own_id = getattr(person, pk.key) if person else None

    if email is not None:
        same_email = select(model).where(func.lower(model.email) == email.lower())
        if own_id is not None:
            same_email = same_email.where(pk != own_id)
        if db.scalars(same_email).first():
            raise _conflict(f"Another {model.__name__.lower()} already uses this e-mail")

        # The linked login account takes its user name from the e-mail (name.lastname),
        # so that user name must be free among the other accounts too.
        users = select(User).where(func.lower(User.username) == username_from_email(email))
        if person is not None and person.account is not None:
            users = users.where(User.user_id != person.account.user_id)
        if db.scalars(users).first():
            raise _conflict("A user account already uses this user name")

    if national_id is not None:
        same_id = select(model).where(model.national_id == national_id)
        if own_id is not None:
            same_id = same_id.where(pk != own_id)
        if db.scalars(same_id).first():
            raise _conflict(f"Another {model.__name__.lower()} already uses this national id")


def create_person(db: Session, model: type[Person], data: PersonCreate) -> Person:
    _check_school(db, data.school_id)
    email = str(data.email).lower()
    _check_unique(db, model, None, email, data.national_id)

    fields = data.model_dump(exclude={"account_password", "email"})
    person = model(**fields, email=email)
    db.add(person)

    if data.account_password is not None:
        role = UserRole.STUDENT if model is Student else UserRole.PROFESSOR
        link = {"student": person} if model is Student else {"professor": person}
        db.add(
            User(
                username=username_from_email(email),
                password_hash=hash_password(data.account_password),
                role=role,
                **link,
            )
        )

    db.commit()
    db.refresh(person)
    return person


def update_person(db: Session, person: Person, data: PersonUpdate) -> Person:
    changes = data.model_dump(exclude_unset=True)
    for field in REQUIRED_FIELDS:
        if field in changes and changes[field] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field} cannot be empty")

    if "email" in changes:
        changes["email"] = str(changes["email"]).lower()
    if "school_id" in changes:
        _check_school(db, changes["school_id"])
    _check_unique(db, type(person), person, changes.get("email"), changes.get("national_id"))

    for field, value in changes.items():
        setattr(person, field, value)
    # Keep the login user name in sync with the person's e-mail (documentation.md §8.2.1).
    if "email" in changes and person.account is not None:
        person.account.username = username_from_email(changes["email"])

    db.commit()
    db.refresh(person)
    return person


def delete_person(db: Session, person: Person) -> None:
    """Only records created by mistake can be deleted: academic history is never erased."""
    if person.account is not None:
        raise _conflict("This person has a user account. Disable the account instead.")
    if isinstance(person, Student) and person.thesis is not None:
        raise _conflict("This student has a registered thesis and cannot be deleted")
    if isinstance(person, Professor):
        pid = person.professor_id
        assigned = db.scalar(
            select(
                exists().where(TutorAssignment.professor_id == pid)
                | exists().where(ReviewerAssignment.professor_id == pid)
            )
        )
        if assigned:
            raise _conflict("This professor has thesis assignments and cannot be deleted")
    db.delete(person)
    db.commit()
