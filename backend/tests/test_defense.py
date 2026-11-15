"""Sprint 5: rooms, defense scheduling with conflict detection, jury grading."""

import datetime as dt

import pytest

from app.core.security import hash_password
from app.models import (
    Defense,
    Professor,
    ReviewerAssignment,
    ReviewerRole,
    Room,
    SystemSetting,
    ThesisStatus,
    ThesisStatusHistory,
    User,
    UserRole,
)
from app.schemas.users import username_from_email
from tests.conftest import PASSWORD, login

ADMIN = "admin"


def email(key: str) -> str:
    return f"{key}@yachaytech.edu.ec"


def at(days: int, hour: int, minute: int = 0) -> str:
    moment = dt.datetime.combine(dt.date.today() + dt.timedelta(days=days), dt.time(hour, minute))
    return moment.isoformat()


@pytest.fixture
def admin(client, world):
    return login(client, ADMIN)


@pytest.fixture
def setup(db, world):
    """Both theses READY_FOR_DEFENSE with full juries that share professor pC.

    thesis 1: tutor pA; jury pB (president), pC, pD
    thesis 2: tutor pB; jury pA (committee, from the world), pC, pE (president)
    """
    profs = dict(world["profs"])
    for key in ("pD", "pE"):
        prof = Professor(first_name=key, last_name="Prof", email=email(key))
        db.add(prof)
        db.add(
            User(
                username=username_from_email(prof.email),
                password_hash=hash_password(PASSWORD),
                role=UserRole.PROFESSOR,
                professor=prof,
            )
        )
        profs[key] = prof
    t1, t2 = world["t1"], world["t2"]
    db.add_all(
        [
            ReviewerAssignment(thesis=t1, professor=profs["pC"]),
            ReviewerAssignment(thesis=t1, professor=profs["pD"]),
            ReviewerAssignment(thesis=t2, professor=profs["pC"]),
            ReviewerAssignment(thesis=t2, professor=profs["pE"], role=ReviewerRole.PRESIDENT),
        ]
    )
    rooms = [Room(name="Auditorium A", building="Main"), Room(name="Room 101", building="Main")]
    db.add_all(rooms)
    db.add(SystemSetting(setting_key="defense_min_passing_grade", value="7.00"))
    t1.status = t2.status = ThesisStatus.READY_FOR_DEFENSE
    db.commit()
    return {"t1": t1.thesis_id, "t2": t2.thesis_id, "rooms": rooms, "profs": profs}


def schedule(client, headers, thesis_id, **data):
    return client.put(f"/api/theses/{thesis_id}/defense", headers=headers, json=data)


def in_room(room, when, minutes=60):
    return {"scheduled_at": when, "duration_minutes": minutes, "room_id": room.room_id}


# ----------------------------------------------------------------------------- rooms


def test_rooms(client, admin, world):
    r = client.post("/api/rooms", headers=admin, json={"name": "Lab 3", "building": "Science"})
    assert r.status_code == 201
    assert r.json()["label"] == "Lab 3 (Science)"
    again = client.post("/api/rooms", headers=admin, json={"name": "Lab 3", "building": "Science"})
    assert again.status_code == 409

    student = login(client, "s1")
    assert [x["name"] for x in client.get("/api/rooms", headers=student).json()] == ["Lab 3"]
    assert (
        client.post("/api/rooms", headers=student, json={"name": "X", "building": "Y"}).status_code
        == 403
    )


# ------------------------------------------------------------------------ scheduling


def test_schedule_requires_ready_thesis_and_valid_place(client, admin, world, db, setup):
    room = setup["rooms"][0]
    world["t1"].status = ThesisStatus.IN_REVIEW
    db.commit()
    assert schedule(client, admin, setup["t1"], **in_room(room, at(3, 10))).status_code == 409

    world["t1"].status = ThesisStatus.READY_FOR_DEFENSE
    db.commit()
    assert schedule(client, admin, setup["t1"], **in_room(room, at(-1, 10))).status_code == 422
    assert schedule(client, admin, setup["t1"], scheduled_at=at(3, 10)).status_code == 422
    virtual_no_link = {"scheduled_at": at(3, 10), "modality": "Virtual"}
    assert schedule(client, admin, setup["t1"], **virtual_no_link).status_code == 422

    r = schedule(client, admin, setup["t1"], **in_room(room, at(3, 10), 90))
    assert r.status_code == 200, r.text
    defense = r.json()["defense"]
    assert defense["room"]["name"] == "Auditorium A"
    assert defense["ends_at"].endswith("11:30:00")


def test_room_conflict(client, admin, setup):
    room = setup["rooms"][0]
    assert schedule(client, admin, setup["t1"], **in_room(room, at(3, 10), 90)).status_code == 200
    # Thesis 2 in the same room at 11:00 overlaps 10:00-11:30.
    r = schedule(client, admin, setup["t2"], **in_room(room, at(3, 11)))
    assert r.status_code == 409
    assert "Auditorium A (Main) is booked" in r.json()["detail"]


def test_jury_conflict(client, admin, setup):
    a, b = setup["rooms"]
    assert schedule(client, admin, setup["t1"], **in_room(a, at(3, 10))).status_code == 200
    # Another room, same time: professor pC sits on both juries.
    r = schedule(client, admin, setup["t2"], **in_room(b, at(3, 10, 30)))
    assert r.status_code == 409
    assert "pC Prof" in r.json()["detail"]
    # A virtual defense still blocks the jury.
    virtual = {
        "scheduled_at": at(3, 10, 30),
        "modality": "Virtual",
        "meeting_url": "https://meet.example.org/abc",
    }
    assert schedule(client, admin, setup["t2"], **virtual).status_code == 409
    # Right after the first one ends there is no conflict.
    assert schedule(client, admin, setup["t2"], **in_room(a, at(3, 11))).status_code == 200


def test_reschedule_and_cancel(client, admin, setup):
    room = setup["rooms"][0]
    schedule(client, admin, setup["t1"], **in_room(room, at(3, 10)))
    # Moving its own defense by 30 minutes does not conflict with itself.
    assert schedule(client, admin, setup["t1"], **in_room(room, at(3, 10, 30))).status_code == 200
    bookings = client.get(
        f"/api/rooms/{room.room_id}/bookings",
        headers=admin,
        params={"day": at(3, 0)[:10]},
    ).json()
    assert [b["starts_at"][11:16] for b in bookings] == ["10:30"]

    r = client.delete(f"/api/theses/{setup['t1']}/defense", headers=admin)
    assert r.status_code == 200
    assert r.json()["defense"] is None


def test_calendar_visibility(client, admin, setup):
    a, b = setup["rooms"]
    schedule(client, admin, setup["t1"], **in_room(a, at(3, 9)))
    schedule(client, admin, setup["t2"], **in_room(b, at(4, 9)))

    def thesis_ids(key):
        rows = client.get("/api/defenses", headers=login(client, key)).json()
        return [row["thesis_id"] for row in rows]

    assert thesis_ids("pC") == [setup["t1"], setup["t2"]]  # jury of both
    assert thesis_ids("s1") == [setup["t1"]]
    assert thesis_ids("s3") == []
    ranged = client.get("/api/defenses", headers=admin, params={"date_from": at(4, 0)[:10]})
    assert [row["thesis_id"] for row in ranged.json()] == [setup["t2"]]


# --------------------------------------------------------------------------- grading


@pytest.fixture
def past_defense(db, setup):
    """Thesis 1's defense started an hour ago (grading is only allowed after the start)."""
    db.add(
        Defense(
            thesis_id=setup["t1"],
            scheduled_at=dt.datetime.now() - dt.timedelta(hours=1),
            room_id=setup["rooms"][0].room_id,
        )
    )
    db.commit()
    return setup["t1"]


def grade(client, key, thesis_id, value):
    return client.put(
        f"/api/theses/{thesis_id}/defense/grade",
        headers=login(client, key),
        json={"grade": value},
    )


def test_grades_close_the_thesis(client, admin, db, past_defense):
    assert grade(client, "pA", past_defense, "9").status_code == 403  # tutor, not jury
    assert grade(client, "pB", past_defense, "11").status_code == 422

    assert grade(client, "pB", past_defense, "9").status_code == 200
    r = grade(client, "pC", past_defense, "8.5")
    assert r.json()["status"] == "READY_FOR_DEFENSE"
    assert r.json()["defense"]["grades_recorded"] == 2

    r = grade(client, "pD", past_defense, "8")
    body = r.json()
    assert body["status"] == "DEFENDED"
    assert body["defense"]["final_grade"] == "8.50"
    assert body["defense"]["passed"] is True

    last = db.query(ThesisStatusHistory).order_by(ThesisStatusHistory.history_id.desc()).first()
    assert (last.to_status, last.comment) == (ThesisStatus.DEFENDED, "Final grade 8.50 (passed)")

    # The student sees the final grade, not each jury member's.
    student = client.get(f"/api/theses/{past_defense}", headers=login(client, "s1")).json()
    assert student["defense"]["final_grade"] == "8.50"
    assert all(rv["grade"] is None for rv in student["reviewers"])

    # A graded defense is final.
    assert grade(client, "pB", past_defense, "10").status_code == 409
    assert client.delete(f"/api/theses/{past_defense}/defense", headers=admin).status_code == 409


def test_failing_average(client, past_defense):
    for key, value in (("pB", "6"), ("pC", "7"), ("pD", "6.5")):
        r = grade(client, key, past_defense, value)
    assert r.json()["defense"]["final_grade"] == "6.50"
    assert r.json()["defense"]["passed"] is False


def test_no_grades_before_the_defense(client, admin, setup):
    schedule(client, admin, setup["t1"], **in_room(setup["rooms"][0], at(2, 10)))
    r = grade(client, "pB", setup["t1"], "9")
    assert r.status_code == 409
    assert "once the defense has started" in r.json()["detail"]
