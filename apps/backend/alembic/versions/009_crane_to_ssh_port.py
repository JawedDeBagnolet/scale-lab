"""009_crane_to_ssh_port

Rename crane_port → ssh_port on iphones table.
crane-controller is replaced by ScaleTweak (scalectl CLI via SSH).

Revision ID: 009
Revises: 008
Create Date: 2026-10-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("iphones", "crane_port", new_column_name="ssh_port")


def downgrade() -> None:
    op.alter_column("iphones", "ssh_port", new_column_name="crane_port")
