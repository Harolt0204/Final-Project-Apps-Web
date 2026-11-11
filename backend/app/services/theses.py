"""Thesis registration and tutor assignment (FR-03, FR-04)."""

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AcademicPeriod,
    Professor,
    Student,
    Thesis,
    ThesisStatus,
    ThesisStatusHistory,
    TutorAssignment,
    TutorRole,
    User,
    UserRole,
)
from app.schemas.theses import ThesisCreate, ThesisUpdate

CLOSED_STATUSES = {ThesisStatus.DEFENDED, ThesisStatus.REJECTED}


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(code, message)


def _load_periods(db: Session, period_ids: list[int]) -> list[AcademicPeriod]:
    unique_ids = set(period_ids)
    periods = list(
        db.scalars(select(AcademicPeriod).where(AcademicPeriod.period_id.in_(unique_ids)))
    )
    if len(periods) != len(unique_ids):
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Academic period not found")
    return periods


def current_periods(db: Session, today: dt.date | None = None) -> list[AcademicPeriod]:
    today = today or dt.date.today()
    query = select(AcademicPeriod).where(
        AcademicPeriod.start_date <= today, AcademicPeriod.end_date >= today
    )
    return list(db.scalars(query))


def register_thesis(db: Session, user: User, data: ThesisCreate) -> Thesis:
    if user.role == UserRole.PROFESSOR:
        raise _error(status.HTTP_403_FORBIDDEN, "Professors cannot register theses")

    if user.role == UserRole.STUDENT:
        if data.student_id not in (None, user.student_id):
            raise _error(status.HTTP_403_FORBIDDEN, "Students can only register their own thesis")
        student_id = user.student_id
    else:
        if data.student_id is None:
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "student_id is required")
        student_id = data.student_id

    student = db.get(Student, student_id)
    if student is None:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Student not found")
    # Checked here for a clear message; UNIQUE(theses.student_id) is the real guarantee.
    if db.scalars(select(Thesis).where(Thesis.student_id == student_id)).first():
        raise _error(status.HTTP_409_CONFLICT, "This student already has a registered thesis")

    periods = _load_periods(db, data.period_ids) if data.period_ids else current_periods(db)
    thesis = Thesis(
        title=data.title,
        abstract=data.abstract,
        student=student,
        periods=periods,
        status=ThesisStatus.PROPOSED,
    )
    db.add(thesis)
    db.add(
        ThesisStatusHistory(
            thesis=thesis,
            from_status=None,
            to_status=ThesisStatus.PROPOSED,
            author=user,
            comment="Topic registered",
        )
    )
    db.commit()
    return thesis


def update_thesis(db: Session, user: User, thesis: Thesis, data: ThesisUpdate) -> Thesis:
    if user.role == UserRole.PROFESSOR:
        raise _error(status.HTTP_403_FORBIDDEN, "Professors cannot edit thesis data")
    if user.role == UserRole.STUDENT:
        if thesis.status != ThesisStatus.PROPOSED:
            raise _error(
                status.HTTP_409_CONFLICT, "The topic can only be edited while it is still proposed"
            )
        if data.period_ids is not None:
            raise _error(status.HTTP_403_FORBIDDEN, "Only administrators change academic periods")

    changes = data.model_dump(exclude_unset=True, exclude={"period_ids"})
    if "title" in changes and changes["title"] is None:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "title cannot be empty")
    for field, value in changes.items():
        setattr(thesis, field, value)
    if data.period_ids is not None:
        thesis.periods = _load_periods(db, data.period_ids)
    db.commit()
    return thesis


def _lock_thesis(db: Session, thesis_id: int) -> Thesis:
    """Lock the thesis row so concurrent assignments are applied one at a time."""
    thesis = db.scalars(
        select(Thesis).where(Thesis.thesis_id == thesis_id).with_for_update()
    ).first()
    if thesis is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Thesis not found")
    if thesis.status in CLOSED_STATUSES:
        raise _error(status.HTTP_409_CONFLICT, "The thesis is closed and cannot be modified")
    return thesis


def assign_tutor(db: Session, thesis_id: int, role: TutorRole, professor_id: int) -> Thesis:
    thesis = _lock_thesis(db, thesis_id)
    if db.get(Professor, professor_id) is None:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Professor not found")

    # I-4: the tutor of a thesis cannot also review it (conflict of interest).
    if any(r.professor_id == professor_id for r in thesis.reviewers):
        raise _error(
            status.HTTP_409_CONFLICT,
            "This professor is a reviewer of the thesis and cannot also tutor it",
        )

    by_role = {t.role: t for t in thesis.tutors}
    other = TutorRole.CO_TUTOR if role == TutorRole.TUTOR else TutorRole.TUTOR
    if other in by_role and by_role[other].professor_id == professor_id:
        raise _error(
            status.HTTP_409_CONFLICT,
            f"This professor is already the {other.value.lower()} of the thesis",
        )
    if role == TutorRole.CO_TUTOR and TutorRole.TUTOR not in by_role:
        raise _error(status.HTTP_409_CONFLICT, "Assign the main tutor before the co-tutor")

    if role in by_role:
        by_role[role].professor_id = professor_id  # replacement
    else:
        thesis.tutors.append(TutorAssignment(role=role, professor_id=professor_id))
    db.commit()
    return thesis


def remove_tutor(db: Session, thesis_id: int, role: TutorRole) -> Thesis:
    thesis = _lock_thesis(db, thesis_id)
    by_role = {t.role: t for t in thesis.tutors}
    if role not in by_role:
        raise _error(status.HTTP_404_NOT_FOUND, f"The thesis has no {role.value.lower()}")
    if role == TutorRole.TUTOR and TutorRole.CO_TUTOR in by_role:
        raise _error(
            status.HTTP_409_CONFLICT, "Remove the co-tutor first, or replace the main tutor instead"
        )
    thesis.tutors.remove(by_role[role])
    db.commit()
    return thesis
