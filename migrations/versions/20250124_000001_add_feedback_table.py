"""Add feedback table.

Revision ID: 002
Revises: 001
Create Date: 2025-01-24 00:00:01.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create feedbacks table
    op.create_table(
        "feedbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_helpful", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analyses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedbacks_analysis_id", "feedbacks", ["analysis_id"])
    op.create_index("ix_feedbacks_is_helpful", "feedbacks", ["is_helpful"])


def downgrade() -> None:
    op.drop_index("ix_feedbacks_is_helpful")
    op.drop_index("ix_feedbacks_analysis_id")
    op.drop_table("feedbacks")
