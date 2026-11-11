"""Students and professors (administrators only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.db import get_db
from app.models import Professor, Student, UserRole
from app.schemas.people import (
    PersonCreate,
    PersonUpdate,
    ProfessorOut,
    StudentCreate,
    StudentOut,
    StudentUpdate,
)
from app.services.people import create_person, delete_person, update_person

admin_only = [Depends(require_roles(UserRole.ADMIN))]
students = APIRouter(prefix="/api/students", tags=["Students"], dependencies=admin_only)
professors = APIRouter(prefix="/api/professors", tags=["Professors"], dependencies=admin_only)

Search = Annotated[str | None, Query(max_length=100, description="Name, e-mail or national id")]


def _search(model, q: str | None):
    query = select(model).order_by(model.last_name, model.first_name)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(
            or_(
                func.lower(model.first_name + " " + model.last_name).like(like),
                func.lower(model.email).like(like),
                model.national_id.like(like),
            )
        )
    return query


def _get_or_404(db: Session, model, pk: int):
    person = db.get(model, pk)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return person


# ---------------------------------------------------------------------------- students


@students.get("", response_model=list[StudentOut])
def list_students(q: Search = None, db: Session = Depends(get_db)) -> list[Student]:
    query = _search(Student, q).options(
        selectinload(Student.school), selectinload(Student.account), selectinload(Student.thesis)
    )
    return list(db.scalars(query))


@students.post("", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(data: StudentCreate, db: Session = Depends(get_db)) -> Student:
    return create_person(db, Student, data)


@students.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)) -> Student:
    return _get_or_404(db, Student, student_id)


@students.patch("/{student_id}", response_model=StudentOut)
def update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db)) -> Student:
    return update_person(db, _get_or_404(db, Student, student_id), data)


@students.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_student(student_id: int, db: Session = Depends(get_db)) -> Response:
    delete_person(db, _get_or_404(db, Student, student_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------------------- professors


@professors.get("", response_model=list[ProfessorOut])
def list_professors(q: Search = None, db: Session = Depends(get_db)) -> list[Professor]:
    query = _search(Professor, q).options(
        selectinload(Professor.school), selectinload(Professor.account)
    )
    return list(db.scalars(query))


@professors.post("", response_model=ProfessorOut, status_code=status.HTTP_201_CREATED)
def create_professor(data: PersonCreate, db: Session = Depends(get_db)) -> Professor:
    return create_person(db, Professor, data)


@professors.get("/{professor_id}", response_model=ProfessorOut)
def get_professor(professor_id: int, db: Session = Depends(get_db)) -> Professor:
    return _get_or_404(db, Professor, professor_id)


@professors.patch("/{professor_id}", response_model=ProfessorOut)
def update_professor(
    professor_id: int, data: PersonUpdate, db: Session = Depends(get_db)
) -> Professor:
    return update_person(db, _get_or_404(db, Professor, professor_id), data)


@professors.delete("/{professor_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_professor(professor_id: int, db: Session = Depends(get_db)) -> Response:
    delete_person(db, _get_or_404(db, Professor, professor_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
