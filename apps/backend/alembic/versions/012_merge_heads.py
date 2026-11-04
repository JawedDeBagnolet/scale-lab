"""Merge ghost head 3830510e0d5c with 011.

Revision ID: 012
Revises: 011, 3830510e0d5c
"""

from alembic import op

revision = "012"
down_revision = ("011", "3830510e0d5c")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
