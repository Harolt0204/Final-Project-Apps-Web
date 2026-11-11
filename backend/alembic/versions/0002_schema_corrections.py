"""Corrections to the inherited schema (documentation.md, section 8.1).

- DEC-03  tutor_assignments: PK (thesis_id, role) + UNIQUE (thesis_id, professor_id).
- DEC-04/05 reviewer_assignments: role ENUM NOT NULL, individual grade 0-10,
          exactly one President (unique generated column), trigger: max 3 reviewers.
- DEC-08  created_at / updated_at on every table.
- D-5     theses.status + stage unified into one ENUM state machine (default decision).
- I-2     CHECK ranges for grades, similarity and period dates.
- I-3     explicit ON DELETE behaviour on every foreign key.
- I-7/I-8 professors.email NOT NULL UNIQUE; national_id on students and professors.

Existing rows must already satisfy the new constraints (for example, no thesis with two
main tutors); otherwise the migration fails and the data must be cleaned first.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALL_TABLES = [
    "students",
    "professors",
    "academic_periods",
    "theses",
    "thesis_period",
    "tutor_assignments",
    "reviewer_assignments",
    "requirements",
    "plagiarism_checks",
    "defenses",
]

# (table, column, referenced table, referenced column, legacy name, new name, on delete)
FOREIGN_KEYS = [
    (
        "theses",
        "student_id",
        "students",
        "student_id",
        "theses_ibfk_1",
        "fk_theses_student_id",
        "RESTRICT",
    ),
    (
        "thesis_period",
        "thesis_id",
        "theses",
        "thesis_id",
        "thesis_period_ibfk_1",
        "fk_thesis_period_thesis_id",
        "CASCADE",
    ),
    (
        "thesis_period",
        "period_id",
        "academic_periods",
        "period_id",
        "thesis_period_ibfk_2",
        "fk_thesis_period_period_id",
        "RESTRICT",
    ),
    (
        "tutor_assignments",
        "thesis_id",
        "theses",
        "thesis_id",
        "tutor_assignments_ibfk_1",
        "fk_tutor_assignments_thesis_id",
        "CASCADE",
    ),
    (
        "tutor_assignments",
        "professor_id",
        "professors",
        "professor_id",
        "tutor_assignments_ibfk_2",
        "fk_tutor_assignments_professor_id",
        "RESTRICT",
    ),
    # thesis_id is the base column of a STORED generated column: MySQL forbids CASCADE.
    (
        "reviewer_assignments",
        "thesis_id",
        "theses",
        "thesis_id",
        "reviewer_assignments_ibfk_1",
        "fk_reviewer_assignments_thesis_id",
        "RESTRICT",
    ),
    (
        "reviewer_assignments",
        "professor_id",
        "professors",
        "professor_id",
        "reviewer_assignments_ibfk_2",
        "fk_reviewer_assignments_professor_id",
        "RESTRICT",
    ),
    (
        "requirements",
        "thesis_id",
        "theses",
        "thesis_id",
        "requirements_ibfk_1",
        "fk_requirements_thesis_id",
        "CASCADE",
    ),
    (
        "plagiarism_checks",
        "thesis_id",
        "theses",
        "thesis_id",
        "plagiarism_checks_ibfk_1",
        "fk_plagiarism_checks_thesis_id",
        "CASCADE",
    ),
    (
        "defenses",
        "thesis_id",
        "theses",
        "thesis_id",
        "defenses_ibfk_1",
        "fk_defenses_thesis_id",
        "CASCADE",
    ),
]

THESIS_STATUSES = (
    "'PROPOSED','TOPIC_APPROVED','THESIS_I','THESIS_II',"
    "'IN_REVIEW','READY_FOR_DEFENSE','DEFENDED','REJECTED'"
)

MAX3_TRIGGER = """
CREATE TRIGGER trg_reviewer_assignments_max3
BEFORE INSERT ON reviewer_assignments
FOR EACH ROW
BEGIN
  IF (SELECT COUNT(*) FROM reviewer_assignments WHERE thesis_id = NEW.thesis_id) >= 3 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'A thesis cannot have more than 3 reviewers';
  END IF;
END
"""


def upgrade() -> None:
    # 1. Drop the unnamed legacy foreign keys; they are re-created at the end with
    #    names and explicit ON DELETE rules. This also frees the keys changed below.
    for table, _col, _rt, _rc, legacy_name, _new, _od in FOREIGN_KEYS:
        op.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {legacy_name}")

    # 2. Audit timestamps on every table (DEC-08).
    for table in ALL_TABLES:
        op.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
            "ON UPDATE CURRENT_TIMESTAMP"
        )

    # 3. People: institutional id, unique login e-mail for professors (I-7, I-8).
    op.execute(
        "ALTER TABLE students "
        "ADD COLUMN national_id VARCHAR(20) NULL AFTER student_id, "
        "ADD CONSTRAINT uq_students_national_id UNIQUE (national_id)"
    )
    op.execute(
        "ALTER TABLE professors "
        "ADD COLUMN national_id VARCHAR(20) NULL AFTER professor_id, "
        "ADD CONSTRAINT uq_professors_national_id UNIQUE (national_id), "
        "MODIFY email VARCHAR(100) NOT NULL, "
        "ADD CONSTRAINT uq_professors_email UNIQUE (email)"
    )

    # 4. Academic periods (I-10).
    op.execute(
        "ALTER TABLE academic_periods "
        "ADD CONSTRAINT uq_academic_periods_name UNIQUE (name), "
        "ADD CONSTRAINT ck_academic_periods_dates CHECK (start_date < end_date)"
    )

    # 5. One thesis state machine instead of status + stage (finding 4, D-5).
    op.execute(
        """
        UPDATE theses SET status = CASE
          WHEN status = 'Defended'  THEN 'DEFENDED'
          WHEN status = 'In Review' THEN 'IN_REVIEW'
          WHEN stage  = 'Defense'   THEN 'READY_FOR_DEFENSE'
          WHEN stage  = 'Thesis II' THEN 'THESIS_II'
          WHEN status = 'Approved'  THEN 'THESIS_I'
          ELSE 'PROPOSED'
        END
        """
    )
    op.execute(
        "ALTER TABLE theses "
        f"MODIFY status ENUM({THESIS_STATUSES}) NOT NULL DEFAULT 'PROPOSED', "
        "DROP COLUMN stage, "
        "ADD INDEX ix_theses_status (status)"
    )

    # 6. Tutors (DEC-03, I-1): at most one Tutor and one Co-Tutor, different people.
    op.execute(
        "ALTER TABLE tutor_assignments "
        "DROP PRIMARY KEY, "
        "ADD PRIMARY KEY (thesis_id, role), "
        "ADD CONSTRAINT uq_tutor_thesis_professor UNIQUE (thesis_id, professor_id)"
    )

    # 7. Reviewers / defense committee (DEC-04, DEC-05).
    op.execute(
        "UPDATE reviewer_assignments SET role = 'Committee' "
        "WHERE role IS NULL OR role NOT IN ('President', 'Committee')"
    )
    op.execute(
        "ALTER TABLE reviewer_assignments "
        "MODIFY role ENUM('President','Committee') NOT NULL DEFAULT 'Committee', "
        "ADD COLUMN grade DECIMAL(4,2) NULL AFTER revision_corrected, "
        "ADD CONSTRAINT ck_reviewer_assignments_grade_range CHECK (grade >= 0 AND grade <= 10), "
        # MySQL has no partial unique indexes: index a column that only has a value
        # for the President row, so a second President violates the UNIQUE constraint.
        "ADD COLUMN president_thesis_id INT "
        "GENERATED ALWAYS AS (CASE WHEN role = 'President' THEN thesis_id END) STORED, "
        "ADD CONSTRAINT uq_one_president_per_thesis UNIQUE (president_thesis_id)"
    )
    # Safety net. Under concurrency the service also locks the thesis row first.
    op.execute(MAX3_TRIGGER)

    # 8. Value ranges (I-2).
    op.execute(
        "ALTER TABLE plagiarism_checks ADD CONSTRAINT ck_plagiarism_checks_similarity_range "
        "CHECK (similarity_percentage >= 0 AND similarity_percentage <= 100)"
    )
    op.execute(
        "ALTER TABLE defenses ADD CONSTRAINT ck_defenses_final_grade_range "
        "CHECK (final_grade >= 0 AND final_grade <= 10)"
    )

    # 9. Named foreign keys with explicit delete rules (I-3).
    for table, col, ref_table, ref_col, _legacy, new_name, on_delete in FOREIGN_KEYS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {new_name} FOREIGN KEY ({col}) "
            f"REFERENCES {ref_table} ({ref_col}) ON DELETE {on_delete}"
        )


def downgrade() -> None:
    for table, _col, _rt, _rc, _legacy, new_name, _od in FOREIGN_KEYS:
        op.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {new_name}")

    op.execute("ALTER TABLE defenses DROP CHECK ck_defenses_final_grade_range")
    op.execute("ALTER TABLE plagiarism_checks DROP CHECK ck_plagiarism_checks_similarity_range")

    op.execute("DROP TRIGGER IF EXISTS trg_reviewer_assignments_max3")
    op.execute(
        "ALTER TABLE reviewer_assignments "
        "DROP INDEX uq_one_president_per_thesis, "
        "DROP COLUMN president_thesis_id, "
        "DROP CHECK ck_reviewer_assignments_grade_range, "
        "DROP COLUMN grade, "
        "MODIFY role VARCHAR(50) NULL DEFAULT NULL"
    )

    op.execute(
        "ALTER TABLE tutor_assignments "
        "DROP INDEX uq_tutor_thesis_professor, "
        "DROP PRIMARY KEY, "
        "ADD PRIMARY KEY (thesis_id, professor_id, role)"
    )

    op.execute(
        "ALTER TABLE theses "
        "DROP INDEX ix_theses_status, "
        "MODIFY status VARCHAR(50) NULL DEFAULT NULL, "
        "ADD COLUMN stage VARCHAR(50) NULL AFTER status"
    )
    op.execute(
        """
        UPDATE theses SET
          stage = CASE
            WHEN status IN ('READY_FOR_DEFENSE', 'DEFENDED') THEN 'Defense'
            WHEN status IN ('THESIS_II', 'IN_REVIEW') THEN 'Thesis II'
            ELSE 'Thesis I'
          END,
          status = CASE
            WHEN status = 'DEFENDED' THEN 'Defended'
            WHEN status = 'IN_REVIEW' THEN 'In Review'
            WHEN status IN ('PROPOSED', 'REJECTED') THEN 'Draft'
            ELSE 'Approved'
          END
        """
    )

    op.execute(
        "ALTER TABLE academic_periods "
        "DROP CHECK ck_academic_periods_dates, DROP INDEX uq_academic_periods_name"
    )
    op.execute(
        "ALTER TABLE professors "
        "DROP INDEX uq_professors_email, MODIFY email VARCHAR(100) NULL, "
        "DROP INDEX uq_professors_national_id, DROP COLUMN national_id"
    )
    op.execute("ALTER TABLE students DROP INDEX uq_students_national_id, DROP COLUMN national_id")

    for table in ALL_TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN created_at, DROP COLUMN updated_at")

    # Re-create the foreign keys unnamed and in the original order, so MySQL gives them
    # back their legacy `<table>_ibfk_<n>` names.
    for table, col, ref_table, ref_col, _legacy, _new, _od in FOREIGN_KEYS:
        op.execute(
            f"ALTER TABLE {table} ADD FOREIGN KEY ({col}) REFERENCES {ref_table} ({ref_col})"
        )
