"""Per-thesis authorization (DEC-07).

Global roles say what kind of user someone is. What a professor may do on a given
thesis comes from the assignment tables: the same professor can be the tutor of one
thesis and a reviewer of another. A user who takes no part in a thesis cannot see it:
the API answers 404, so it does not even reveal that the thesis exists
(OWASP API1:2023, Broken Object Level Authorization).
"""

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ReviewerAssignment,
    Thesis,
    TutorAssignment,
    User,
    UserRole,
)

THESIS_LOAD_OPTIONS = (
    selectinload(Thesis.student),
    selectinload(Thesis.tutors).selectinload(TutorAssignment.professor),
    selectinload(Thesis.reviewers).selectinload(ReviewerAssignment.professor),
)


def visibility_clause(user: User) -> ColumnElement[bool] | None:
    """Condition on Thesis.thesis_id / Thesis.student_id for what the user may see;
    None means everything (administrators)."""
    if user.role == UserRole.ADMIN:
        return None
    if user.role == UserRole.STUDENT:
        return Thesis.student_id == user.student_id

    # Professor: only theses where they hold a tutor or reviewer assignment.
    as_tutor = select(TutorAssignment.thesis_id).where(
        TutorAssignment.professor_id == user.professor_id
    )
    as_reviewer = select(ReviewerAssignment.thesis_id).where(
        ReviewerAssignment.professor_id == user.professor_id
    )
    return or_(Thesis.thesis_id.in_(as_tutor), Thesis.thesis_id.in_(as_reviewer))


def visible_theses_query(user: User) -> Select[tuple[Thesis]]:
    query = select(Thesis).options(*THESIS_LOAD_OPTIONS).order_by(Thesis.thesis_id)
    clause = visibility_clause(user)
    return query if clause is None else query.where(clause)


def get_visible_thesis(db: Session, user: User, thesis_id: int) -> Thesis:
    thesis = db.scalars(visible_theses_query(user).where(Thesis.thesis_id == thesis_id)).first()
    if thesis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thesis not found")
    return thesis


def roles_on_thesis(user: User, thesis: Thesis) -> list[str]:
    """The user's roles on this specific thesis, e.g. ['Tutor'] or ['President']."""
    if user.role == UserRole.ADMIN:
        return ["Administrator"]
    if user.role == UserRole.STUDENT:
        return ["Student"] if thesis.student_id == user.student_id else []

    roles = [t.role.value for t in thesis.tutors if t.professor_id == user.professor_id]
    roles += [r.role.value for r in thesis.reviewers if r.professor_id == user.professor_id]
    return roles
