"""Review observations with history (FR-08, finding 5 in documentation.md).

The inherited schema kept ONE observation per reviewer in `reviewer_assignments.comments`
(overwritten each time) plus a `revision_corrected` flag. They become:
- `review_observations`: every observation, the student's response and its resolution.
  The composite foreign key to reviewer_assignments guarantees, in the database, that
  only a reviewer of the thesis can author an observation on it.
- `reviewer_assignments.approved_at`: when the reviewer approved the manuscript.
Existing comments are migrated as observations (resolved when revision_corrected was true).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE review_observations (
          observation_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          thesis_id      INT NOT NULL,
          professor_id   INT NOT NULL,
          text           TEXT NOT NULL,
          status         ENUM('OPEN','ADDRESSED','RESOLVED') NOT NULL DEFAULT 'OPEN',
          response       TEXT NULL,
          responded_at   DATETIME NULL,
          resolved_at    DATETIME NULL,
          created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT fk_review_observations_reviewer FOREIGN KEY (thesis_id, professor_id)
            REFERENCES reviewer_assignments (thesis_id, professor_id) ON DELETE RESTRICT,
          CONSTRAINT ck_review_observations_addressed
            CHECK (status <> 'ADDRESSED' OR response IS NOT NULL),
          CONSTRAINT ck_review_observations_resolved
            CHECK (status <> 'RESOLVED' OR resolved_at IS NOT NULL),
          INDEX ix_review_observations_thesis_status (thesis_id, status)
        )
        """
    )
    op.execute(
        """
        INSERT INTO review_observations (thesis_id, professor_id, text, status, resolved_at)
        SELECT thesis_id, professor_id, comments,
               IF(revision_corrected, 'RESOLVED', 'OPEN'),
               IF(revision_corrected, CURRENT_TIMESTAMP, NULL)
        FROM reviewer_assignments
        WHERE comments IS NOT NULL AND TRIM(comments) <> ''
        """
    )
    op.execute(
        "ALTER TABLE reviewer_assignments "
        "ADD COLUMN approved_at DATETIME NULL AFTER role, "
        "DROP COLUMN comments, "
        "DROP COLUMN revision_corrected"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE reviewer_assignments "
        "ADD COLUMN comments TEXT NULL AFTER role, "
        "ADD COLUMN revision_corrected BOOL NULL AFTER comments"
    )
    # Back to one text per reviewer: all their observations, concatenated.
    op.execute(
        """
        UPDATE reviewer_assignments ra
        JOIN (
          SELECT thesis_id, professor_id,
                 GROUP_CONCAT(text ORDER BY created_at SEPARATOR '\\n---\\n') AS texts,
                 MIN(status = 'RESOLVED') AS all_resolved
          FROM review_observations
          GROUP BY thesis_id, professor_id
        ) o ON o.thesis_id = ra.thesis_id AND o.professor_id = ra.professor_id
        SET ra.comments = o.texts, ra.revision_corrected = o.all_resolved
        """
    )
    op.execute("ALTER TABLE reviewer_assignments DROP COLUMN approved_at")
    op.execute("DROP TABLE review_observations")
