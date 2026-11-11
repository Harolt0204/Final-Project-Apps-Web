"""Check, against the real MySQL database, that the business rules enforced by the
schema actually reject invalid data. The unit tests run on SQLite, which cannot run the
MySQL trigger, so this script is the integration check for the database layer.

Usage (from backend/, after `alembic upgrade head` and `python -m scripts.seed`):
    .venv/Scripts/python.exe -m scripts.verify_db_rules

Every statement runs inside a transaction that is rolled back: no data is changed.
Exit code 0 when every rule holds, 1 otherwise. CI runs it after the migrations.
"""

import sys

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import engine

# MySQL error codes: duplicate key, FK violation, CHECK violation, trigger SIGNAL.
DUPLICATE, FOREIGN_KEY, CHECK, SIGNAL = 1062, 1452, 3819, 1644


def first(conn, sql: str):
    row = conn.execute(text(sql)).first()
    if row is None:
        sys.exit(f"Seed data missing for: {sql}")
    return row


def main() -> int:
    failures = 0
    with engine.connect() as conn:
        trans = conn.begin()
        # A thesis with a main tutor and a full committee, and a professor outside it.
        thesis_id, tutor_id = first(
            conn,
            "SELECT t.thesis_id, ta.professor_id FROM theses t "
            "JOIN tutor_assignments ta ON ta.thesis_id = t.thesis_id AND ta.role = 'Tutor' "
            "WHERE (SELECT COUNT(*) FROM reviewer_assignments r "
            "       WHERE r.thesis_id = t.thesis_id) = 3 LIMIT 1",
        )
        outsider = first(
            conn,
            "SELECT professor_id FROM professors WHERE professor_id NOT IN ("
            f"  SELECT professor_id FROM reviewer_assignments WHERE thesis_id = {thesis_id} "
            f"  UNION SELECT professor_id FROM tutor_assignments WHERE thesis_id = {thesis_id}"
            ") LIMIT 1",
        )[0]
        reviewer = first(
            conn,
            f"SELECT professor_id FROM reviewer_assignments WHERE thesis_id = {thesis_id} "
            "AND role = 'Committee' LIMIT 1",
        )[0]
        student_id = first(conn, "SELECT student_id FROM students LIMIT 1")[0]
        type_id = first(conn, "SELECT requirement_type_id FROM requirement_types LIMIT 1")[0]

        checks = [
            (
                "Only one main tutor per thesis (DEC-03)",
                DUPLICATE,
                f"INSERT INTO tutor_assignments (thesis_id, professor_id, role) "
                f"VALUES ({thesis_id}, {outsider}, 'Tutor')",
            ),
            (
                "At most 3 reviewers per thesis (DEC-04, trigger)",
                SIGNAL,
                f"INSERT INTO reviewer_assignments (thesis_id, professor_id) "
                f"VALUES ({thesis_id}, {outsider})",
            ),
            (
                "Exactly one president per thesis (DEC-05)",
                DUPLICATE,
                f"UPDATE reviewer_assignments SET role = 'President' "
                f"WHERE thesis_id = {thesis_id} AND professor_id = {reviewer}",
            ),
            (
                "Jury grades between 0 and 10",
                CHECK,
                f"UPDATE reviewer_assignments SET grade = 15 WHERE thesis_id = {thesis_id}",
            ),
            (
                "Only reviewers write observations (composite FK)",
                FOREIGN_KEY,
                f"INSERT INTO review_observations (thesis_id, professor_id, text) "
                f"VALUES ({thesis_id}, {tutor_id}, 'x')",
            ),
            (
                "Similarity verdict consistent with threshold",
                CHECK,
                "INSERT INTO plagiarism_checks (thesis_id, similarity_percentage, checked_at, "
                "tool, threshold_applied, verdict) "
                f"VALUES ({thesis_id}, 25, NOW(), 'x', 10, 'ACCEPTED')",
            ),
            (
                "A rejected requirement needs a note",
                CHECK,
                f"REPLACE INTO student_requirements (student_id, requirement_type_id, status, "
                f"certified_at) VALUES ({student_id}, {type_id}, 'REJECTED', NOW())",
            ),
            (
                "User account linked to the person of its role",
                CHECK,
                f"INSERT INTO users (email, password_hash, role, student_id) "
                f"VALUES ('check@example.org', 'x', 'admin', {student_id})",
            ),
            (
                "In-person defense needs a room",
                CHECK,
                "INSERT INTO defenses (thesis_id, scheduled_at, modality) "
                "VALUES ((SELECT MAX(thesis_id) FROM theses) + 1000, NOW(), 'In-person')",
            ),
            (
                "Academic period starts before it ends",
                CHECK,
                "INSERT INTO academic_periods (name, start_date, end_date) "
                "VALUES ('check', '2027-02-01', '2027-01-01')",
            ),
        ]

        for label, expected, sql in checks:
            savepoint = conn.begin_nested()
            try:
                conn.execute(text(sql))
                outcome, ok = "ACCEPTED (rule not enforced!)", False
            except DBAPIError as exc:
                code = exc.orig.args[0] if exc.orig is not None else None
                ok = code == expected
                outcome = f"rejected ({code})" if ok else f"unexpected error {code}"
            savepoint.rollback()
            failures += not ok
            print(f"[{'OK ' if ok else 'FAIL'}] {label}: {outcome}")

        trans.rollback()

    print(f"\n{len(checks) - failures}/{len(checks)} database rules enforced")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
