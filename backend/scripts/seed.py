"""Load demo data for local development.

Usage (from backend/, after `alembic upgrade head`):
    .venv/Scripts/python.exe -m scripts.seed

All people below are fictitious. Every account uses DEV_PASSWORD, which is for local
development only and must never be used on a deployed environment.

The assignments reproduce the access-model example of the proposal (slide 9):
Prof. A is tutor of thesis 1 and reviewer of thesis 2; Prof. B is president of
thesis 1, tutor of thesis 2 and reviewer of thesis 3; Prof. C is reviewer of
thesis 1 and co-tutor of thesis 3.
"""

import datetime as dt
import sys
import unicodedata

from sqlalchemy import select

from app.core.security import hash_password
from app.db import SessionLocal
from app.models import (
    AcademicPeriod,
    Defense,
    DefenseModality,
    ObservationStatus,
    PlagiarismCheck,
    Professor,
    RequirementStatus,
    RequirementType,
    ReviewerAssignment,
    ReviewerRole,
    ReviewObservation,
    Room,
    School,
    SimilarityVerdict,
    Student,
    StudentRequirement,
    Thesis,
    ThesisStatus,
    ThesisStatusHistory,
    TutorAssignment,
    TutorRole,
    User,
    UserRole,
)
from app.schemas.users import username_from_email

DEV_PASSWORD = "123"
DOMAIN = "yachaytech.edu.ec"

# School codes from the catalog that migration 0004 loads.
MATH, PHYS, BIO, CHEM = "MATH", "PHYS", "BIO", "CHEM"

PROFESSORS = [  # key, first, last, school
    ("A", "Andrea", "Benítez", MATH),
    ("B", "Carlos", "Mendoza", MATH),
    ("C", "Lucía", "Paredes", PHYS),
    ("D", "Jorge", "Salazar", MATH),
    ("E", "Sofía", "Andrade", BIO),
]

STUDENTS = [  # key, first, last, school
    ("s1", "Daniela", "Torres", MATH),
    ("s2", "Mateo", "Guerrero", MATH),
    ("s3", "Valeria", "Castillo", PHYS),
    ("s4", "Diego", "Morales", BIO),
    ("s5", "Camila", "Ortiz", CHEM),  # no thesis yet
    ("s6", "Andrés", "Vega", MATH),
    ("s7", "Paula", "Ríos", PHYS),
]

ORDERED_FLOW = [
    ThesisStatus.PROPOSED,
    ThesisStatus.TOPIC_APPROVED,
    ThesisStatus.THESIS_I,
    ThesisStatus.THESIS_II,
    ThesisStatus.IN_REVIEW,
    ThesisStatus.READY_FOR_DEFENSE,
    ThesisStatus.DEFENDED,
]

THESES = [
    {
        "student": "s1",
        "title": "Graph neural networks for predicting student dropout in Ecuadorian universities",
        "status": ThesisStatus.IN_REVIEW,
        "tutors": [("A", TutorRole.TUTOR)],
        "reviewers": [
            ("B", ReviewerRole.PRESIDENT),
            ("C", ReviewerRole.COMMITTEE),
            ("D", ReviewerRole.COMMITTEE),
        ],
    },
    {
        "student": "s2",
        "title": "A verified scheduler for university defense rooms using constraint programming",
        "status": ThesisStatus.THESIS_II,
        "tutors": [("B", TutorRole.TUTOR)],
        "reviewers": [
            ("A", ReviewerRole.PRESIDENT),
            ("D", ReviewerRole.COMMITTEE),
            ("E", ReviewerRole.COMMITTEE),
        ],
    },
    {
        "student": "s3",
        "title": "Optical properties of graphene quantum dots synthesized from Andean biomass",
        "status": ThesisStatus.THESIS_I,
        "tutors": [("D", TutorRole.TUTOR), ("C", TutorRole.CO_TUTOR)],
        "reviewers": [("B", ReviewerRole.PRESIDENT), ("E", ReviewerRole.COMMITTEE)],
    },
    {
        "student": "s4",
        "title": "Microbial diversity of hot springs in the Imbabura province",
        "status": ThesisStatus.PROPOSED,
        "tutors": [("E", TutorRole.TUTOR)],
        "reviewers": [],
    },
    # Sprint 5: one thesis waiting for its defense and one already defended.
    {
        "student": "s6",
        "title": "Formal verification of smart contracts for public procurement",
        "status": ThesisStatus.READY_FOR_DEFENSE,
        "tutors": [("A", TutorRole.TUTOR)],
        "reviewers": [
            ("C", ReviewerRole.PRESIDENT),
            ("D", ReviewerRole.COMMITTEE),
            ("E", ReviewerRole.COMMITTEE),
        ],
    },
    {
        "student": "s7",
        "title": "Thin-film perovskite solar cells under high-altitude irradiance",
        "status": ThesisStatus.DEFENDED,
        "tutors": [("C", TutorRole.TUTOR)],
        "reviewers": [
            ("A", ReviewerRole.PRESIDENT),
            ("B", ReviewerRole.COMMITTEE),
            ("D", ReviewerRole.COMMITTEE),
        ],
    },
]

DEFENDED_AT = dt.datetime(2026, 10, 15, 11, 30)

ROOMS = [  # name, building, capacity
    ("Auditorium A", "Main Building", 120),
    ("Room 204", "Main Building", 40),
    ("Seminar Room 1", "Science Building", 30),
]


def ascii_lower(text: str) -> str:
    """'Andrés Ríos' -> 'andres rios': e-mail addresses without accents."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def email_for(first: str, last: str) -> str:
    return f"{ascii_lower(first)}.{ascii_lower(last)}@{DOMAIN}"


def main() -> None:
    db = SessionLocal()
    if db.scalars(select(User)).first() is not None:
        sys.exit(
            "The database already has users. To start over run:\n"
            "  alembic downgrade base && alembic upgrade head"
        )

    schools = {s.code: s for s in db.scalars(select(School))}
    password_hash = hash_password(DEV_PASSWORD)  # hash once: bcrypt is slow on purpose
    admin = User(username="admin", password_hash=password_hash, role=UserRole.ADMIN)
    db.add(admin)

    periods = [
        AcademicPeriod(
            name="2026-I", start_date=dt.date(2026, 3, 2), end_date=dt.date(2026, 7, 31)
        ),
        AcademicPeriod(
            name="2026-II", start_date=dt.date(2026, 9, 1), end_date=dt.date(2027, 1, 29)
        ),
    ]
    db.add_all(periods)

    professors: dict[str, Professor] = {}
    for i, (key, first, last, school) in enumerate(PROFESSORS, start=1):
        prof = Professor(
            first_name=first,
            last_name=last,
            school=schools[school],
            institution="Yachay Tech",
            email=email_for(first, last),
            national_id=f"10000000{i:02d}",
        )
        professors[key] = prof
        db.add(prof)
        db.add(
            User(
                username=username_from_email(prof.email),
                password_hash=password_hash,
                role=UserRole.PROFESSOR,
                professor=prof,
            )
        )

    students: dict[str, Student] = {}
    for i, (key, first, last, school) in enumerate(STUDENTS, start=1):
        student = Student(
            first_name=first,
            last_name=last,
            school=schools[school],
            institution="Yachay Tech",
            email=email_for(first, last),
            national_id=f"17000000{i:02d}",
        )
        students[key] = student
        db.add(student)
        db.add(
            User(
                username=username_from_email(student.email),
                password_hash=password_hash,
                role=UserRole.STUDENT,
                student=student,
            )
        )
    db.flush()

    start = dt.datetime(2026, 3, 9, 10, 0)
    for spec in THESES:
        thesis = Thesis(
            title=spec["title"],
            status=spec["status"],
            student=students[spec["student"]],
            periods=periods,
            abstract="Demo thesis created by the seed script.",
        )
        db.add(thesis)
        for key, role in spec["tutors"]:
            thesis.tutors.append(TutorAssignment(professor=professors[key], role=role))
        for key, role in spec["reviewers"]:
            db.add(ReviewerAssignment(thesis=thesis, professor=professors[key], role=role))

        # Audit trail consistent with the current status.
        previous = None
        for step, status in enumerate(ORDERED_FLOW[: ORDERED_FLOW.index(spec["status"]) + 1]):
            defended = status == ThesisStatus.DEFENDED
            db.add(
                ThesisStatusHistory(
                    thesis=thesis,
                    from_status=previous,
                    to_status=status,
                    author=admin,
                    # The defended thesis closes when its last jury grade arrives.
                    changed_at=DEFENDED_AT if defended else start + dt.timedelta(weeks=5 * step),
                    comment="Final grade 9.00 (passed)" if defended else "Seed data",
                )
            )
            previous = status

    # Committee review of thesis 1: one observation in each state of the cycle, and the
    # president has already approved (their only observation is resolved).
    db.flush()
    t1 = students["s1"].thesis
    reviewed = dt.datetime(2026, 10, 20, 9, 0)
    db.add_all(
        [
            ReviewObservation(
                thesis_id=t1.thesis_id,
                professor_id=professors["B"].professor_id,
                text="Section 2 should compare against at least one non-graph baseline.",
                status=ObservationStatus.RESOLVED,
                response="Added logistic regression and random forest baselines (Table 3).",
                responded_at=reviewed + dt.timedelta(days=4),
                resolved_at=reviewed + dt.timedelta(days=6),
            ),
            ReviewObservation(
                thesis_id=t1.thesis_id,
                professor_id=professors["C"].professor_id,
                text="Report confidence intervals for the dropout prediction metrics.",
                status=ObservationStatus.ADDRESSED,
                response="Bootstrap 95% intervals added to Table 4.",
                responded_at=reviewed + dt.timedelta(days=5),
            ),
            ReviewObservation(
                thesis_id=t1.thesis_id,
                professor_id=professors["D"].professor_id,
                text="Describe how personal data was anonymized before training.",
            ),
        ]
    )
    for reviewer in t1.reviewers:
        if reviewer.professor_id == professors["B"].professor_id:
            reviewer.approved_at = reviewed + dt.timedelta(days=6, hours=2)

    # Pre-defense gate inputs (Sprint 4). Thesis 1: similarity accepted, all requirements
    # certified except the foreign language one. Thesis 2: a first check above the
    # threshold. Daniela and Mateo have part of their administrative requirements done.
    t2 = students["s2"].thesis
    db.add_all(
        [
            PlagiarismCheck(
                thesis_id=t1.thesis_id,
                similarity_percentage=6.4,
                checked_at=reviewed,
                tool="Turnitin",
                threshold_applied=10,
                verdict=SimilarityVerdict.ACCEPTED,
                recorded_by=admin.user_id,
            ),
            PlagiarismCheck(
                thesis_id=t2.thesis_id,
                similarity_percentage=13.8,
                checked_at=reviewed + dt.timedelta(days=3),
                tool="Turnitin",
                threshold_applied=10,
                verdict=SimilarityVerdict.REJECTED,
                recorded_by=admin.user_id,
                notes="Chapter 2 reuses text from a seminar paper without citation.",
            ),
        ]
    )
    types = {t.code: t for t in db.scalars(select(RequirementType))}
    certified = {
        "s1": ["CURRICULUM", "INTERNSHIP", "COMMUNITY", "FINANCIAL", "LIBRARY"],
        "s2": ["CURRICULUM", "INTERNSHIP"],
    }
    for key, codes in certified.items():
        for code in codes:
            db.add(
                StudentRequirement(
                    student_id=students[key].student_id,
                    requirement_type_id=types[code].requirement_type_id,
                    status=RequirementStatus.CERTIFIED,
                    certified_by=admin.user_id,
                    certified_at=reviewed - dt.timedelta(days=30),
                )
            )

    # Sprint 5: rooms, a scheduled defense and a graded one. Both theses passed every
    # step before the defense: approvals, similarity and all active requirements.
    rooms = [Room(name=n, building=b, capacity=c) for n, b, c in ROOMS]
    db.add_all(rooms)
    db.flush()
    t6, t7 = students["s6"].thesis, students["s7"].thesis
    for thesis, checked in ((t6, reviewed), (t7, dt.datetime(2026, 9, 18, 9, 0))):
        for reviewer in thesis.reviewers:
            reviewer.approved_at = checked
        db.add(
            PlagiarismCheck(
                thesis_id=thesis.thesis_id,
                similarity_percentage=4.9,
                checked_at=checked,
                tool="Turnitin",
                threshold_applied=10,
                verdict=SimilarityVerdict.ACCEPTED,
                recorded_by=admin.user_id,
            )
        )
        for rtype in types.values():
            if rtype.is_active:
                db.add(
                    StudentRequirement(
                        student_id=thesis.student_id,
                        requirement_type_id=rtype.requirement_type_id,
                        status=RequirementStatus.CERTIFIED,
                        certified_by=admin.user_id,
                        certified_at=checked - dt.timedelta(days=10),
                    )
                )
    next_week = dt.datetime.combine(dt.date.today() + dt.timedelta(days=5), dt.time(10, 0))
    db.add(
        Defense(
            thesis_id=t6.thesis_id,
            scheduled_at=next_week,
            duration_minutes=90,
            modality=DefenseModality.IN_PERSON,
            room_id=rooms[0].room_id,
        )
    )
    grades = {"A": 9.0, "B": 8.5, "D": 9.5}
    for reviewer in t7.reviewers:
        for key, value in grades.items():
            if reviewer.professor_id == professors[key].professor_id:
                reviewer.grade = value
    db.add(
        Defense(
            thesis_id=t7.thesis_id,
            scheduled_at=DEFENDED_AT - dt.timedelta(minutes=90),
            duration_minutes=90,
            modality=DefenseModality.IN_PERSON,
            room_id=rooms[2].room_id,
            final_grade=9.0,
        )
    )

    db.commit()
    print(
        f"Seed complete: 1 admin, {len(PROFESSORS)} professors, {len(STUDENTS)} students, "
        f"{len(THESES)} theses. Password for every account: see DEV_PASSWORD in this file."
    )


if __name__ == "__main__":
    main()
