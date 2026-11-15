"""Log in with the user name (name.lastname) instead of the full institutional e-mail.

`users.email` becomes `users.username` and keeps only the local part of the address
(name.lastname@yachaytech.edu.ec -> name.lastname). Students and professors keep their
full e-mail as contact data; their account user name is derived from it.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN = "yachaytech.edu.ec"


def upgrade() -> None:
    op.execute("ALTER TABLE users RENAME COLUMN email TO username")
    op.execute("ALTER TABLE users RENAME INDEX uq_users_email TO uq_users_username")
    op.execute("UPDATE users SET username = LOWER(SUBSTRING_INDEX(username, '@', 1))")


def downgrade() -> None:
    op.execute(f"UPDATE users SET username = CONCAT(username, '@{DOMAIN}')")
    op.execute("ALTER TABLE users RENAME INDEX uq_users_username TO uq_users_email")
    op.execute("ALTER TABLE users RENAME COLUMN username TO email")
