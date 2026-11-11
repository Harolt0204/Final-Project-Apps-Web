"""Status workflow, reviewer committee and review observations (Sprint 3)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.routes.theses import thesis_detail
from app.db import get_db
from app.models import User, UserRole
from app.schemas.theses import (
    ObservationCreate,
    ObservationOut,
    ObservationResponse,
    ReviewerAssign,
    StatusChange,
    ThesisDetail,
    WorkflowOut,
)
from app.services import review, workflow
from app.services.access import get_visible_thesis

router = APIRouter(prefix="/api/theses/{thesis_id}", tags=["Workflow and review"])


# -------------------------------------------------------------------------- workflow


@router.get("/workflow", response_model=WorkflowOut)
def get_workflow(
    thesis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> WorkflowOut:
    """Possible next statuses, who can apply them and what is still missing."""
    thesis = get_visible_thesis(db, user, thesis_id)
    return WorkflowOut(status=thesis.status, options=workflow.options(user, thesis))


@router.post("/status", response_model=ThesisDetail)
def change_status(
    thesis_id: int,
    data: StatusChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThesisDetail:
    """Apply a transition. 409 lists the prerequisites that are still missing."""
    get_visible_thesis(db, user, thesis_id)  # 404 for non-participants
    thesis = workflow.change_status(db, user, thesis_id, data.to_status, data.comment)
    return thesis_detail(db, thesis, user)


# ------------------------------------------------------------------------- committee


@router.put("/reviewers/{professor_id}", response_model=ThesisDetail)
def set_reviewer(
    thesis_id: int,
    professor_id: int,
    data: ReviewerAssign,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ThesisDetail:
    """Add a reviewer or change their role (President / Committee)."""
    thesis = review.set_reviewer(db, thesis_id, professor_id, data.role)
    return thesis_detail(db, thesis, user)


@router.delete("/reviewers/{professor_id}", response_model=ThesisDetail)
def remove_reviewer(
    thesis_id: int,
    professor_id: int,
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> ThesisDetail:
    return thesis_detail(db, review.remove_reviewer(db, thesis_id, professor_id), user)


@router.put("/approval", response_model=ThesisDetail)
def approve_manuscript(
    thesis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ThesisDetail:
    """A reviewer approves the manuscript (needs all of their observations resolved)."""
    thesis = get_visible_thesis(db, user, thesis_id)
    return thesis_detail(db, review.set_approval(db, user, thesis, approve=True), user)


@router.delete("/approval", response_model=ThesisDetail)
def withdraw_approval(
    thesis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ThesisDetail:
    thesis = get_visible_thesis(db, user, thesis_id)
    return thesis_detail(db, review.set_approval(db, user, thesis, approve=False), user)


# ---------------------------------------------------------------------- observations


@router.get("/observations", response_model=list[ObservationOut])
def list_observations(
    thesis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return get_visible_thesis(db, user, thesis_id).observations


@router.post("/observations", response_model=ObservationOut, status_code=status.HTTP_201_CREATED)
def add_observation(
    thesis_id: int,
    data: ObservationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    thesis = get_visible_thesis(db, user, thesis_id)
    observation = review.add_observation(db, user, thesis, data.text)
    db.refresh(observation)
    return observation


@router.post("/observations/{observation_id}/response", response_model=ObservationOut)
def respond(
    thesis_id: int,
    observation_id: int,
    data: ObservationResponse,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The student answers an open observation."""
    thesis = get_visible_thesis(db, user, thesis_id)
    return review.respond(db, user, thesis, observation_id, data.response)


@router.post("/observations/{observation_id}/resolve", response_model=ObservationOut)
def resolve(
    thesis_id: int,
    observation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The author accepts the student's response."""
    thesis = get_visible_thesis(db, user, thesis_id)
    return review.review_response(db, user, thesis, observation_id, accept=True)


@router.post("/observations/{observation_id}/reopen", response_model=ObservationOut)
def reopen(
    thesis_id: int,
    observation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The author rejects the student's response; the observation is open again."""
    thesis = get_visible_thesis(db, user, thesis_id)
    return review.review_response(db, user, thesis, observation_id, accept=False)
