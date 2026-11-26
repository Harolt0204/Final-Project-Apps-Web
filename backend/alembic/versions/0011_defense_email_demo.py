"""Persist Gmail demo notification delivery alongside defense scheduling."""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "defense_emails",
        sa.Column("email_id", sa.Integer(), primary_key=True),
        sa.Column("thesis_id", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.String(100)),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.thesis_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_defense_emails_pending", "defense_emails", ["status", "available_at", "email_id"]
    )


def downgrade() -> None:
    op.drop_table("defense_emails")
