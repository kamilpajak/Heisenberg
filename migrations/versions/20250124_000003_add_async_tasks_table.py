"""Add async_tasks table for background processing.

Revision ID: 004
Revises: 003
Create Date: 2025-01-24 00:00:03.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create task status enum
    task_status_enum = postgresql.ENUM(
        "pending", "running", "completed", "failed",
        name="taskstatus",
        create_type=True,
    )
    task_status_enum.create(op.get_bind(), checkfirst=True)

    # Create async_tasks table
    op.create_table(
        "async_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            task_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_async_tasks_organization_id", "async_tasks", ["organization_id"])
    op.create_index("ix_async_tasks_status", "async_tasks", ["status"])
    op.create_index("ix_async_tasks_created_at", "async_tasks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_async_tasks_created_at")
    op.drop_index("ix_async_tasks_status")
    op.drop_index("ix_async_tasks_organization_id")
    op.drop_table("async_tasks")

    # Drop the enum type
    task_status_enum = postgresql.ENUM(
        "pending", "running", "completed", "failed",
        name="taskstatus",
    )
    task_status_enum.drop(op.get_bind(), checkfirst=True)
