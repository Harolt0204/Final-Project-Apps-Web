"""Sprint 3: status workflow, reviewer committee and review observations."""

import pytest

from app.core.security import hash_password
from app.models import (
    Professor,
    ReviewerAssignment,
    ThesisStatus,
    ThesisStatusHistory,
    User,
    UserRole,
)
from tests.conftest import PASSWORD, login

ADMIN = "admin@yachaytech.edu.ec"


def email(key: str) -> str:
    return f"{key}@yachaytech.edu.ec"


@pytest.fixture
def admin(client, world):
    return login(client, ADMIN)


@pytest.fixture
def extra_profs(db, world):
    """pD and pE, with accounts, to complete committees."""
    profs = {}
    for key in ("pD", "pE"):
        prof = Professor(first_name=key, last_name="Prof", email=email(key))
        db.add(prof)
        db.add(
            User(
                email=prof.email,
                password_hash=hash_password(PASSWORD),
                role=UserRole.PROFESSOR,
                professor=prof,
            )
        )
        profs[key] = prof
    db.commit()
    return profs


@pytest.fixture
def in_review(db, world, extra_profs):
    """Thesis 1 under committee review: tutor pA; president pB; members pC and pD."""
    t1 = world["t1"]
    t1.status = ThesisStatus.IN_REVIEW
    db.add_all(
        [
            ReviewerAssignment(thesis=t1, professor=world["profs"]["pC"]),
            ReviewerAssignment(thesis=t1, professor=extra_profs["pD"]),
        ]
    )
    db.commit()
    return t1.thesis_id


def move(client, headers, thesis_id, to_status, comment=None):
    return client.post(
        f"/api/theses/{thesis_id}/status",
        headers=headers,
        json={"to_status": to_status, "comment": comment},
    )


# -------------------------------------------------------------------------- workflow


def test_admin_approves_topic_and_history_is_recorded(client, admin, world, db):
    t1 = world["t1"].thesis_id
    r = move(client, admin, t1, "TOPIC_APPROVED", "Approved in council session 12")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "TOPIC_APPROVED"

    row = db.query(ThesisStatusHistory).filter_by(thesis_id=t1).one()
    assert (row.from_status, row.to_status) == (ThesisStatus.PROPOSED, ThesisStatus.TOPIC_APPROVED)
    assert row.changed_by == world["users"]["admin"].user_id
    assert row.comment == "Approved in council session 12"


def test_topic_needs_a_main_tutor(client, admin, world):
    s3 = world["students"]["s3"].student_id
    created = client.post(
        "/api/theses", headers=admin, json={"title": "No tutor yet", "student_id": s3}
    ).json()
    r = move(client, admin, created["thesis_id"], "TOPIC_APPROVED")
    assert r.status_code == 409
    assert "tutor" in r.json()["detail"]


def test_invalid_transition_and_permissions(client, admin, world):
    t1 = world["t1"].thesis_id
    assert move(client, admin, t1, "DEFENDED").status_code == 409

    student = login(client, email("s1"))
    assert move(client, student, t1, "TOPIC_APPROVED").status_code == 403
    # A professor outside the thesis does not even see it.
    outsider = login(client, email("pC"))
    assert move(client, outsider, t1, "TOPIC_APPROVED").status_code == 404


def test_rejection_requires_a_comment(client, admin, world):
    t1 = world["t1"].thesis_id
    assert move(client, admin, t1, "REJECTED").status_code == 422
    r = move(client, admin, t1, "REJECTED", "Out of the program's scope")
    assert r.json()["status"] == "REJECTED"


def test_tutor_moves_thesis_i_to_ii_but_cannot_approve_topics(client, world, db):
    t1 = world["t1"]
    tutor = login(client, email("pA"))
    assert move(client, tutor, t1.thesis_id, "TOPIC_APPROVED").status_code == 403

    t1.status = ThesisStatus.THESIS_I
    db.commit()
    assert move(client, tutor, t1.thesis_id, "THESIS_II").status_code == 200


def test_review_needs_full_committee(client, admin, world, db, extra_profs):
    t1 = world["t1"]
    t1.status = ThesisStatus.THESIS_II
    db.commit()
    r = move(client, admin, t1.thesis_id, "IN_REVIEW")
    assert r.status_code == 409
    assert "3 reviewers (it has 1)" in r.json()["detail"]

    for key in ("pC", "pD"):
        prof = world["profs"].get(key) or extra_profs[key]
        assert (
            client.put(
                f"/api/theses/{t1.thesis_id}/reviewers/{prof.professor_id}", headers=admin, json={}
            ).status_code
            == 200
        )
    assert move(client, admin, t1.thesis_id, "IN_REVIEW").status_code == 200


def test_workflow_shows_what_is_missing(client, world):
    t1 = world["t1"].thesis_id
    student = login(client, email("s1"))
    body = client.get(f"/api/theses/{t1}/workflow", headers=student).json()
    assert body["status"] == "PROPOSED"
    options = {o["to_status"]: o for o in body["options"]}
    assert set(options) == {"TOPIC_APPROVED", "REJECTED"}
    assert options["TOPIC_APPROVED"]["blockers"] == []  # tutor pA is assigned
    assert options["TOPIC_APPROVED"]["can_perform"] is False  # students cannot approve


# ------------------------------------------------------------------------- committee


def put_reviewer(client, headers, thesis_id, prof, role="Committee"):
    return client.put(
        f"/api/theses/{thesis_id}/reviewers/{prof.professor_id}",
        headers=headers,
        json={"role": role},
    )


def test_committee_rules(client, admin, world, db, extra_profs):
    t1 = world["t1"]
    profs = world["profs"]
    # Not before the topic is approved.
    assert put_reviewer(client, admin, t1.thesis_id, profs["pC"]).status_code == 409

    t1.status = ThesisStatus.THESIS_II
    db.commit()
    # The tutor (pA) cannot review their own student's thesis.
    assert put_reviewer(client, admin, t1.thesis_id, profs["pA"]).status_code == 409
    # Only one president: pB already is.
    assert put_reviewer(client, admin, t1.thesis_id, profs["pC"], "President").status_code == 409

    assert put_reviewer(client, admin, t1.thesis_id, profs["pC"]).status_code == 200
    assert put_reviewer(client, admin, t1.thesis_id, extra_profs["pD"]).status_code == 200
    r = put_reviewer(client, admin, t1.thesis_id, extra_profs["pE"])
    assert r.status_code == 409
    assert "3 reviewers" in r.json()["detail"]

    # Swap the president: demote pB, then promote pC.
    assert put_reviewer(client, admin, t1.thesis_id, profs["pB"], "Committee").status_code == 200
    r = put_reviewer(client, admin, t1.thesis_id, profs["pC"], "President")
    roles = {x["professor"]["full_name"]: x["role"] for x in r.json()["reviewers"]}
    assert roles == {"pB Prof": "Committee", "pC Prof": "President", "pD Prof": "Committee"}

    # Only admins manage the committee.
    tutor = login(client, email("pA"))
    assert put_reviewer(client, tutor, t1.thesis_id, extra_profs["pE"]).status_code == 403


# ---------------------------------------------------------------------- observations


def test_observation_cycle(client, world, in_review):
    president = login(client, email("pB"))
    member = login(client, email("pC"))
    student = login(client, email("s1"))
    base = f"/api/theses/{in_review}/observations"

    # The tutor is not a reviewer and cannot write observations.
    tutor = login(client, email("pA"))
    assert client.post(base, headers=tutor, json={"text": "x"}).status_code == 403

    r = client.post(base, headers=president, json={"text": "Clarify the dataset split."})
    assert r.status_code == 201
    obs = r.json()
    assert (obs["status"], obs["author_name"]) == ("OPEN", "pB Prof")
    oid = obs["observation_id"]

    # Only the author resolves, and only after the student responds.
    assert client.post(f"{base}/{oid}/resolve", headers=president).status_code == 409
    other_student = login(client, email("s2"))
    r = client.post(f"{base}/{oid}/response", headers=other_student, json={"response": "x"})
    assert r.status_code == 404
    r = client.post(f"{base}/{oid}/response", headers=student, json={"response": "Done, see 3.2"})
    assert r.json()["status"] == "ADDRESSED"
    assert client.post(f"{base}/{oid}/resolve", headers=member).status_code == 403

    # Reopen, answer again, resolve.
    assert client.post(f"{base}/{oid}/reopen", headers=president).json()["status"] == "OPEN"
    client.post(f"{base}/{oid}/response", headers=student, json={"response": "Now with a table"})
    r = client.post(f"{base}/{oid}/resolve", headers=president)
    assert r.json()["status"] == "RESOLVED"
    assert r.json()["resolved_at"] is not None

    listed = client.get(base, headers=student).json()
    assert [o["status"] for o in listed] == ["RESOLVED"]


def test_ready_for_defense_gate(client, admin, world, in_review):
    president = login(client, email("pB"))
    student = login(client, email("s1"))
    base = f"/api/theses/{in_review}"
    oid = client.post(
        f"{base}/observations", headers=president, json={"text": "Fix figure 4"}
    ).json()["observation_id"]

    # Cannot approve with a pending observation of their own.
    assert client.put(f"{base}/approval", headers=president).status_code == 409

    r = move(client, admin, in_review, "READY_FOR_DEFENSE")
    assert r.status_code == 409
    assert "3 reviewer(s) have not approved" in r.json()["detail"]
    assert "1 review observation(s)" in r.json()["detail"]

    client.post(f"{base}/observations/{oid}/response", headers=student, json={"response": "Ok"})
    client.post(f"{base}/observations/{oid}/resolve", headers=president)
    for key in ("pB", "pC", "pD"):
        r = client.put(f"{base}/approval", headers=login(client, email(key)))
        assert r.status_code == 200, r.text

    # Sprint 4: the gate also needs an accepted similarity check.
    r = move(client, admin, in_review, "READY_FOR_DEFENSE")
    assert "No similarity check" in r.json()["detail"]
    check = {"similarity_percentage": "4.5", "tool": "Turnitin"}
    client.post(f"{base}/similarity-checks", headers=admin, json=check)

    assert move(client, admin, in_review, "READY_FOR_DEFENSE").status_code == 200


def test_return_for_changes_clears_approvals(client, admin, world, in_review):
    base = f"/api/theses/{in_review}"
    client.put(f"{base}/approval", headers=login(client, email("pC")))
    r = move(client, admin, in_review, "THESIS_II", "Major revision of chapter 4")
    assert r.status_code == 200
    assert all(rv["approved_at"] is None for rv in r.json()["reviewers"])


def test_reviewer_with_observations_cannot_be_removed(client, admin, world, in_review):
    member = login(client, email("pC"))
    client.post(f"/api/theses/{in_review}/observations", headers=member, json={"text": "Typo"})
    pc = world["profs"]["pC"].professor_id
    r = client.delete(f"/api/theses/{in_review}/reviewers/{pc}", headers=admin)
    assert r.status_code == 409
