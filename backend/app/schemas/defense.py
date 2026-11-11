"""Rooms, defense schedule and jury grades (Sprint 5)."""

import datetime as dt
from decimal import Decimal
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import Defense, DefenseModality

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RoomOut(ORMModel):
    room_id: int
    name: str
    building: str
    capacity: int | None
    is_active: bool
    label: str


class RoomCreate(BaseModel):
    name: Label
    building: Label
    capacity: Annotated[int, Field(gt=0, le=2000)] | None = None


class RoomUpdate(BaseModel):
    name: Label | None = None
    building: Label | None = None
    capacity: Annotated[int, Field(gt=0, le=2000)] | None = None
    is_active: bool | None = None


class DefenseSchedule(BaseModel):
    scheduled_at: dt.datetime
    duration_minutes: Annotated[int, Field(ge=15, le=480)] = 60
    modality: DefenseModality = DefenseModality.IN_PERSON
    room_id: int | None = None
    meeting_url: Annotated[AnyHttpUrl, Field(max_length=255)] | None = None

    @model_validator(mode="after")
    def place_matches_modality(self) -> "DefenseSchedule":
        # Mirrors ck_defenses_place.
        if self.modality == DefenseModality.IN_PERSON and self.room_id is None:
            raise ValueError("An in-person defense needs a room")
        if self.modality == DefenseModality.VIRTUAL and self.meeting_url is None:
            raise ValueError("A virtual defense needs a meeting link")
        return self


class GradeIn(BaseModel):
    grade: Annotated[Decimal, Field(ge=0, le=10, max_digits=4, decimal_places=2)]


class DefenseOut(ORMModel):
    defense_id: int
    scheduled_at: dt.datetime
    ends_at: dt.datetime
    duration_minutes: int
    modality: DefenseModality
    room: RoomOut | None
    meeting_url: str | None
    final_grade: Decimal | None
    # Filled in by the API: grades received so far, the pass mark and the result.
    grades_recorded: int = 0
    min_passing_grade: Decimal | None = None
    passed: bool | None = None


class CalendarItem(DefenseOut):
    thesis_id: int
    thesis_title: str
    student_name: str
    jury: list[str]


class RoomBooking(BaseModel):
    thesis_id: int
    starts_at: dt.datetime
    ends_at: dt.datetime


def defense_out(defense: Defense, min_grade: Decimal, model=DefenseOut, **extra):
    """Build the response with the grades received so far and the pass/fail result."""
    grades = [r.grade for r in defense.thesis.reviewers if r.grade is not None]
    final = defense.final_grade
    return model.model_validate(
        {
            "defense_id": defense.defense_id,
            "scheduled_at": defense.scheduled_at,
            "ends_at": defense.ends_at,
            "duration_minutes": defense.duration_minutes,
            "modality": defense.modality,
            "room": defense.room,
            "meeting_url": defense.meeting_url,
            "final_grade": final,
            "grades_recorded": len(grades),
            "min_passing_grade": min_grade,
            "passed": None if final is None else final >= min_grade,
            **extra,
        }
    )
