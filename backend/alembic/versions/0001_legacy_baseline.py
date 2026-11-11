"""Baseline: the inherited schema, exactly as the previous project created it.

This is the DDL that `thesis_api/models.py` produced through `db.create_all()`
(documentation.md, section 3.1), including its weaknesses. It is NOT corrected here on
purpose: every correction is a later migration, so the evolution stays traceable.
Foreign keys are left unnamed, as SQLAlchemy created them, so MySQL names them
`<table>_ibfk_<n>`; migration 0002 relies on those names.

Revision ID: 0001
Revises:
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_DDL = [
    """
    CREATE TABLE students (
      student_id           INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      first_name           VARCHAR(100) NOT NULL,
      last_name            VARCHAR(100) NOT NULL,
      school               VARCHAR(100),
      institution          VARCHAR(100),
      email                VARCHAR(100) NOT NULL UNIQUE,
      phone                VARCHAR(20),
      completed_curriculum BOOL,
      cleared_library      BOOL,
      cleared_laboratory   BOOL
    )
    """,
    """
    CREATE TABLE professors (
      professor_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      first_name   VARCHAR(100) NOT NULL,
      last_name    VARCHAR(100) NOT NULL,
      school       VARCHAR(100),
      institution  VARCHAR(100),
      email        VARCHAR(100)
    )
    """,
    """
    CREATE TABLE academic_periods (
      period_id  INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      name       VARCHAR(100) NOT NULL,
      start_date DATE,
      end_date   DATE
    )
    """,
    """
    CREATE TABLE theses (
      thesis_id  INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      title      VARCHAR(255) NOT NULL,
      abstract   TEXT,
      status     VARCHAR(50),
      stage      VARCHAR(50),
      student_id INT NOT NULL UNIQUE,
      FOREIGN KEY (student_id) REFERENCES students(student_id)
    )
    """,
    """
    CREATE TABLE thesis_period (
      thesis_id INT NOT NULL,
      period_id INT NOT NULL,
      PRIMARY KEY (thesis_id, period_id),
      FOREIGN KEY (thesis_id) REFERENCES theses(thesis_id),
      FOREIGN KEY (period_id) REFERENCES academic_periods(period_id)
    )
    """,
    """
    CREATE TABLE tutor_assignments (
      thesis_id    INT NOT NULL,
      professor_id INT NOT NULL,
      role         ENUM('Tutor','Co-Tutor') NOT NULL,
      PRIMARY KEY (thesis_id, professor_id, role),
      FOREIGN KEY (thesis_id)    REFERENCES theses(thesis_id),
      FOREIGN KEY (professor_id) REFERENCES professors(professor_id)
    )
    """,
    """
    CREATE TABLE reviewer_assignments (
      thesis_id          INT NOT NULL,
      professor_id       INT NOT NULL,
      role               VARCHAR(50),
      comments           TEXT,
      revision_corrected BOOL,
      PRIMARY KEY (thesis_id, professor_id),
      FOREIGN KEY (thesis_id)    REFERENCES theses(thesis_id),
      FOREIGN KEY (professor_id) REFERENCES professors(professor_id)
    )
    """,
    """
    CREATE TABLE requirements (
      requirement_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      thesis_id      INT NOT NULL,
      name           VARCHAR(100) NOT NULL,
      status         BOOL,
      FOREIGN KEY (thesis_id) REFERENCES theses(thesis_id)
    )
    """,
    """
    CREATE TABLE plagiarism_checks (
      check_id              INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      thesis_id             INT NOT NULL UNIQUE,
      similarity_percentage NUMERIC(5,2),
      FOREIGN KEY (thesis_id) REFERENCES theses(thesis_id)
    )
    """,
    """
    CREATE TABLE defenses (
      defense_id  INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      thesis_id   INT NOT NULL UNIQUE,
      date        DATE,
      time        VARCHAR(50),
      location    VARCHAR(100),
      modality    VARCHAR(50),
      final_grade NUMERIC(4,2),
      FOREIGN KEY (thesis_id) REFERENCES theses(thesis_id)
    )
    """,
]

# Reverse dependency order.
LEGACY_TABLES = [
    "defenses",
    "plagiarism_checks",
    "requirements",
    "reviewer_assignments",
    "tutor_assignments",
    "thesis_period",
    "theses",
    "academic_periods",
    "professors",
    "students",
]


def upgrade() -> None:
    for statement in LEGACY_DDL:
        op.execute(statement)


def downgrade() -> None:
    for table in LEGACY_TABLES:
        op.execute(f"DROP TABLE {table}")
