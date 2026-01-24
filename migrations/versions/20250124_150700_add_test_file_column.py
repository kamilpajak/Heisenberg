"""Add test_file column to analyses table.

Revision ID: 005
Revises: 004
Create Date: 2025-01-24 15:07:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("test_file", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analyses", "test_file")
