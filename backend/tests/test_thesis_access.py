"""Per-thesis authorization: users only see theses they take part in."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import ReviewerAssignment, ReviewerRole, TutorAssignment, TutorRole
from tests.conftest import login


def titles(client, email):
    response = client.get("/api/theses", headers=login(client, email))
    assert response.status_code == 200
    return sorted(t["title"] for t in response.json())


def test_admin_sees_every_thesis(client, world):
    assert titles(client, "admin@yachaytech.edu.ec") == ["Thesis one", "Thesis two"]


def test_professor_sees_only_assigned_theses(client, world):
    assert titles(client, "pA@yachaytech.edu.ec") == ["Thesis one", "Thesis two"]
    assert titles(client, "pC@yachaytech.edu.ec") == []


def test_student_sees_only_own_thesis(client, world):
    assert titles(client, "s1@yachaytech.edu.ec") == ["Thesis one"]
    assert titles(client, "s3@yachaytech.edu.ec") == []


def test_roles_are_derived_per_thesis(client, world):
    response = client.get("/api/theses", headers=login(client, "pB@yachaytech.edu.ec"))
    roles = {t["title"]: t["my_roles"] for t in response.json()}
    assert roles == {"Thesis one": ["President"], "Thesis two": ["Tutor"]}


def test_outsiders_get_404_not_403(client, world):
    t1 = world["t1"].thesis_id
    assert (
        client.get(f"/api/theses/{t1}", headers=login(client, "pC@yachaytech.edu.ec")).status_code
        == 404
    )
    assert (
        client.get(f"/api/theses/{t1}", headers=login(client, "s2@yachaytech.edu.ec")).status_code
        == 404
    )

    detail = client.get(f"/api/theses/{t1}", headers=login(client, "s1@yachaytech.edu.ec"))
    assert detail.status_code == 200
    body = detail.json()
    assert body["my_roles"] == ["Student"]
    assert body["tutors"][0]["role"] == "Tutor"
    assert body["status"] == "PROPOSED"


# --- Rules enforced by the database itself (DEC-03, DEC-05, I-2) -----------------------


def test_db_rejects_second_main_tutor(db, world):
    db.add(
        TutorAssignment(thesis=world["t1"], professor=world["profs"]["pC"], role=TutorRole.TUTOR)
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_db_rejects_same_professor_as_tutor_and_cotutor(db, world):
    db.add(
        TutorAssignment(thesis=world["t1"], professor=world["profs"]["pA"], role=TutorRole.CO_TUTOR)
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_db_rejects_second_president(db, world):
    db.add(
        ReviewerAssignment(
            thesis=world["t1"], professor=world["profs"]["pC"], role=ReviewerRole.PRESIDENT
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_db_rejects_grade_out_of_range(db, world):
    db.add(
        ReviewerAssignment(
            thesis=world["t1"],
            professor=world["profs"]["pC"],
            role=ReviewerRole.COMMITTEE,
            grade=15,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
