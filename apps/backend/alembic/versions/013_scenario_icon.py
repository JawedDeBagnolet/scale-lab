"""Add icon column to scenarios table.

Revision ID: 013
Revises: 012
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scenarios",
        sa.Column("icon", sa.String(50), nullable=True, server_default="lightning"),
    )


def downgrade() -> None:
    op.drop_column("scenarios", "icon")
