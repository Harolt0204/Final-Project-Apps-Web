"""Login accounts with global roles (DEC-07) and the thesis status history (DEC-08).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THESIS_STATUSES = (
    "'PROPOSED','TOPIC_APPROVED','THESIS_I','THESIS_II',"
    "'IN_REVIEW','READY_FOR_DEFENSE','DEFENDED','REJECTED'"
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
          user_id       INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          email         VARCHAR(100) NOT NULL,
          password_hash VARCHAR(255) NOT NULL,
          role          ENUM('admin','professor','student') NOT NULL,
          student_id    INT NULL,
          professor_id  INT NULL,
          is_active     BOOLEAN NOT NULL DEFAULT TRUE,
          last_login_at DATETIME NULL,
          created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT uq_users_email        UNIQUE (email),
          CONSTRAINT uq_users_student_id   UNIQUE (student_id),
          CONSTRAINT uq_users_professor_id UNIQUE (professor_id),
          -- No ON DELETE: MySQL forbids referential actions on columns used by a CHECK.
          -- People are never deleted; their account is deactivated instead.
          CONSTRAINT fk_users_student_id   FOREIGN KEY (student_id)
            REFERENCES students (student_id),
          CONSTRAINT fk_users_professor_id FOREIGN KEY (professor_id)
            REFERENCES professors (professor_id),
          CONSTRAINT ck_users_link CHECK (
            (role = 'student'   AND student_id IS NOT NULL AND professor_id IS NULL) OR
            (role = 'professor' AND professor_id IS NOT NULL AND student_id IS NULL) OR
            (role = 'admin'     AND student_id IS NULL     AND professor_id IS NULL))
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE thesis_status_history (
          history_id  INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          thesis_id   INT NOT NULL,
          from_status ENUM({THESIS_STATUSES}) NULL,
          to_status   ENUM({THESIS_STATUSES}) NOT NULL,
          changed_by  INT NOT NULL,
          changed_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          comment     TEXT NULL,
          CONSTRAINT fk_thesis_status_history_thesis_id FOREIGN KEY (thesis_id)
            REFERENCES theses (thesis_id) ON DELETE RESTRICT,
          CONSTRAINT fk_thesis_status_history_changed_by FOREIGN KEY (changed_by)
            REFERENCES users (user_id) ON DELETE RESTRICT,
          INDEX ix_tsh_thesis_time (thesis_id, changed_at)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE thesis_status_history")
    op.execute("DROP TABLE users")
