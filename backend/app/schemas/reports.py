"""Analytical reports (Sprint 6)."""

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class Overview(BaseModel):
    total_theses: int
    active_theses: int
    by_status: dict[str, int]
    upcoming_defenses_30_days: int


class WorkloadRow(BaseModel):
    professor_id: int
    full_name: str
    school: str | None
    tutor_active: int
    cotutor_active: int
    president_active: int
    committee_active: int
    total_active: int
    supervised_defended: int


class SchoolGrades(BaseModel):
    school_code: str
    school_name: str
    defenses: int
    average_grade: Decimal
    min_grade: Decimal
    max_grade: Decimal
    passed: int
    pass_rate: Decimal


class GradesBySchool(BaseModel):
    min_passing_grade: Decimal
    overall_average: Decimal | None
    schools: list[SchoolGrades]


class Booking(BaseModel):
    thesis_id: int
    thesis_title: str
    start: dt.datetime
    end: dt.datetime


class Window(BaseModel):
    start: dt.datetime
    end: dt.datetime


class RoomDay(BaseModel):
    day: dt.date
    bookings: list[Booking]
    free: list[Window]
    occupancy: Decimal


class RoomAvailabilityRow(BaseModel):
    room_id: int
    label: str
    capacity: int | None
    occupancy: Decimal
    days: list[RoomDay]


class RoomAvailability(BaseModel):
    date_from: dt.date
    days: int
    working_hours: str
    rooms: list[RoomAvailabilityRow]
