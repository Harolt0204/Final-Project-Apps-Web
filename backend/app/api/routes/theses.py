"""Theses, filtered by what the logged-in user is allowed to see."""

from enum import StrEnum

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db import get_db
from app.models import Thesis, TutorRole, User, UserRole
from app.schemas.defense import defense_out
from app.schemas.theses import (
    ThesisCreate,
    ThesisDetail,
    ThesisSummary,
    ThesisUpdate,
    TutorAssign,
)
from app.services import compliance
from app.services import theses as service
from app.services.access import get_visible_thesis, roles_on_thesis, visible_theses_query

router = APIRouter(prefix="/api/theses", tags=["Theses"])


class TutorSlot(StrEnum):
    """URL form of the tutor roles."""

    TUTOR = "tutor"
    CO_TUTOR = "co-tutor"

    @property
    def role(self) -> TutorRole:
        return TutorRole.TUTOR if self is TutorSlot.TUTOR else TutorRole.CO_TUTOR


def _common_fields(thesis: Thesis, user: User) -> dict:
    return {
        "thesis_id": thesis.thesis_id,
        "title": thesis.title,
        "status": thesis.status,
        "student": thesis.student,
        "tutors": thesis.tutors,
        "reviewers": thesis.reviewers,
        "my_roles": roles_on_thesis(user, thesis),
        "updated_at": thesis.updated_at,
    }


def _hide_jury_grades(result, user: User):
    """Students see the final defense grade, not each jury member's grade."""
    if user.role == UserRole.STUDENT:
        for reviewer in result.reviewers:
            reviewer.grade = None
    return result


def thesis_detail(db: Session, thesis: Thesis, user: User) -> ThesisDetail:
    db.refresh(thesis)  # reload columns and relationships changed by the service
    defense = (
        defense_out(thesis.defense, compliance.min_passing_grade(db)) if thesis.defense else None
    )
    detail = ThesisDetail.model_validate(
        {
            **_common_fields(thesis, user),
            "abstract": thesis.abstract,
            "periods": thesis.periods,
            "status_history": thesis.status_history,
            "defense": defense,
            "created_at": thesis.created_at,
        }
    )
    return _hide_jury_grades(detail, user)


@router.get("", response_model=list[ThesisSummary])
def list_theses(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ThesisSummary]:
    """Admins see every thesis; professors, those they tutor or review; students, their own."""
    theses = db.scalars(visible_theses_query(user)).all()
    return [
        _hide_jury_grades(ThesisSummary.model_validate(_common_fields(t, user)), user)
        for t in theses
    ]


@router.post("", response_model=ThesisDetail, status_code=status.HTTP_201_CREATED)
def register_thesis(
    data: ThesisCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ThesisDetail:
    """Register a thesis topic. It starts as PROPOSED and the change is recorded in the
    status history."""
    return thesis_detail(db, service.register_thesis(db, user, data), user)


@router.get("/{thesis_id}", response_model=ThesisDetail)
def get_thesis(
    thesis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ThesisDetail:
    """404 also when the thesis exists but the user takes no part in it."""
    return thesis_detail(db, get_visible_thesis(db, user, thesis_id), user)


@router.patch("/{thesis_id}", response_model=ThesisDetail)
def update_thesis(
    thesis_id: int,
    data: ThesisUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThesisDetail:
    """Students may edit their own topic while it is PROPOSED; admins at any time."""
    thesis = get_visible_thesis(db, user, thesis_id)
    return thesis_detail(db, service.update_thesis(db, user, thesis, data), user)


@router.put("/{thesis_id}/tutors/{slot}", response_model=ThesisDetail)
def assign_tutor(
    thesis_id: int,
    slot: TutorSlot,
    data: TutorAssign,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ThesisDetail:
    """Assign or replace the tutor or co-tutor (DEC-03). A professor cannot be tutor and
    co-tutor, nor tutor and reviewer, of the same thesis."""
    return thesis_detail(
        db, service.assign_tutor(db, thesis_id, slot.role, data.professor_id), user
    )


@router.delete("/{thesis_id}/tutors/{slot}", response_model=ThesisDetail)
def remove_tutor(
    thesis_id: int,
    slot: TutorSlot,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ThesisDetail:
    return thesis_detail(db, service.remove_tutor(db, thesis_id, slot.role), user)
