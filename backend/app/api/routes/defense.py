"""Rooms, defense scheduling, calendar and jury grades (Sprint 5)."""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.routes.theses import thesis_detail
from app.db import get_db
from app.models import Room, User, UserRole
from app.schemas.defense import (
    CalendarItem,
    DefenseSchedule,
    GradeIn,
    RoomBooking,
    RoomCreate,
    RoomOut,
    RoomUpdate,
    defense_out,
)
from app.schemas.theses import ThesisDetail
from app.services import compliance
from app.services import defense as service
from app.services.access import get_visible_thesis

router = APIRouter(prefix="/api")
admin_only = Depends(require_roles(UserRole.ADMIN))


# ----------------------------------------------------------------------------- rooms


@router.get("/rooms", response_model=list[RoomOut], tags=["Rooms"])
def list_rooms(
    include_inactive: bool = Query(False),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Room).order_by(Room.building, Room.name)
    if not include_inactive:
        query = query.where(Room.is_active.is_(True))
    return list(db.scalars(query))


def _unique_room(db: Session, building: str, name: str, own_id: int | None = None) -> None:
    query = select(Room).where(Room.building == building, Room.name == name)
    if own_id is not None:
        query = query.where(Room.room_id != own_id)
    if db.scalars(query).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This room already exists in the building")


@router.post(
    "/rooms", response_model=RoomOut, status_code=201, tags=["Rooms"], dependencies=[admin_only]
)
def create_room(data: RoomCreate, db: Session = Depends(get_db)):
    _unique_room(db, data.building, data.name)
    room = Room(**data.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.patch("/rooms/{room_id}", response_model=RoomOut, tags=["Rooms"], dependencies=[admin_only])
def update_room(room_id: int, data: RoomUpdate, db: Session = Depends(get_db)):
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "building", "is_active"):
        if field in changes and changes[field] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field} cannot be empty")
    _unique_room(
        db, changes.get("building", room.building), changes.get("name", room.name), room_id
    )
    for field, value in changes.items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms/{room_id}/bookings", response_model=list[RoomBooking], tags=["Rooms"])
def room_bookings(
    room_id: int,
    day: dt.date = Query(..., description="YYYY-MM-DD"),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Busy slots of a room on a day, to pick a free time when scheduling."""
    if db.get(Room, room_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    return [
        RoomBooking(thesis_id=d.thesis_id, starts_at=d.scheduled_at, ends_at=d.ends_at)
        for d in service.room_bookings(db, room_id, day)
    ]


# -------------------------------------------------------------------------- calendar


@router.get("/defenses", response_model=list[CalendarItem], tags=["Defenses"])
def defense_calendar(
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Defenses the user takes part in (all of them for administrators)."""
    min_grade = compliance.min_passing_grade(db)
    return [
        defense_out(
            d,
            min_grade,
            CalendarItem,
            thesis_id=d.thesis_id,
            thesis_title=d.thesis.title,
            student_name=d.thesis.student.full_name,
            jury=[f"{r.professor.full_name} ({r.role.value})" for r in d.thesis.reviewers],
        )
        for d in service.calendar(db, user, date_from, date_to)
    ]


# ----------------------------------------------------------------- schedule and grade


@router.put("/theses/{thesis_id}/defense", response_model=ThesisDetail, tags=["Defenses"])
def schedule_defense(
    thesis_id: int,
    data: DefenseSchedule,
    user: User = admin_only,
    db: Session = Depends(get_db),
) -> ThesisDetail:
    """Schedule or reschedule. 409 explains any room or jury conflict."""
    thesis = service.schedule_defense(
        db,
        thesis_id,
        data.scheduled_at,
        data.duration_minutes,
        data.modality,
        data.room_id,
        str(data.meeting_url) if data.meeting_url else None,
    )
    return thesis_detail(db, thesis, user)


@router.delete("/theses/{thesis_id}/defense", response_model=ThesisDetail, tags=["Defenses"])
def cancel_defense(
    thesis_id: int, user: User = admin_only, db: Session = Depends(get_db)
) -> ThesisDetail:
    return thesis_detail(db, service.cancel_defense(db, thesis_id), user)


@router.put("/theses/{thesis_id}/defense/grade", response_model=ThesisDetail, tags=["Defenses"])
def record_grade(
    thesis_id: int,
    data: GradeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThesisDetail:
    """A jury member records their grade. The third grade closes the thesis as DEFENDED."""
    get_visible_thesis(db, user, thesis_id)  # 404 for non-participants
    return thesis_detail(db, service.record_grade(db, user, thesis_id, data.grade), user)
