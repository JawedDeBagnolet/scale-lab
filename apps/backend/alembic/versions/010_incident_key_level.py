"""Add key, level, title, causes columns to incidents table.

Revision ID: 010_incident_key_level
Revises: 009_crane_to_ssh_port
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010_incident_key_level"
down_revision = "009_crane_to_ssh_port"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column("incidents", sa.Column("key", sa.String(300), nullable=True))
    op.add_column("incidents", sa.Column("level", sa.String(10), server_default="error", nullable=False))
    op.add_column("incidents", sa.Column("title", sa.String(300), server_default="", nullable=False))
    op.add_column("incidents", sa.Column("causes", postgresql.JSONB(), nullable=True))

    # Populate key from existing data: module|event_type|target
    op.execute(
        "UPDATE incidents SET key = module || '|' || event_type || '|' || COALESCE(target, '')"
        " WHERE key IS NULL"
    )

    # Make key not nullable and add unique index
    op.alter_column("incidents", "key", nullable=False)
    op.create_index(op.f("ix_incidents_key"), "incidents", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_incidents_key"), table_name="incidents")
    op.drop_column("incidents", "causes")
    op.drop_column("incidents", "title")
    op.drop_column("incidents", "level")
    op.drop_column("incidents", "key")
