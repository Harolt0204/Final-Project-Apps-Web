"""Schools catalog (finding 9 in documentation.md).

`students.school` and `professors.school` were free text, so "average defense grade by
school" could not be computed reliably. They become a foreign key to `schools`.
Existing text values are migrated: each distinct name becomes a catalog row.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reference data: the schools of Yachay Tech University.
YACHAY_SCHOOLS = [
    ("MATH", "School of Mathematical and Computational Sciences"),
    ("PHYS", "School of Physical Sciences and Nanotechnology"),
    ("BIO", "School of Biological Sciences and Engineering"),
    ("CHEM", "School of Chemical Sciences and Engineering"),
    ("EARTH", "School of Earth Sciences, Energy and Environment"),
    ("AGRO", "School of Agricultural and Agroindustrial Sciences"),
]

PEOPLE = ["students", "professors"]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE schools (
          school_id  INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          code       VARCHAR(20)  NOT NULL,
          name       VARCHAR(150) NOT NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT uq_schools_code UNIQUE (code),
          CONSTRAINT uq_schools_name UNIQUE (name)
        )
        """
    )
    values = ", ".join(f"('{code}', '{name}')" for code, name in YACHAY_SCHOOLS)
    op.execute(f"INSERT INTO schools (code, name) VALUES {values}")

    # Free-text names not in the catalog are kept as new rows (code generated from id).
    for table in PEOPLE:
        op.execute(
            f"""
            INSERT INTO schools (code, name)
            SELECT DISTINCT CONCAT('TMP-', MD5(TRIM(t.school))), TRIM(t.school)
            FROM {table} t
            WHERE t.school IS NOT NULL AND TRIM(t.school) <> ''
              AND TRIM(t.school) NOT IN (SELECT name FROM schools)
            """
        )
    op.execute("UPDATE schools SET code = CONCAT('S', school_id) WHERE code LIKE 'TMP-%'")

    for table in PEOPLE:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN school_id INT NULL AFTER last_name, "
            f"ADD CONSTRAINT fk_{table}_school_id FOREIGN KEY (school_id) "
            "REFERENCES schools (school_id) ON DELETE RESTRICT"
        )
        op.execute(
            f"UPDATE {table} t JOIN schools s ON s.name = TRIM(t.school) "
            "SET t.school_id = s.school_id"
        )
        op.execute(f"ALTER TABLE {table} DROP COLUMN school")


def downgrade() -> None:
    for table in PEOPLE:
        op.execute(f"ALTER TABLE {table} ADD COLUMN school VARCHAR(100) NULL AFTER last_name")
        op.execute(
            f"UPDATE {table} t JOIN schools s ON s.school_id = t.school_id "
            "SET t.school = LEFT(s.name, 100)"
        )
        op.execute(f"ALTER TABLE {table} DROP FOREIGN KEY fk_{table}_school_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN school_id")
    op.execute("DROP TABLE schools")
