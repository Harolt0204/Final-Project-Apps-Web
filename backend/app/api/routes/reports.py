"""Analytical reports for coordination (administrators only)."""

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db import get_db
from app.models import UserRole
from app.schemas.reports import GradesBySchool, Overview, RoomAvailability, WorkloadRow
from app.services import reports

router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.get("/overview", response_model=Overview)
def overview(db: Session = Depends(get_db)):
    return reports.overview(db)


@router.get("/tutor-workload", response_model=list[WorkloadRow])
def tutor_workload(
    period_id: int | None = Query(None, description="Only theses of this academic period"),
    db: Session = Depends(get_db),
):
    """Active theses per professor by role, and theses they supervised to defense."""
    return reports.tutor_workload(db, period_id)


@router.get("/grades-by-school", response_model=GradesBySchool)
def grades_by_school(
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    db: Session = Depends(get_db),
):
    """Average, range and pass rate of final defense grades, by the student's school."""
    return reports.grades_by_school(db, date_from, date_to)


@router.get("/room-availability", response_model=RoomAvailability)
def room_availability(
    date_from: dt.date | None = None,
    days: int = Query(7, ge=1, le=31),
    db: Session = Depends(get_db),
):
    """Bookings, free windows (08:00-18:00) and occupancy of each active room."""
    return reports.room_availability(db, date_from or dt.date.today(), days)
