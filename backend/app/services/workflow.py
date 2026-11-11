"""Thesis state machine (objective 3 of the proposal, DEC-17).

Each allowed transition says WHO may perform it and WHICH prerequisites must hold.
A thesis advances only when its prerequisites are met; every change is written to
thesis_status_history in the same transaction (DEC-08).

    PROPOSED ──► TOPIC_APPROVED ──► THESIS_I ──► THESIS_II ──► IN_REVIEW ──► READY_FOR_DEFENSE
       │                                              ▲             │
       └──► REJECTED                                  └─────────────┘ (returned for changes)

IN_REVIEW ──► READY_FOR_DEFENSE is the pre-defense gate (Fig. 1 of the proposal): full
committee, manuscript approved, observations resolved, latest similarity check accepted
and every administrative requirement certified. READY_FOR_DEFENSE ──► DEFENDED is added
in Sprint 5 (defense and jury grades).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.models import (
    ObservationStatus,
    ReviewerRole,
    SimilarityVerdict,
    Thesis,
    ThesisStatus,
    ThesisStatusHistory,
    TutorRole,
    User,
    UserRole,
)
from app.services.compliance import missing_requirements

S = ThesisStatus


class Actor(StrEnum):
    ADMIN = "admin"
    TUTOR = "tutor"  # main tutor of the thesis


Check = Callable[[Thesis], str | None]


def has_tutor(thesis: Thesis) -> str | None:
    if not any(t.role == TutorRole.TUTOR for t in thesis.tutors):
        return "A main tutor must be assigned"
    return None


def full_committee(thesis: Thesis) -> str | None:
    """DEC-04/05: exactly 3 reviewers, one of them the president."""
    count = len(thesis.reviewers)
    if count != 3:
        return f"The committee needs 3 reviewers (it has {count})"
    if not any(r.role == ReviewerRole.PRESIDENT for r in thesis.reviewers):
        return "The committee needs a president"
    return None


def all_reviewers_approved(thesis: Thesis) -> str | None:
    pending = [r for r in thesis.reviewers if r.approved_at is None]
    if pending:
        return f"{len(pending)} reviewer(s) have not approved the manuscript"
    return None


def observations_resolved(thesis: Thesis) -> str | None:
    pending = [o for o in thesis.observations if o.status != ObservationStatus.RESOLVED]
    if pending:
        return f"{len(pending)} review observation(s) are not resolved"
    return None


def similarity_accepted(thesis: Thesis) -> str | None:
    if not thesis.similarity_checks:
        return "No similarity check has been recorded"
    latest = thesis.similarity_checks[-1]
    if latest.verdict != SimilarityVerdict.ACCEPTED:
        return (
            f"The latest similarity check ({latest.similarity_percentage}%) exceeds "
            f"the {latest.threshold_applied}% threshold"
        )
    return None


def requirements_certified(thesis: Thesis) -> str | None:
    missing = missing_requirements(object_session(thesis), thesis.student_id)
    if missing:
        return f"{len(missing)} administrative requirement(s) pending: {', '.join(missing)}"
    return None


@dataclass(frozen=True)
class Rule:
    actors: frozenset[Actor]
    checks: tuple[Check, ...] = ()
    comment_required: bool = False
    label: str = ""
    on_apply: Callable[[Thesis], None] | None = field(default=None, compare=False)


def _clear_approvals(thesis: Thesis) -> None:
    """A manuscript sent back for changes must be approved again."""
    for reviewer in thesis.reviewers:
        reviewer.approved_at = None


ADMIN = frozenset({Actor.ADMIN})
ADMIN_OR_TUTOR = frozenset({Actor.ADMIN, Actor.TUTOR})

TRANSITIONS: dict[ThesisStatus, dict[ThesisStatus, Rule]] = {
    S.PROPOSED: {
        S.TOPIC_APPROVED: Rule(ADMIN, (has_tutor,), label="Approve topic"),
        S.REJECTED: Rule(ADMIN, comment_required=True, label="Reject topic"),
    },
    S.TOPIC_APPROVED: {
        S.THESIS_I: Rule(ADMIN, (has_tutor,), label="Start Thesis I"),
    },
    S.THESIS_I: {
        S.THESIS_II: Rule(ADMIN_OR_TUTOR, (has_tutor,), label="Pass to Thesis II"),
    },
    S.THESIS_II: {
        S.IN_REVIEW: Rule(ADMIN_OR_TUTOR, (full_committee,), label="Submit to committee"),
    },
    S.IN_REVIEW: {
        S.READY_FOR_DEFENSE: Rule(
            ADMIN,
            (
                full_committee,
                all_reviewers_approved,
                observations_resolved,
                similarity_accepted,
                requirements_certified,
            ),
            label="Approve for defense",
        ),
        S.THESIS_II: Rule(
            ADMIN,
            comment_required=True,
            label="Return for changes",
            on_apply=_clear_approvals,
        ),
    },
}


def actors_for(user: User, thesis: Thesis) -> set[Actor]:
    if user.role == UserRole.ADMIN:
        return {Actor.ADMIN}
    if user.role == UserRole.PROFESSOR and any(
        t.role == TutorRole.TUTOR and t.professor_id == user.professor_id for t in thesis.tutors
    ):
        return {Actor.TUTOR}
    return set()


def options(user: User, thesis: Thesis) -> list[dict]:
    """Next steps from the current status, with what is still missing for each one.
    Shown to every participant, so students see what their thesis still needs."""
    mine = actors_for(user, thesis)
    result = []
    for target, rule in TRANSITIONS.get(thesis.status, {}).items():
        blockers = [msg for check in rule.checks if (msg := check(thesis))]
        result.append(
            {
                "to_status": target,
                "label": rule.label,
                "actors": sorted(rule.actors),
                "blockers": blockers,
                "comment_required": rule.comment_required,
                "can_perform": bool(mine & rule.actors) and not blockers,
            }
        )
    return result


def record_status(
    db: Session, thesis: Thesis, new_status: ThesisStatus, user: User, comment: str | None
) -> None:
    """Change the status and write the audit row in the same transaction (DEC-08)."""
    db.add(
        ThesisStatusHistory(
            thesis_id=thesis.thesis_id,
            from_status=thesis.status,
            to_status=new_status,
            changed_by=user.user_id,
            comment=comment,
        )
    )
    thesis.status = new_status


def change_status(
    db: Session, user: User, thesis_id: int, target: ThesisStatus, comment: str | None
) -> Thesis:
    # Lock the row: two concurrent transitions must not both read the same old status.
    thesis = db.scalars(
        select(Thesis).where(Thesis.thesis_id == thesis_id).with_for_update()
    ).first()
    if thesis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thesis not found")

    rule = TRANSITIONS.get(thesis.status, {}).get(target)
    if rule is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A thesis cannot go from {thesis.status.value} to {target.value}",
        )
    if not actors_for(user, thesis) & rule.actors:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot perform this change")
    if rule.comment_required and not (comment and comment.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A comment is required")

    blockers = [msg for check in rule.checks if (msg := check(thesis))]
    if blockers:
        raise HTTPException(status.HTTP_409_CONFLICT, "; ".join(blockers))

    if rule.on_apply:
        rule.on_apply(thesis)
    record_status(db, thesis, target, user, comment.strip() if comment else None)
    db.commit()
    return thesis
