"""Sprint 6: analytical reports."""

import datetime as dt

import pytest

from app.models import (
    Defense,
    Room,
    School,
    SystemSetting,
    ThesisStatus,
)
from tests.conftest import login

ADMIN = "admin@yachaytech.edu.ec"


@pytest.fixture
def admin(client, world):
    return login(client, ADMIN)


@pytest.fixture
def data(db, world):
    """Thesis 1 defended (MATH, 8.25), thesis 2 defended (no school, 6.50)."""
    math = School(code="MATH", name="School of Mathematical and Computational Sciences")
    room = Room(name="Auditorium A", building="Main")
    db.add_all([math, room, SystemSetting(setting_key="defense_min_passing_grade", value="7.00")])
    world["students"]["s1"].school = math
    t1, t2 = world["t1"], world["t2"]
    t1.status = t2.status = ThesisStatus.DEFENDED
    db.flush()
    db.add_all(
        [
            Defense(
                thesis_id=t1.thesis_id,
                scheduled_at=dt.datetime(2026, 10, 1, 9, 0),
                room_id=room.room_id,
                final_grade=8.25,
            ),
            Defense(
                thesis_id=t2.thesis_id,
                scheduled_at=dt.datetime(2026, 10, 2, 9, 0),
                room_id=room.room_id,
                final_grade=6.5,
            ),
        ]
    )
    db.commit()
    return {"room": room}


def test_reports_are_admin_only(client, world):
    prof = login(client, "pA@yachaytech.edu.ec")
    for path in ("overview", "tutor-workload", "grades-by-school", "room-availability"):
        assert client.get(f"/api/reports/{path}", headers=prof).status_code == 403


def test_overview(client, admin, world):
    body = client.get("/api/reports/overview", headers=admin).json()
    assert body["total_theses"] == 2
    assert body["by_status"]["PROPOSED"] == 2
    assert body["active_theses"] == 2


def test_tutor_workload_counts_active_roles(client, admin, world, db):
    rows = {
        r["full_name"]: r for r in client.get("/api/reports/tutor-workload", headers=admin).json()
    }
    # pA tutors thesis 1 and sits on thesis 2's committee; pB tutors 2 and presides 1.
    assert (rows["pA Prof"]["tutor_active"], rows["pA Prof"]["committee_active"]) == (1, 1)
    assert (rows["pB Prof"]["tutor_active"], rows["pB Prof"]["president_active"]) == (1, 1)
    assert rows["pC Prof"]["total_active"] == 0

    # Defended theses leave the active load and count as supervised.
    world["t1"].status = ThesisStatus.DEFENDED
    db.commit()
    rows = {
        r["full_name"]: r for r in client.get("/api/reports/tutor-workload", headers=admin).json()
    }
    assert rows["pA Prof"]["tutor_active"] == 0
    assert rows["pA Prof"]["supervised_defended"] == 1
    assert rows["pB Prof"]["president_active"] == 0


def test_grades_by_school(client, admin, data):
    body = client.get("/api/reports/grades-by-school", headers=admin).json()
    assert body["overall_average"] == "7.38"
    schools = {s["school_code"]: s for s in body["schools"]}
    assert schools["MATH"]["average_grade"] == "8.25"
    assert schools["MATH"]["pass_rate"] == "100.00"
    assert schools["—"]["passed"] == 0  # 6.50 is below the 7.00 pass mark

    ranged = client.get(
        "/api/reports/grades-by-school", headers=admin, params={"date_from": "2026-10-02"}
    ).json()
    assert [s["school_code"] for s in ranged["schools"]] == ["—"]


def test_room_availability(client, admin, data):
    body = client.get(
        "/api/reports/room-availability",
        headers=admin,
        params={"date_from": "2026-10-01", "days": 2},
    ).json()
    room = body["rooms"][0]
    day1 = room["days"][0]
    assert [b["start"][11:16] for b in day1["bookings"]] == ["09:00"]
    assert [(w["start"][11:16], w["end"][11:16]) for w in day1["free"]] == [
        ("08:00", "09:00"),
        ("10:00", "18:00"),
    ]
    assert day1["occupancy"] == "10.00"  # 60 of 600 working minutes
    assert room["occupancy"] == "10.00"  # 120 of 1200 over both days
    assert (
        client.get("/api/reports/room-availability", headers=admin, params={"days": 40}).status_code
        == 422
    )


def test_workload_by_period(client, admin, world, db):
    from app.models import AcademicPeriod

    period = AcademicPeriod(
        name="2026-II", start_date=dt.date(2026, 9, 1), end_date=dt.date(2027, 1, 29)
    )
    db.add(period)
    world["t1"].periods = [period]
    db.commit()
    rows = client.get(
        "/api/reports/tutor-workload", headers=admin, params={"period_id": period.period_id}
    ).json()
    totals = {r["full_name"]: r["total_active"] for r in rows}
    assert totals["pA Prof"] == 1  # thesis 2 is not in the period
    assert totals["pB Prof"] == 1
