"""Add rotation_url to proxies table.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxies", sa.Column("rotation_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("proxies", "rotation_url")
