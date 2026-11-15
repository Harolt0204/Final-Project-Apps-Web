"""Sprint 2: thesis registration (FR-03) and tutor assignment (FR-04, DEC-03)."""

import datetime as dt

import pytest

from app.models import AcademicPeriod, ThesisStatus
from tests.conftest import login

ADMIN = "admin"
TOPIC = {"title": "Quantum walks on graphs", "abstract": "An abstract."}


@pytest.fixture
def admin(client, world):
    return login(client, ADMIN)


@pytest.fixture
def current_period(db):
    today = dt.date.today()
    period = AcademicPeriod(
        name="Current",
        start_date=today - dt.timedelta(days=30),
        end_date=today + dt.timedelta(days=30),
    )
    db.add(period)
    db.commit()
    return period


# ---------------------------------------------------------------------- registration


def test_student_registers_own_thesis(client, world, current_period):
    headers = login(client, "s3")
    r = client.post("/api/theses", headers=headers, json=TOPIC)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PROPOSED"
    assert body["student"]["full_name"] == "s3 Student"
    assert [p["name"] for p in body["periods"]] == ["Current"]
    assert body["status_history"][0]["to_status"] == "PROPOSED"
    assert body["status_history"][0]["changed_by_name"] == "s3 Student"

    # Only one thesis per student.
    assert client.post("/api/theses", headers=headers, json=TOPIC).status_code == 409


def test_student_cannot_register_for_someone_else(client, world):
    headers = login(client, "s3")
    other = world["students"]["s1"].student_id
    r = client.post("/api/theses", headers=headers, json={**TOPIC, "student_id": other})
    assert r.status_code == 403


def test_professor_cannot_register(client, world):
    headers = login(client, "pC")
    assert client.post("/api/theses", headers=headers, json=TOPIC).status_code == 403


def test_admin_registers_for_a_student(client, admin, world):
    assert client.post("/api/theses", headers=admin, json=TOPIC).status_code == 422
    s3 = world["students"]["s3"].student_id
    r = client.post("/api/theses", headers=admin, json={**TOPIC, "student_id": s3})
    assert r.status_code == 201
    assert r.json()["status_history"][0]["changed_by_name"] == "Administrator"


def test_short_title_is_rejected(client, world):
    headers = login(client, "s3")
    assert client.post("/api/theses", headers=headers, json={"title": "abc"}).status_code == 422


def test_student_edits_topic_only_while_proposed(client, db, world):
    headers = login(client, "s1")
    t1 = world["t1"]
    r = client.patch(f"/api/theses/{t1.thesis_id}", headers=headers, json={"title": "New title"})
    assert r.status_code == 200
    assert r.json()["title"] == "New title"

    # Another student's thesis is invisible.
    t2 = world["t2"].thesis_id
    assert client.patch(f"/api/theses/{t2}", headers=headers, json=TOPIC).status_code == 404

    t1.status = ThesisStatus.THESIS_I
    db.commit()
    r = client.patch(f"/api/theses/{t1.thesis_id}", headers=headers, json={"title": "Later"})
    assert r.status_code == 409


# -------------------------------------------------------------------- tutor assignment


def put_tutor(client, headers, thesis_id, slot, professor):
    return client.put(
        f"/api/theses/{thesis_id}/tutors/{slot}",
        headers=headers,
        json={"professor_id": professor.professor_id},
    )


def test_only_admins_assign_tutors(client, world):
    headers = login(client, "pA")
    r = put_tutor(client, headers, world["t1"].thesis_id, "co-tutor", world["profs"]["pC"])
    assert r.status_code == 403


def test_assign_and_replace_tutors(client, admin, world):
    t1, profs = world["t1"].thesis_id, world["profs"]
    r = put_tutor(client, admin, t1, "co-tutor", profs["pC"])
    assert r.status_code == 200, r.text
    tutors = {t["role"]: t["professor"]["full_name"] for t in r.json()["tutors"]}
    assert tutors == {"Tutor": "pA Prof", "Co-Tutor": "pC Prof"}

    # Professor C now sees the thesis, as co-tutor.
    prof_c = login(client, "pC")
    listed = client.get("/api/theses", headers=prof_c).json()
    assert [(t["thesis_id"], t["my_roles"]) for t in listed] == [(t1, ["Co-Tutor"])]


def test_same_professor_cannot_be_tutor_and_cotutor(client, admin, world):
    r = put_tutor(client, admin, world["t1"].thesis_id, "co-tutor", world["profs"]["pA"])
    assert r.status_code == 409


def test_reviewer_cannot_be_tutor(client, admin, world):
    # pB is president of thesis 1.
    r = put_tutor(client, admin, world["t1"].thesis_id, "tutor", world["profs"]["pB"])
    assert r.status_code == 409
    assert "reviewer" in r.json()["detail"]


def test_cotutor_requires_main_tutor(client, admin, world, db):
    s3 = world["students"]["s3"].student_id
    created = client.post("/api/theses", headers=admin, json={**TOPIC, "student_id": s3}).json()
    r = put_tutor(client, admin, created["thesis_id"], "co-tutor", world["profs"]["pC"])
    assert r.status_code == 409


def test_remove_tutors(client, admin, world):
    t1, profs = world["t1"].thesis_id, world["profs"]
    put_tutor(client, admin, t1, "co-tutor", profs["pC"])
    assert client.delete(f"/api/theses/{t1}/tutors/tutor", headers=admin).status_code == 409
    assert client.delete(f"/api/theses/{t1}/tutors/co-tutor", headers=admin).status_code == 200
    r = client.delete(f"/api/theses/{t1}/tutors/tutor", headers=admin)
    assert r.status_code == 200
    assert r.json()["tutors"] == []
    assert client.delete(f"/api/theses/{t1}/tutors/tutor", headers=admin).status_code == 404


def test_closed_thesis_cannot_change_tutors(client, admin, world, db):
    world["t1"].status = ThesisStatus.DEFENDED
    db.commit()
    r = put_tutor(client, admin, world["t1"].thesis_id, "co-tutor", world["profs"]["pC"])
    assert r.status_code == 409
