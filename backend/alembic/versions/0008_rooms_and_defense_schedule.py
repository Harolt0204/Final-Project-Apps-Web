"""Rooms catalog and a real defense schedule (DEC-09, I-6, finding 8).

`defenses` stored `date`, `time` (free text) and `location` (free text), so overlapping
defenses could not be detected. They become:
- rooms: catalog of defense rooms;
- defenses.scheduled_at (DATETIME) + duration_minutes, room_id or meeting_url, and a
  closed modality. A CHECK keeps the place consistent with the modality:
  in-person => room and no link; virtual => link and no room.
The API rejects defenses that overlap in the same room or with the same jury member.

The defense jury is the reviewer committee (DEC-05); each member's grade lives in
reviewer_assignments.grade (0-10) and the final grade is their average (D-8 default).
A new setting stores the minimum passing grade (7.00 by default).

Legacy data: date + time become scheduled_at (time parsed when it looks like HH:MM;
otherwise 00:00; no date at all falls back to created_at), each distinct location becomes
a room, and missing places are filled with "Not recorded" so the constraints hold.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOT_RECORDED = "Not recorded"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE rooms (
          room_id    INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
          name       VARCHAR(100) NOT NULL,
          building   VARCHAR(100) NOT NULL,
          capacity   SMALLINT NULL,
          is_active  BOOLEAN NOT NULL DEFAULT TRUE,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          CONSTRAINT uq_rooms_building_name UNIQUE (building, name),
          CONSTRAINT ck_rooms_capacity CHECK (capacity IS NULL OR capacity > 0)
        )
        """
    )

    # --- legacy data -------------------------------------------------------------
    op.execute(
        """
        UPDATE defenses SET modality =
          IF(LOWER(TRIM(COALESCE(modality, ''))) LIKE 'virtual%', 'Virtual', 'In-person')
        """
    )
    op.execute(
        f"""
        INSERT INTO rooms (name, building)
        SELECT DISTINCT LEFT(TRIM(location), 100), '{NOT_RECORDED}' FROM defenses
        WHERE modality = 'In-person' AND location IS NOT NULL AND TRIM(location) <> ''
        """
    )
    op.execute(
        f"""
        INSERT INTO rooms (name, building)
        SELECT '{NOT_RECORDED}', '{NOT_RECORDED}' FROM DUAL
        WHERE EXISTS (SELECT 1 FROM defenses WHERE modality = 'In-person'
                      AND (location IS NULL OR TRIM(location) = ''))
        """
    )
    op.execute(
        "ALTER TABLE defenses "
        "ADD COLUMN scheduled_at DATETIME NULL AFTER thesis_id, "
        "ADD COLUMN duration_minutes SMALLINT NOT NULL DEFAULT 60 AFTER scheduled_at, "
        "ADD COLUMN room_id INT NULL AFTER modality, "
        "ADD COLUMN meeting_url VARCHAR(255) NULL AFTER room_id"
    )
    op.execute(
        """
        UPDATE defenses SET scheduled_at = COALESCE(
          TIMESTAMP(date, IF(TRIM(COALESCE(time, '')) REGEXP '^([01]?[0-9]|2[0-3]):[0-5][0-9]$',
                             MAKETIME(SUBSTRING_INDEX(TRIM(time), ':', 1),
                                      SUBSTRING_INDEX(TRIM(time), ':', -1), 0),
                             '00:00:00')),
          created_at)
        """
    )
    op.execute(
        f"""
        UPDATE defenses d JOIN rooms r
          ON r.building = '{NOT_RECORDED}'
         AND r.name = IF(d.location IS NULL OR TRIM(d.location) = '',
                         '{NOT_RECORDED}', LEFT(TRIM(d.location), 100))
        SET d.room_id = r.room_id
        WHERE d.modality = 'In-person'
        """
    )
    op.execute(f"UPDATE defenses SET meeting_url = '{NOT_RECORDED}' WHERE modality = 'Virtual'")

    # --- new structure -----------------------------------------------------------
    op.execute(
        "ALTER TABLE defenses "
        "DROP COLUMN date, DROP COLUMN time, DROP COLUMN location, "
        "MODIFY scheduled_at DATETIME NOT NULL, "
        "MODIFY modality ENUM('In-person','Virtual') NOT NULL DEFAULT 'In-person', "
        # No ON DELETE: MySQL forbids referential actions on a column used by a CHECK.
        "ADD CONSTRAINT fk_defenses_room_id FOREIGN KEY (room_id) REFERENCES rooms (room_id), "
        "ADD CONSTRAINT ck_defenses_duration CHECK (duration_minutes BETWEEN 15 AND 480), "
        "ADD CONSTRAINT ck_defenses_place CHECK ("
        "  (modality = 'In-person' AND room_id IS NOT NULL AND meeting_url IS NULL) OR "
        "  (modality = 'Virtual' AND room_id IS NULL AND meeting_url IS NOT NULL)), "
        "ADD INDEX ix_defenses_room_time (room_id, scheduled_at), "
        "ADD INDEX ix_defenses_scheduled_at (scheduled_at)"
    )

    op.execute(
        "INSERT INTO system_settings (setting_key, value, description) VALUES "
        "('defense_min_passing_grade', '7.00', 'Minimum final defense grade to pass (0-10)')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE setting_key = 'defense_min_passing_grade'")
    op.execute(
        "ALTER TABLE defenses "
        "DROP FOREIGN KEY fk_defenses_room_id, "
        "DROP CHECK ck_defenses_place, DROP CHECK ck_defenses_duration, "
        "DROP INDEX ix_defenses_room_time, DROP INDEX ix_defenses_scheduled_at, "
        "ADD COLUMN date DATE NULL AFTER thesis_id, "
        "ADD COLUMN time VARCHAR(50) NULL AFTER date, "
        "ADD COLUMN location VARCHAR(100) NULL AFTER time, "
        "MODIFY modality VARCHAR(50) NULL"
    )
    op.execute(
        """
        UPDATE defenses d LEFT JOIN rooms r ON r.room_id = d.room_id
        SET d.date = DATE(d.scheduled_at),
            d.time = DATE_FORMAT(d.scheduled_at, '%H:%i'),
            d.location = IF(d.modality = 'Virtual', d.meeting_url, r.name)
        """
    )
    op.execute(
        "ALTER TABLE defenses DROP COLUMN meeting_url, DROP COLUMN room_id, "
        "DROP COLUMN duration_minutes, DROP COLUMN scheduled_at"
    )
    op.execute("DROP TABLE rooms")
