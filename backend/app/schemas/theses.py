"""Request and response models for theses and their participants."""

import datetime as dt
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import ObservationStatus, ReviewerRole, ThesisStatus, TutorRole
from app.schemas.catalog import PeriodOut, SchoolOut
from app.schemas.defense import DefenseOut

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=255)]
Abstract = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PersonOut(ORMModel):
    full_name: str
    email: str


class StudentOut(PersonOut):
    student_id: int
    school: SchoolOut | None


class ProfessorOut(PersonOut):
    professor_id: int


class TutorOut(ORMModel):
    role: TutorRole
    professor: ProfessorOut


class ReviewerOut(ORMModel):
    role: ReviewerRole
    professor: ProfessorOut
    approved_at: dt.datetime | None
    grade: Decimal | None


class StatusChangeOut(ORMModel):
    from_status: ThesisStatus | None
    to_status: ThesisStatus
    changed_at: dt.datetime
    changed_by_name: str
    comment: str | None


class ThesisSummary(ORMModel):
    thesis_id: int
    title: str
    status: ThesisStatus
    student: StudentOut
    tutors: list[TutorOut]
    reviewers: list[ReviewerOut]
    # Roles of the logged-in user on this thesis (derived from assignments).
    my_roles: list[str]
    updated_at: dt.datetime


class ThesisDetail(ThesisSummary):
    abstract: str | None
    periods: list[PeriodOut]
    status_history: list[StatusChangeOut]
    defense: DefenseOut | None = None
    created_at: dt.datetime


# ------------------------------------------------------------------------- requests


class ThesisCreate(BaseModel):
    """Topic registration (FR-03). Students register their own thesis; administrators
    register it for a given student."""

    title: Title
    abstract: Abstract | None = None
    student_id: int | None = None
    # Empty: the thesis is linked to the period in course, if there is one.
    period_ids: list[int] = Field(default_factory=list, max_length=10)


class ThesisUpdate(BaseModel):
    title: Title | None = None
    abstract: Abstract | None = None
    period_ids: list[int] | None = Field(default=None, max_length=10)


class TutorAssign(BaseModel):
    professor_id: int


# ---------------------------------------------------------------- workflow (Sprint 3)

Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class StatusChange(BaseModel):
    to_status: ThesisStatus
    comment: Comment | None = None


class WorkflowOption(BaseModel):
    to_status: ThesisStatus
    label: str
    actors: list[str]
    blockers: list[str]
    comment_required: bool
    can_perform: bool


class WorkflowOut(BaseModel):
    status: ThesisStatus
    options: list[WorkflowOption]


class ReviewerAssign(BaseModel):
    role: ReviewerRole = ReviewerRole.COMMITTEE


class ObservationCreate(BaseModel):
    text: LongText


class ObservationResponse(BaseModel):
    response: LongText


class ObservationOut(ORMModel):
    observation_id: int
    professor_id: int
    author_name: str
    text: str
    status: ObservationStatus
    response: str | None
    responded_at: dt.datetime | None
    resolved_at: dt.datetime | None
    created_at: dt.datetime
