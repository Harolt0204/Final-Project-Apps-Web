"""Sprint 2: students, professors, schools and academic periods."""

import pytest

from app.models import School
from tests.conftest import login

ADMIN = "admin"


@pytest.fixture
def admin(client, world):
    return login(client, ADMIN)


@pytest.fixture
def school(db):
    school = School(code="MATH", name="School of Mathematical and Computational Sciences")
    db.add(school)
    db.commit()
    return school


def new_student(**overrides):
    data = {
        "first_name": "Ana",
        "last_name": "Vera",
        "email": "ana.vera@yachaytech.edu.ec",
        "national_id": "1712345678",
    }
    return {**data, **overrides}


def test_people_endpoints_are_admin_only(client, world):
    headers = login(client, "pA")
    assert client.get("/api/students", headers=headers).status_code == 403
    assert client.get("/api/professors", headers=headers).status_code == 403
    assert client.post("/api/students", headers=headers, json=new_student()).status_code == 403


def test_create_student_with_school_and_account(client, admin, school):
    payload = new_student(school_id=school.school_id, account_password="first-password-1")
    r = client.post("/api/students", headers=admin, json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["school"]["code"] == "MATH"
    assert body["has_account"] is True
    assert body["has_thesis"] is False
    # The new account can log in right away.
    login(client, "ana.vera", "first-password-1")


def test_duplicate_email_or_national_id_is_409(client, admin):
    assert client.post("/api/students", headers=admin, json=new_student()).status_code == 201
    dup_email = new_student(national_id="0999999999")
    dup_id = new_student(email="other@yachaytech.edu.ec")
    for payload in (dup_email, dup_id):
        r = client.post("/api/students", headers=admin, json=payload)
        assert r.status_code == 409


def test_account_username_must_be_free_among_users(client, admin):
    # "admin" is already a user name, so admin@... cannot get an account as a student.
    payload = new_student(email="admin@yachaytech.edu.ec", account_password="first-password-1")
    assert client.post("/api/students", headers=admin, json=payload).status_code == 409


def test_unknown_school_is_422(client, admin):
    r = client.post("/api/students", headers=admin, json=new_student(school_id=999))
    assert r.status_code == 422


def test_changing_email_also_changes_login(client, admin, world):
    s1 = world["students"]["s1"]
    r = client.patch(
        f"/api/students/{s1.student_id}",
        headers=admin,
        json={"email": "s1.new@yachaytech.edu.ec"},
    )
    assert r.status_code == 200
    login(client, "s1.new")


def test_search_students(client, admin):
    client.post("/api/students", headers=admin, json=new_student())
    found = client.get("/api/students", headers=admin, params={"q": "vera"}).json()
    assert [s["full_name"] for s in found] == ["Ana Vera"]


def test_delete_protects_academic_records(client, admin, world):
    s1 = world["students"]["s1"]  # has an account and a thesis
    assert client.delete(f"/api/students/{s1.student_id}", headers=admin).status_code == 409
    pc = world["profs"]["pC"]  # has an account
    assert client.delete(f"/api/professors/{pc.professor_id}", headers=admin).status_code == 409

    created = client.post("/api/students", headers=admin, json=new_student()).json()
    r = client.delete(f"/api/students/{created['student_id']}", headers=admin)
    assert r.status_code == 204


def test_professor_crud(client, admin):
    payload = {"first_name": "Rosa", "last_name": "Mena", "email": "rosa.mena@yachaytech.edu.ec"}
    created = client.post("/api/professors", headers=admin, json=payload)
    assert created.status_code == 201
    pid = created.json()["professor_id"]
    updated = client.patch(f"/api/professors/{pid}", headers=admin, json={"last_name": "Mena V."})
    assert updated.json()["full_name"] == "Rosa Mena V."
    assert (
        client.patch(f"/api/professors/{pid}", headers=admin, json={"first_name": None}).status_code
        == 422
    )


def test_periods(client, admin, world):
    bad = {"name": "2027-I", "start_date": "2027-07-01", "end_date": "2027-03-01"}
    assert client.post("/api/periods", headers=admin, json=bad).status_code == 422

    good = {"name": "2027-I", "start_date": "2027-03-01", "end_date": "2027-07-31"}
    assert client.post("/api/periods", headers=admin, json=good).status_code == 201
    assert client.post("/api/periods", headers=admin, json=good).status_code == 409

    # Everyone logged in can read periods; only admins create them.
    student = login(client, "s1")
    assert [p["name"] for p in client.get("/api/periods", headers=student).json()] == ["2027-I"]
    assert client.post("/api/periods", headers=student, json=good).status_code == 403


def test_schools(client, admin, school):
    student = login(client, "s1")
    assert len(client.get("/api/schools", headers=student).json()) == 1
    r = client.post("/api/schools", headers=admin, json={"code": "earth", "name": "Earth"})
    assert r.status_code == 201
    assert r.json()["code"] == "EARTH"
    r = client.post("/api/schools", headers=admin, json={"code": "MATH", "name": "Other"})
    assert r.status_code == 409
