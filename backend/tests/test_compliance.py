"""Sprint 4: similarity checks, administrative requirements and the pre-defense gate."""

import datetime as dt

import pytest

from app.models import (
    PlagiarismCheck,
    RequirementType,
    ReviewerAssignment,
    SimilarityVerdict,
    SystemSetting,
    ThesisStatus,
)
from tests.conftest import login

ADMIN = "admin@yachaytech.edu.ec"


def email(key: str) -> str:
    return f"{key}@yachaytech.edu.ec"


@pytest.fixture
def admin(client, world):
    return login(client, ADMIN)


@pytest.fixture
def threshold(db):
    db.add(SystemSetting(setting_key="similarity_max_percentage", value="10.00"))
    db.commit()


@pytest.fixture
def types(db):
    rows = [
        RequirementType(code="INTERNSHIP", name="Pre-professional internships", sort_order=1),
        RequirementType(code="LANGUAGE", name="Foreign language proficiency", sort_order=2),
        RequirementType(code="LAB", name="Laboratory clearance", is_active=False, sort_order=3),
    ]
    db.add_all(rows)
    db.commit()
    return {r.code: r for r in rows}


def checks_url(thesis_id: int) -> str:
    return f"/api/theses/{thesis_id}/similarity-checks"


# ------------------------------------------------------------------------- similarity


def test_similarity_verdict_follows_threshold(client, admin, world, db, threshold):
    t1 = world["t1"]
    t1.status = ThesisStatus.THESIS_II
    db.commit()

    r = client.post(
        checks_url(t1.thesis_id),
        headers=admin,
        json={"similarity_percentage": "14.3", "tool": "Turnitin"},
    )
    assert r.status_code == 201, r.text
    first = r.json()
    assert (first["verdict"], first["threshold_applied"]) == ("REJECTED", "10.00")
    assert first["recorded_by_name"] == "Administrator"

    # Raising the threshold does not rewrite past verdicts.
    assert (
        client.put(
            "/api/settings/similarity_max_percentage", headers=admin, json={"value": "15"}
        ).json()["value"]
        == "15.00"
    )
    r = client.post(
        checks_url(t1.thesis_id),
        headers=admin,
        json={
            "similarity_percentage": "14.3",
            "tool": "Turnitin",
            "report_url": "https://drive.example.org/report.pdf",
        },
    )
    assert r.json()["verdict"] == "ACCEPTED"

    # Both checks stay in the history, visible to the student.
    student = login(client, email("s1"))
    body = client.get(checks_url(t1.thesis_id), headers=student).json()
    assert body["threshold"] == "15.00"
    assert [c["verdict"] for c in body["checks"]] == ["REJECTED", "ACCEPTED"]


def test_similarity_rules(client, admin, world, db, threshold):
    t1 = world["t1"]
    payload = {"similarity_percentage": "5", "tool": "Turnitin"}
    # Not before Thesis II.
    assert client.post(checks_url(t1.thesis_id), headers=admin, json=payload).status_code == 409

    t1.status = ThesisStatus.IN_REVIEW
    db.commit()
    tutor = login(client, email("pA"))
    assert client.post(checks_url(t1.thesis_id), headers=tutor, json=payload).status_code == 403
    bad = {"similarity_percentage": "120", "tool": "Turnitin"}
    assert client.post(checks_url(t1.thesis_id), headers=admin, json=bad).status_code == 422
    future = {**payload, "checked_at": (dt.datetime.now() + dt.timedelta(days=2)).isoformat()}
    assert client.post(checks_url(t1.thesis_id), headers=admin, json=future).status_code == 422
    outsider = login(client, email("pC"))
    assert client.get(checks_url(t1.thesis_id), headers=outsider).status_code == 404


def test_db_keeps_verdict_consistent(db, world):
    from sqlalchemy.exc import IntegrityError

    db.add(
        PlagiarismCheck(
            thesis_id=world["t1"].thesis_id,
            similarity_percentage=30,
            checked_at=dt.datetime.now(),
            tool="x",
            threshold_applied=10,
            verdict=SimilarityVerdict.ACCEPTED,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_settings_validation(client, admin, world, threshold):
    url = "/api/settings/similarity_max_percentage"
    assert client.put(url, headers=admin, json={"value": "abc"}).status_code == 422
    assert client.put(url, headers=admin, json={"value": "150"}).status_code == 422
    assert (
        client.put("/api/settings/unknown", headers=admin, json={"value": "1"}).status_code == 404
    )
    student = login(client, email("s1"))
    assert client.put(url, headers=student, json={"value": "50"}).status_code == 403


# ----------------------------------------------------------------------- requirements


def req_url(student_id: int, type_id: int | None = None) -> str:
    base = f"/api/students/{student_id}/requirements"
    return f"{base}/{type_id}" if type_id else base


def test_checklist_and_certification(client, admin, world, types):
    s1 = world["students"]["s1"].student_id
    body = client.get(req_url(s1), headers=admin).json()
    # Inactive types are not part of the checklist.
    assert [i["requirement_type"]["code"] for i in body["items"]] == ["INTERNSHIP", "LANGUAGE"]
    assert {i["status"] for i in body["items"]} == {"PENDING"}
    assert body["complete"] is False

    internship = types["INTERNSHIP"].requirement_type_id
    r = client.put(
        req_url(s1, internship),
        headers=admin,
        json={"status": "CERTIFIED", "evidence_url": "https://example.org/cert.pdf"},
    )
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert (item["status"], item["certified_by_name"]) == ("CERTIFIED", "Administrator")

    # A rejection must explain why.
    language = types["LANGUAGE"].requirement_type_id
    bad = client.put(req_url(s1, language), headers=admin, json={"status": "REJECTED"})
    assert bad.status_code == 422
    r = client.put(
        req_url(s1, language),
        headers=admin,
        json={"status": "REJECTED", "notes": "Certificate expired"},
    )
    assert r.json()["items"][1]["status"] == "REJECTED"

    # Back to pending.
    r = client.delete(req_url(s1, language), headers=admin)
    assert r.json()["items"][1]["status"] == "PENDING"


def test_who_sees_requirements(client, admin, world, types):
    s1 = world["students"]["s1"].student_id
    t1 = world["t1"].thesis_id
    assert client.get(req_url(s1), headers=login(client, email("s1"))).status_code == 200
    assert client.get(req_url(s1), headers=login(client, email("s2"))).status_code == 404
    # The tutor sees them through the thesis; an outsider does not.
    tutor = login(client, email("pA"))
    assert client.get(f"/api/theses/{t1}/requirements", headers=tutor).status_code == 200
    outsider = login(client, email("pC"))
    assert client.get(f"/api/theses/{t1}/requirements", headers=outsider).status_code == 404
    # Only admins certify.
    internship = types["INTERNSHIP"].requirement_type_id
    r = client.put(req_url(s1, internship), headers=tutor, json={"status": "CERTIFIED"})
    assert r.status_code == 403


def test_requirement_type_catalog(client, admin, world, types):
    r = client.post(
        "/api/requirement-types",
        headers=admin,
        json={"code": "thesis_fee", "name": "Graduation fee paid", "sort_order": 9},
    )
    assert r.status_code == 201
    assert r.json()["code"] == "THESIS_FEE"
    dup = client.post(
        "/api/requirement-types",
        headers=admin,
        json={"code": "OTHER", "name": "Graduation fee paid"},
    )
    assert dup.status_code == 409

    lab = types["LAB"].requirement_type_id
    client.patch(f"/api/requirement-types/{lab}", headers=admin, json={"is_active": True})
    student = login(client, email("s1"))
    codes = [t["code"] for t in client.get("/api/requirement-types", headers=student).json()]
    assert codes == ["INTERNSHIP", "LANGUAGE", "LAB", "THESIS_FEE"]


# --------------------------------------------------------------------- pre-defense gate


def test_gate_blocks_until_similarity_and_requirements(client, admin, world, db, types, threshold):
    """Committee and reviews are complete; only Sprint 4 prerequisites are missing."""
    from app.models import Professor

    t1 = world["t1"]
    t1.status = ThesisStatus.IN_REVIEW
    extra = Professor(first_name="pD", last_name="Prof", email=email("pD"))
    db.add_all(
        [
            extra,
            ReviewerAssignment(thesis=t1, professor=world["profs"]["pC"]),
            ReviewerAssignment(thesis=t1, professor=extra),
        ]
    )
    db.flush()
    for reviewer in t1.reviewers:
        reviewer.approved_at = dt.datetime.now()
    db.commit()

    def blockers():
        body = client.get(f"/api/theses/{t1.thesis_id}/workflow", headers=admin).json()
        ready = next(o for o in body["options"] if o["to_status"] == "READY_FOR_DEFENSE")
        return ready["blockers"]

    assert blockers() == [
        "No similarity check has been recorded",
        "2 administrative requirement(s) pending: Pre-professional internships, "
        "Foreign language proficiency",
    ]

    client.post(
        checks_url(t1.thesis_id),
        headers=admin,
        json={"similarity_percentage": "22", "tool": "Turnitin"},
    )
    assert blockers()[0] == "The latest similarity check (22.00%) exceeds the 10.00% threshold"

    client.post(
        checks_url(t1.thesis_id),
        headers=admin,
        json={"similarity_percentage": "8", "tool": "Turnitin"},
    )
    s1 = world["students"]["s1"].student_id
    for rtype in (types["INTERNSHIP"], types["LANGUAGE"]):
        client.put(
            req_url(s1, rtype.requirement_type_id), headers=admin, json={"status": "CERTIFIED"}
        )
    assert blockers() == []

    r = client.post(
        f"/api/theses/{t1.thesis_id}/status", headers=admin, json={"to_status": "READY_FOR_DEFENSE"}
    )
    assert r.status_code == 200
