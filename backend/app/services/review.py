"""Reviewer committee (FR-05, DEC-04/05) and the review observation cycle (FR-08).

Committee rules:
- at most 3 reviewers (service + MySQL trigger) and at most one president (unique index);
- a tutor or co-tutor cannot review the same thesis (I-4);
- the committee can change from TOPIC_APPROVED up to IN_REVIEW;
- a reviewer who already wrote observations cannot be removed (the history would be lost).

Observation cycle, only while the thesis is IN_REVIEW:
    reviewer opens ─► OPEN ─► student responds ─► ADDRESSED ─► reviewer resolves ─► RESOLVED
                       ▲                              │
                       └──────── reviewer reopens ────┘
A reviewer approves the manuscript only when all of their observations are resolved.
"""

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ObservationStatus,
    Professor,
    ReviewerAssignment,
    ReviewerRole,
    ReviewObservation,
    Thesis,
    ThesisStatus,
    User,
    UserRole,
)

COMMITTEE_EDITABLE = {
    ThesisStatus.TOPIC_APPROVED,
    ThesisStatus.THESIS_I,
    ThesisStatus.THESIS_II,
    ThesisStatus.IN_REVIEW,
}
MAX_REVIEWERS = 3


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(code, message)


def _lock(db: Session, thesis_id: int) -> Thesis:
    thesis = db.scalars(
        select(Thesis).where(Thesis.thesis_id == thesis_id).with_for_update()
    ).first()
    if thesis is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Thesis not found")
    return thesis


def _now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


# ------------------------------------------------------------------------- committee


def set_reviewer(db: Session, thesis_id: int, professor_id: int, role: ReviewerRole) -> Thesis:
    """Add a reviewer, or change the role of one already on the committee."""
    thesis = _lock(db, thesis_id)
    if thesis.status not in COMMITTEE_EDITABLE:
        raise _error(
            status.HTTP_409_CONFLICT,
            "The committee can only change between topic approval and the committee review",
        )
    if db.get(Professor, professor_id) is None:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Professor not found")
    if any(t.professor_id == professor_id for t in thesis.tutors):
        raise _error(
            status.HTTP_409_CONFLICT,
            "This professor tutors the thesis and cannot also review it",
        )

    current = next((r for r in thesis.reviewers if r.professor_id == professor_id), None)
    if role == ReviewerRole.PRESIDENT and any(
        r.role == ReviewerRole.PRESIDENT and r.professor_id != professor_id
        for r in thesis.reviewers
    ):
        raise _error(
            status.HTTP_409_CONFLICT,
            "The committee already has a president. Change them to committee member first.",
        )

    if current is not None:
        current.role = role
    else:
        if len(thesis.reviewers) >= MAX_REVIEWERS:
            raise _error(status.HTTP_409_CONFLICT, "The committee already has 3 reviewers")
        db.add(ReviewerAssignment(thesis_id=thesis_id, professor_id=professor_id, role=role))
    db.commit()
    return thesis


def remove_reviewer(db: Session, thesis_id: int, professor_id: int) -> Thesis:
    thesis = _lock(db, thesis_id)
    if thesis.status not in COMMITTEE_EDITABLE:
        raise _error(status.HTTP_409_CONFLICT, "The committee can no longer change")
    current = next((r for r in thesis.reviewers if r.professor_id == professor_id), None)
    if current is None:
        raise _error(status.HTTP_404_NOT_FOUND, "This professor is not a reviewer of the thesis")
    if any(o.professor_id == professor_id for o in thesis.observations):
        raise _error(
            status.HTTP_409_CONFLICT,
            "This reviewer has written observations and cannot be removed",
        )
    db.delete(current)
    db.commit()
    return thesis


# ---------------------------------------------------------------------- observations


def _reviewer_of(thesis: Thesis, user: User) -> ReviewerAssignment:
    if user.role == UserRole.PROFESSOR:
        for r in thesis.reviewers:
            if r.professor_id == user.professor_id:
                return r
    raise _error(status.HTTP_403_FORBIDDEN, "Only reviewers of this thesis can do this")


def _require_review(thesis: Thesis) -> None:
    if thesis.status != ThesisStatus.IN_REVIEW:
        raise _error(status.HTTP_409_CONFLICT, "The thesis is not under committee review")


def _observation(thesis: Thesis, observation_id: int) -> ReviewObservation:
    for o in thesis.observations:
        if o.observation_id == observation_id:
            return o
    raise _error(status.HTTP_404_NOT_FOUND, "Observation not found")


def add_observation(db: Session, user: User, thesis: Thesis, text: str) -> ReviewObservation:
    _require_review(thesis)
    reviewer = _reviewer_of(thesis, user)
    observation = ReviewObservation(
        thesis_id=thesis.thesis_id, professor_id=reviewer.professor_id, text=text
    )
    db.add(observation)
    reviewer.approved_at = None  # a new observation withdraws this reviewer's approval
    db.commit()
    return observation


def respond(
    db: Session, user: User, thesis: Thesis, observation_id: int, response: str
) -> ReviewObservation:
    _require_review(thesis)
    if user.role != UserRole.STUDENT or thesis.student_id != user.student_id:
        raise _error(status.HTTP_403_FORBIDDEN, "Only the student of this thesis can respond")
    observation = _observation(thesis, observation_id)
    if observation.status != ObservationStatus.OPEN:
        raise _error(status.HTTP_409_CONFLICT, "Only open observations can be answered")
    observation.response = response
    observation.responded_at = _now()
    observation.status = ObservationStatus.ADDRESSED
    db.commit()
    return observation


def review_response(
    db: Session, user: User, thesis: Thesis, observation_id: int, accept: bool
) -> ReviewObservation:
    """The author accepts the response (RESOLVED) or reopens the observation (OPEN)."""
    _require_review(thesis)
    reviewer = _reviewer_of(thesis, user)
    observation = _observation(thesis, observation_id)
    if observation.professor_id != reviewer.professor_id:
        raise _error(status.HTTP_403_FORBIDDEN, "Only the author can resolve this observation")
    if observation.status != ObservationStatus.ADDRESSED:
        raise _error(status.HTTP_409_CONFLICT, "The student has not responded yet")
    if accept:
        observation.status = ObservationStatus.RESOLVED
        observation.resolved_at = _now()
    else:
        observation.status = ObservationStatus.OPEN
    db.commit()
    return observation


def set_approval(db: Session, user: User, thesis: Thesis, approve: bool) -> Thesis:
    _require_review(thesis)
    reviewer = _reviewer_of(thesis, user)
    if approve:
        pending = [
            o
            for o in thesis.observations
            if o.professor_id == reviewer.professor_id and o.status != ObservationStatus.RESOLVED
        ]
        if pending:
            raise _error(
                status.HTTP_409_CONFLICT,
                f"Resolve your {len(pending)} pending observation(s) before approving",
            )
        reviewer.approved_at = _now()
    else:
        reviewer.approved_at = None
    db.commit()
    return thesis
