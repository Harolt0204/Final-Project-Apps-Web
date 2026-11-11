"""Similarity (plagiarism) check history (FR-07, finding 7) and system settings (D-8).

- plagiarism_checks allowed ONE check per thesis and had no date, tool or verdict, so a
  re-check after corrections overwrote the previous one. It becomes a history: several
  checks per thesis, each with date, tool, the threshold applied and the verdict. A CHECK
  constraint keeps the verdict consistent with the percentage and the threshold.
- system_settings stores parameters such as the maximum similarity accepted, instead of
  hard-coding them (documentation.md, D-8). Default: 10 %, pending client validation.

Legacy rows without a percentage carry no information and are removed.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_THRESHOLD = "10.00"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE system_settings (
          setting_key VARCHAR(50)  NOT NULL PRIMARY KEY,
          value       VARCHAR(255) NOT NULL,
          description VARCHAR(255) NULL,
          created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "INSERT INTO system_settings (setting_key, value, description) VALUES "
        f"('similarity_max_percentage', '{DEFAULT_THRESHOLD}', "
        "'Maximum similarity percentage accepted in a plagiarism check')"
    )

    op.execute("DELETE FROM plagiarism_checks WHERE similarity_percentage IS NULL")
    # A new index on thesis_id first, so the foreign key keeps an index when the
    # legacy UNIQUE index (named `thesis_id`) is dropped.
    op.execute(
        "ALTER TABLE plagiarism_checks "
        "ADD COLUMN checked_at DATETIME NULL AFTER similarity_percentage, "
        "ADD COLUMN tool VARCHAR(100) NULL AFTER checked_at, "
        "ADD COLUMN threshold_applied DECIMAL(5,2) NULL AFTER tool, "
        "ADD COLUMN verdict ENUM('ACCEPTED','REJECTED') NULL AFTER threshold_applied, "
        "ADD COLUMN report_url VARCHAR(500) NULL AFTER verdict, "
        "ADD COLUMN notes TEXT NULL AFTER report_url, "
        "ADD COLUMN recorded_by INT NULL AFTER notes, "
        "ADD INDEX ix_plagiarism_checks_thesis_time (thesis_id, checked_at)"
    )
    op.execute("ALTER TABLE plagiarism_checks DROP INDEX thesis_id")
    op.execute(
        f"""
        UPDATE plagiarism_checks SET
          checked_at = created_at,
          tool = 'Not recorded (legacy)',
          threshold_applied = {DEFAULT_THRESHOLD},
          verdict = IF(similarity_percentage <= {DEFAULT_THRESHOLD}, 'ACCEPTED', 'REJECTED')
        """
    )
    op.execute(
        "ALTER TABLE plagiarism_checks "
        "MODIFY similarity_percentage DECIMAL(5,2) NOT NULL, "
        "MODIFY checked_at DATETIME NOT NULL, "
        "MODIFY tool VARCHAR(100) NOT NULL, "
        "MODIFY threshold_applied DECIMAL(5,2) NOT NULL, "
        "MODIFY verdict ENUM('ACCEPTED','REJECTED') NOT NULL, "
        "ADD CONSTRAINT ck_plagiarism_checks_threshold_range "
        "  CHECK (threshold_applied >= 0 AND threshold_applied <= 100), "
        "ADD CONSTRAINT ck_plagiarism_checks_verdict "
        "  CHECK ((verdict = 'ACCEPTED') = (similarity_percentage <= threshold_applied)), "
        # recorded_by is NULL only for legacy rows.
        "ADD CONSTRAINT fk_plagiarism_checks_recorded_by FOREIGN KEY (recorded_by) "
        "  REFERENCES users (user_id) ON DELETE RESTRICT"
    )


def downgrade() -> None:
    # Back to one check per thesis: keep the most recent one.
    op.execute(
        """
        DELETE p FROM plagiarism_checks p
        JOIN plagiarism_checks newer
          ON newer.thesis_id = p.thesis_id
         AND (newer.checked_at > p.checked_at
              OR (newer.checked_at = p.checked_at AND newer.check_id > p.check_id))
        """
    )
    op.execute(
        "ALTER TABLE plagiarism_checks "
        "DROP FOREIGN KEY fk_plagiarism_checks_recorded_by, "
        "DROP CHECK ck_plagiarism_checks_verdict, "
        "DROP CHECK ck_plagiarism_checks_threshold_range"
    )
    op.execute("ALTER TABLE plagiarism_checks ADD UNIQUE INDEX thesis_id (thesis_id)")
    op.execute(
        "ALTER TABLE plagiarism_checks "
        "DROP INDEX ix_plagiarism_checks_thesis_time, "
        "DROP INDEX fk_plagiarism_checks_recorded_by, "
        "DROP COLUMN recorded_by, DROP COLUMN notes, DROP COLUMN report_url, "
        "DROP COLUMN verdict, DROP COLUMN threshold_applied, DROP COLUMN tool, "
        "DROP COLUMN checked_at, "
        "MODIFY similarity_percentage DECIMAL(5,2) NULL"
    )
    op.execute("DROP TABLE system_settings")
