"""Defense scheduling with conflict detection (DEC-09) and jury grading (FR-09, DEC-05).

Scheduling (administrators), only for theses READY_FOR_DEFENSE:
- the date must be in the future and the room active (in-person) or a link given (virtual);
- no other defense may overlap in the same room;
- no jury member (the 3 reviewers) may have another defense that overlaps.
MySQL has no range exclusion constraints, so overlaps are checked here while the
candidate rows are locked (SELECT ... FOR UPDATE), as documentation.md §8.1 proposes.

Grading (jury members), once the defense has started: each member records a 0-10 grade.
When the third grade arrives, the final grade is their average (D-8 default) and the
thesis becomes DEFENDED in the same transaction, with its status history row.
"""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Defense,
    DefenseModality,
    ReviewerAssignment,
    Room,
    Thesis,
    ThesisStatus,
    User,
    UserRole,
)
from app.services import compliance
from app.services.access import visibility_clause
from app.services.workflow import record_status

MAX_DURATION = dt.timedelta(minutes=480)


def _error(code: int, message: str) -> HTTPException:
    return HTTPException(code, message)


def _now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


def _fmt(moment: dt.datetime) -> str:
    return moment.strftime("%d %b %Y %H:%M")


def _lock_thesis(db: Session, thesis_id: int) -> Thesis:
    thesis = db.scalars(
        select(Thesis).where(Thesis.thesis_id == thesis_id).with_for_update()
    ).first()
    if thesis is None:
        raise _error(status.HTTP_404_NOT_FOUND, "Thesis not found")
    return thesis


def overlapping_defenses(
    db: Session, start: dt.datetime, end: dt.datetime, exclude_thesis_id: int | None = None
) -> list[Defense]:
    """Defenses that overlap [start, end), locked for the rest of the transaction.

    A defense lasts at most 8 hours, so only those starting in (start - 8h, end) can
    overlap; the exact test runs in Python, which keeps the query portable."""
    query = (
        select(Defense)
        .where(Defense.scheduled_at < end, Defense.scheduled_at > start - MAX_DURATION)
        .options(selectinload(Defense.room), selectinload(Defense.thesis))
        .with_for_update()
    )
    if exclude_thesis_id is not None:
        query = query.where(Defense.thesis_id != exclude_thesis_id)
    return [d for d in db.scalars(query) if d.ends_at > start]


def schedule_defense(
    db: Session,
    thesis_id: int,
    scheduled_at: dt.datetime,
    duration_minutes: int,
    modality: DefenseModality,
    room_id: int | None,
    meeting_url: str | None,
) -> Thesis:
    thesis = _lock_thesis(db, thesis_id)
    if thesis.status != ThesisStatus.READY_FOR_DEFENSE:
        raise _error(status.HTTP_409_CONFLICT, "Only theses approved for defense can be scheduled")
    if any(r.grade is not None for r in thesis.reviewers):
        raise _error(
            status.HTTP_409_CONFLICT, "Grading has started; the defense can no longer change"
        )

    start = scheduled_at.replace(tzinfo=None, second=0, microsecond=0)
    if start <= _now():
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "The defense must be in the future")
    end = start + dt.timedelta(minutes=duration_minutes)

    if modality == DefenseModality.IN_PERSON:
        room = db.get(Room, room_id)
        if room is None or not room.is_active:
            raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "Room not found or inactive")

    jury = {r.professor_id: r.professor.full_name for r in thesis.reviewers}
    for other in overlapping_defenses(db, start, end, exclude_thesis_id=thesis_id):
        when = f"{_fmt(other.scheduled_at)}–{other.ends_at.strftime('%H:%M')}"
        if modality == DefenseModality.IN_PERSON and other.room_id == room_id:
            raise _error(
                status.HTTP_409_CONFLICT,
                f"{other.room.label} is booked {when} (thesis #{other.thesis_id})",
            )
        busy = [jury[r.professor_id] for r in other.thesis.reviewers if r.professor_id in jury]
        if busy:
            raise _error(
                status.HTTP_409_CONFLICT,
                f"{', '.join(busy)} already sit(s) on another jury {when} "
                f"(thesis #{other.thesis_id})",
            )

    defense = thesis.defense or Defense(thesis_id=thesis_id)
    defense.scheduled_at = start
    defense.duration_minutes = duration_minutes
    defense.modality = modality
    defense.room_id = room_id if modality == DefenseModality.IN_PERSON else None
    defense.meeting_url = meeting_url if modality == DefenseModality.VIRTUAL else None
    db.add(defense)
    db.commit()
    return thesis


def cancel_defense(db: Session, thesis_id: int) -> Thesis:
    thesis = _lock_thesis(db, thesis_id)
    if thesis.defense is None:
        raise _error(status.HTTP_404_NOT_FOUND, "No defense is scheduled")
    if thesis.defense.final_grade is not None or any(r.grade is not None for r in thesis.reviewers):
        raise _error(status.HTTP_409_CONFLICT, "A graded defense cannot be cancelled")
    db.delete(thesis.defense)
    db.commit()
    return thesis


def record_grade(db: Session, user: User, thesis_id: int, grade: Decimal) -> Thesis:
    thesis = _lock_thesis(db, thesis_id)
    if thesis.status != ThesisStatus.READY_FOR_DEFENSE:
        raise _error(status.HTTP_409_CONFLICT, "The thesis is not awaiting its defense")
    defense = thesis.defense
    if defense is None:
        raise _error(status.HTTP_409_CONFLICT, "No defense is scheduled")

    member: ReviewerAssignment | None = next(
        (
            r
            for r in thesis.reviewers
            if user.role == UserRole.PROFESSOR and r.professor_id == user.professor_id
        ),
        None,
    )
    if member is None:
        raise _error(status.HTTP_403_FORBIDDEN, "Only jury members grade the defense")
    if _now() < defense.scheduled_at:
        raise _error(
            status.HTTP_409_CONFLICT, "Grades can be recorded once the defense has started"
        )

    member.grade = grade
    grades = [r.grade for r in thesis.reviewers]
    if len(grades) == 3 and all(g is not None for g in grades):
        final = (sum(grades) / 3).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        defense.final_grade = final
        result = "passed" if final >= compliance.min_passing_grade(db) else "failed"
        record_status(db, thesis, ThesisStatus.DEFENDED, user, f"Final grade {final} ({result})")
    db.commit()
    return thesis


def calendar(
    db: Session, user: User, date_from: dt.date | None, date_to: dt.date | None
) -> list[Defense]:
    """Defenses the user can see, optionally within [date_from, date_to]."""
    query = (
        select(Defense)
        .join(Thesis, Thesis.thesis_id == Defense.thesis_id)
        .options(
            selectinload(Defense.room),
            selectinload(Defense.thesis).selectinload(Thesis.student),
            selectinload(Defense.thesis)
            .selectinload(Thesis.reviewers)
            .selectinload(ReviewerAssignment.professor),
        )
        .order_by(Defense.scheduled_at)
    )
    clause = visibility_clause(user)
    if clause is not None:
        query = query.where(clause)
    if date_from:
        query = query.where(Defense.scheduled_at >= dt.datetime.combine(date_from, dt.time()))
    if date_to:
        query = query.where(
            Defense.scheduled_at < dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time())
        )
    return list(db.scalars(query))


def room_bookings(db: Session, room_id: int, day: dt.date) -> list[Defense]:
    start = dt.datetime.combine(day, dt.time())
    query = (
        select(Defense)
        .where(
            Defense.room_id == room_id,
            Defense.scheduled_at >= start,
            Defense.scheduled_at < start + dt.timedelta(days=1),
        )
        .order_by(Defense.scheduled_at)
    )
    return list(db.scalars(query))
