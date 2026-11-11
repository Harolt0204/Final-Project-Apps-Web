"""Token revocation on password change (hardening, Sprint 6).

`users.password_changed_at` records when the password last changed. Access tokens issued
before that moment are rejected, so changing or resetting a password logs out every
other session that used the old one.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN password_changed_at DATETIME NULL AFTER password_hash")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN password_changed_at")
