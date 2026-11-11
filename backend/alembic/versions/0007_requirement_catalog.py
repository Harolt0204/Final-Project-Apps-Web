"""Administrative graduation requirements (FR-10, finding 3, D-6).

The inherited schema modelled requirements twice and incompletely:
(a) three booleans on students (curriculum, library, laboratory) with no date or author,
(b) a per-thesis `requirements` table with a free-text name that no endpoint used.
Both are replaced by:
- requirement_types: catalog of the requirements (regulation: internships, community
  engagement, foreign language...). Default list pending client validation (D-6).
- student_requirements: one row per student and requirement with who certified it,
  when, and the evidence. No row means "pending". A rejection needs a note.

Legacy data is migrated: true booleans become certifications, and rows of the old table
whose status is true are mapped by name (unknown names become inactive catalog entries).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# code, name, description, active, order
DEFAULT_TYPES = [
    ("CURRICULUM", "Curriculum completed", "All courses of the study plan passed.", 1, 10),
    (
        "INTERNSHIP",
        "Pre-professional internships",
        "Internship hours required by the CES academic regulation.",
        1,
        20,
    ),
    (
        "COMMUNITY",
        "Community engagement (vinculación con la sociedad)",
        "Community engagement hours required by the CES academic regulation.",
        1,
        30,
    ),
    (
        "LANGUAGE",
        "Foreign language proficiency",
        "Certificate of the foreign language level required by the university.",
        1,
        40,
    ),
    ("FINANCIAL", "Financial clearance", "No pending payments with the university.", 1, 50),
    ("LIBRARY", "Library clearance", "No borrowed books or pending fines.", 1, 60),
    (
        "LABORATORY",
        "Laboratory clearance",
        "Inherited from the previous system; not in the documented list (to confirm, D-6).",
        0,
        70,
    ),
]

LEGACY_FLAGS = [
    ("completed_curriculum", "CURRICULUM"),
    ("cleared_library", "LIBRARY"),
    ("cleared_laboratory", "LABORATORY"),
]


def _sql(value) -> str:
    return "'" + str(value).replace("'", "''") + "'" if isinstance(value, str) else str(value)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE requirement_types (
          requirement_type_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          code        VARCHAR(30)  NOT NULL,
          name        VARCHAR(150) NOT NULL,
          description TEXT NULL,
          is_active   BOOLEAN NOT NULL DEFAULT TRUE,
          sort_order  SMALLINT NOT NULL DEFAULT 0,
          created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT uq_requirement_types_code UNIQUE (code),
          CONSTRAINT uq_requirement_types_name UNIQUE (name)
        )
        """
    )
    values = ", ".join("(" + ", ".join(_sql(v) for v in row) + ")" for row in DEFAULT_TYPES)
    op.execute(
        "INSERT INTO requirement_types (code, name, description, is_active, sort_order) "
        f"VALUES {values}"
    )

    op.execute(
        """
        CREATE TABLE student_requirements (
          student_id          INT NOT NULL,
          requirement_type_id INT NOT NULL,
          status              ENUM('CERTIFIED','REJECTED') NOT NULL,
          certified_by        INT NULL,
          certified_at        DATETIME NOT NULL,
          evidence_url        VARCHAR(500) NULL,
          notes               TEXT NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (student_id, requirement_type_id),
          CONSTRAINT fk_student_requirements_student_id FOREIGN KEY (student_id)
            REFERENCES students (student_id) ON DELETE RESTRICT,
          CONSTRAINT fk_student_requirements_requirement_type_id
            FOREIGN KEY (requirement_type_id)
            REFERENCES requirement_types (requirement_type_id) ON DELETE RESTRICT,
          -- certified_by is NULL only for data migrated from the previous system.
          CONSTRAINT fk_student_requirements_certified_by FOREIGN KEY (certified_by)
            REFERENCES users (user_id) ON DELETE RESTRICT,
          CONSTRAINT ck_student_requirements_rejected_note
            CHECK (status <> 'REJECTED' OR notes IS NOT NULL)
        )
        """
    )

    # (a) Legacy booleans on students.
    for column, code in LEGACY_FLAGS:
        op.execute(
            f"""
            INSERT INTO student_requirements
              (student_id, requirement_type_id, status, certified_at, notes)
            SELECT s.student_id, t.requirement_type_id, 'CERTIFIED', CURRENT_TIMESTAMP,
                   'Migrated from the previous system'
            FROM students s JOIN requirement_types t ON t.code = '{code}'
            WHERE s.{column} = 1
            """
        )

    # (b) Legacy per-thesis table: unknown names become inactive catalog entries.
    op.execute(
        """
        INSERT INTO requirement_types (code, name, is_active, sort_order)
        SELECT DISTINCT CONCAT('TMP-', LEFT(MD5(TRIM(r.name)), 20)), TRIM(r.name), FALSE, 900
        FROM requirements r
        WHERE TRIM(r.name) NOT IN (SELECT name FROM requirement_types)
        """
    )
    op.execute(
        "UPDATE requirement_types SET code = CONCAT('LEGACY-', requirement_type_id) "
        "WHERE code LIKE 'TMP-%'"
    )
    op.execute(
        """
        INSERT IGNORE INTO student_requirements
          (student_id, requirement_type_id, status, certified_at, notes)
        SELECT th.student_id, t.requirement_type_id, 'CERTIFIED', CURRENT_TIMESTAMP,
               'Migrated from the previous system'
        FROM requirements r
        JOIN theses th ON th.thesis_id = r.thesis_id
        JOIN requirement_types t ON t.name = TRIM(r.name)
        WHERE r.status = 1
        """
    )

    op.execute("DROP TABLE requirements")
    op.execute(
        "ALTER TABLE students DROP COLUMN completed_curriculum, "
        "DROP COLUMN cleared_library, DROP COLUMN cleared_laboratory"
    )


def downgrade() -> None:
    """Restores the legacy columns and table. The booleans are filled back from the
    certifications; the old per-thesis table is recreated empty, because its rows
    cannot be rebuilt from per-student data."""
    op.execute(
        "ALTER TABLE students "
        "ADD COLUMN completed_curriculum BOOL NULL, "
        "ADD COLUMN cleared_library BOOL NULL, "
        "ADD COLUMN cleared_laboratory BOOL NULL"
    )
    for column, code in LEGACY_FLAGS:
        op.execute(
            f"""
            UPDATE students s SET s.{column} = EXISTS (
              SELECT 1 FROM student_requirements sr
              JOIN requirement_types t ON t.requirement_type_id = sr.requirement_type_id
              WHERE sr.student_id = s.student_id AND t.code = '{code}'
                AND sr.status = 'CERTIFIED')
            """
        )
    op.execute(
        """
        CREATE TABLE requirements (
          requirement_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          thesis_id      INT NOT NULL,
          name           VARCHAR(100) NOT NULL,
          status         BOOL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT fk_requirements_thesis_id FOREIGN KEY (thesis_id)
            REFERENCES theses (thesis_id) ON DELETE CASCADE
        )
        """
    )
    op.execute("DROP TABLE student_requirements")
    op.execute("DROP TABLE requirement_types")
