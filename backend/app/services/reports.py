"""Analytical reports (objective 5 of the proposal): tutor workload, average defense
grade by school and defense-room availability, plus a status overview.

Volumes are small (one university's theses), so the queries load the rows once and
aggregate in Python, which keeps the code portable between MySQL and the SQLite tests.
"""

import datetime as dt
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Defense,
    Professor,
    ReviewerAssignment,
    ReviewerRole,
    Room,
    Student,
    Thesis,
    ThesisStatus,
    TutorAssignment,
    TutorRole,
    thesis_period,
)
from app.services import compliance

CLOSED = {ThesisStatus.DEFENDED, ThesisStatus.REJECTED}
# Working day used to compute free slots and occupancy in the room report.
DAY_START = dt.time(8, 0)
DAY_END = dt.time(18, 0)


def _two(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _thesis_ids_in_period(db: Session, period_id: int | None) -> set[int] | None:
    if period_id is None:
        return None
    rows = db.execute(
        select(thesis_period.c.thesis_id).where(thesis_period.c.period_id == period_id)
    )
    return {r[0] for r in rows}


# ------------------------------------------------------------------------- overview


def overview(db: Session) -> dict:
    statuses = Counter(db.scalars(select(Thesis.status)))
    now = dt.datetime.now()
    upcoming = db.scalars(
        select(Defense.defense_id).where(
            Defense.scheduled_at >= now, Defense.scheduled_at < now + dt.timedelta(days=30)
        )
    ).all()
    return {
        "total_theses": sum(statuses.values()),
        "by_status": {s.value: statuses.get(s, 0) for s in ThesisStatus},
        "active_theses": sum(n for s, n in statuses.items() if s not in CLOSED),
        "upcoming_defenses_30_days": len(upcoming),
    }


# ------------------------------------------------------------------- tutor workload


def tutor_workload(db: Session, period_id: int | None = None) -> list[dict]:
    """Per professor: how many theses they tutor, co-tutor, preside or review.
    "Active" excludes defended and rejected theses."""
    in_period = _thesis_ids_in_period(db, period_id)
    professors = db.scalars(
        select(Professor)
        .options(selectinload(Professor.school))
        .order_by(Professor.last_name, Professor.first_name)
    ).all()
    status_of = dict(db.execute(select(Thesis.thesis_id, Thesis.status)).all())

    def counted(thesis_id: int) -> bool:
        return in_period is None or thesis_id in in_period

    rows = {
        p.professor_id: {
            "professor_id": p.professor_id,
            "full_name": p.full_name,
            "school": p.school.code if p.school else None,
            "tutor_active": 0,
            "cotutor_active": 0,
            "president_active": 0,
            "committee_active": 0,
            "supervised_defended": 0,
        }
        for p in professors
    }
    for a in db.scalars(select(TutorAssignment)):
        if not counted(a.thesis_id):
            continue
        row, closed = rows[a.professor_id], status_of[a.thesis_id] in CLOSED
        if a.role == TutorRole.TUTOR and status_of[a.thesis_id] == ThesisStatus.DEFENDED:
            row["supervised_defended"] += 1
        if not closed:
            row["tutor_active" if a.role == TutorRole.TUTOR else "cotutor_active"] += 1
    for r in db.scalars(select(ReviewerAssignment)):
        if counted(r.thesis_id) and status_of[r.thesis_id] not in CLOSED:
            key = "president_active" if r.role == ReviewerRole.PRESIDENT else "committee_active"
            rows[r.professor_id][key] += 1

    result = []
    for row in rows.values():
        row["total_active"] = (
            row["tutor_active"]
            + row["cotutor_active"]
            + row["president_active"]
            + row["committee_active"]
        )
        result.append(row)
    return sorted(result, key=lambda r: (-r["total_active"], r["full_name"]))


# -------------------------------------------------------------- grades by school


def grades_by_school(
    db: Session, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> dict:
    """Final defense grade per school of the student, for graded defenses."""
    query = (
        select(Defense)
        .where(Defense.final_grade.is_not(None))
        .options(
            selectinload(Defense.thesis).selectinload(Thesis.student).selectinload(Student.school)
        )
    )
    if date_from:
        query = query.where(Defense.scheduled_at >= dt.datetime.combine(date_from, dt.time()))
    if date_to:
        end = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time())
        query = query.where(Defense.scheduled_at < end)

    min_grade = compliance.min_passing_grade(db)
    groups: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for d in db.scalars(query):
        school = d.thesis.student.school
        key = (school.code, school.name) if school else ("—", "No school recorded")
        groups[key].append(Decimal(d.final_grade))

    schools = []
    for (code, name), grades in sorted(groups.items(), key=lambda g: g[0][1]):
        passed = sum(1 for g in grades if g >= min_grade)
        schools.append(
            {
                "school_code": code,
                "school_name": name,
                "defenses": len(grades),
                "average_grade": _two(sum(grades) / len(grades)),
                "min_grade": _two(min(grades)),
                "max_grade": _two(max(grades)),
                "passed": passed,
                "pass_rate": _two(Decimal(100 * passed) / len(grades)),
            }
        )
    all_grades = [g for grades in groups.values() for g in grades]
    return {
        "min_passing_grade": min_grade,
        "overall_average": _two(sum(all_grades) / len(all_grades)) if all_grades else None,
        "schools": schools,
    }


# ------------------------------------------------------------- room availability


def _free_windows(day: dt.date, busy: list[tuple[dt.datetime, dt.datetime]]) -> list[dict]:
    cursor = dt.datetime.combine(day, DAY_START)
    close = dt.datetime.combine(day, DAY_END)
    windows = []
    for start, end in sorted(busy):
        start, end = max(start, cursor), min(end, close)
        if start > cursor:
            windows.append({"start": cursor, "end": start})
        cursor = max(cursor, end)
    if cursor < close:
        windows.append({"start": cursor, "end": close})
    return windows


def room_availability(db: Session, date_from: dt.date, days: int) -> dict:
    """Per active room and day: bookings, free windows within the working day and
    occupancy percentage."""
    start = dt.datetime.combine(date_from, dt.time())
    end = start + dt.timedelta(days=days)
    rooms = db.scalars(
        select(Room).where(Room.is_active.is_(True)).order_by(Room.building, Room.name)
    ).all()
    defenses = db.scalars(
        select(Defense)
        .where(
            Defense.room_id.is_not(None), Defense.scheduled_at >= start, Defense.scheduled_at < end
        )
        .options(selectinload(Defense.thesis))
        .order_by(Defense.scheduled_at)
    ).all()
    by_room_day: dict[tuple[int, dt.date], list[Defense]] = defaultdict(list)
    for d in defenses:
        by_room_day[(d.room_id, d.scheduled_at.date())].append(d)

    working_minutes = (
        dt.datetime.combine(date_from, DAY_END) - dt.datetime.combine(date_from, DAY_START)
    ).seconds // 60
    result = []
    for room in rooms:
        room_days, busy_total = [], 0
        for offset in range(days):
            day = date_from + dt.timedelta(days=offset)
            booked = by_room_day.get((room.room_id, day), [])
            day_open = dt.datetime.combine(day, DAY_START)
            day_close = dt.datetime.combine(day, DAY_END)
            busy_minutes = sum(
                max(0, (min(d.ends_at, day_close) - max(d.scheduled_at, day_open)).seconds // 60)
                for d in booked
                if d.ends_at > day_open and d.scheduled_at < day_close
            )
            busy_total += busy_minutes
            room_days.append(
                {
                    "day": day,
                    "bookings": [
                        {
                            "thesis_id": d.thesis_id,
                            "thesis_title": d.thesis.title,
                            "start": d.scheduled_at,
                            "end": d.ends_at,
                        }
                        for d in booked
                    ],
                    "free": _free_windows(day, [(d.scheduled_at, d.ends_at) for d in booked]),
                    "occupancy": _two(Decimal(100 * busy_minutes) / working_minutes),
                }
            )
        result.append(
            {
                "room_id": room.room_id,
                "label": room.label,
                "capacity": room.capacity,
                "days": room_days,
                "occupancy": _two(Decimal(100 * busy_total) / (working_minutes * days)),
            }
        )
    return {
        "date_from": date_from,
        "days": days,
        "working_hours": f"{DAY_START:%H:%M}-{DAY_END:%H:%M}",
        "rooms": result,
    }
