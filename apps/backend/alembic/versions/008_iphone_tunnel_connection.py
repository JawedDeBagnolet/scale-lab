"""008_iphone_tunnel_connection

Add connection_type, mcp_port, crane_port to iphones table
to support dual USB + reverse SSH tunnel dispatch.

Revision ID: 008
Revises: 007
Create Date: 2026-10-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "iphones",
        sa.Column(
            "connection_type",
            sa.String(10),
            server_default="usb",
            nullable=False,
        ),
    )
    op.add_column(
        "iphones",
        sa.Column("mcp_port", sa.Integer(), nullable=True),
    )
    op.add_column(
        "iphones",
        sa.Column("crane_port", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("iphones", "crane_port")
    op.drop_column("iphones", "mcp_port")
    op.drop_column("iphones", "connection_type")
