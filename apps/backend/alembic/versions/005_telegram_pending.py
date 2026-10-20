"""005_telegram_pending — Table for pending Telegram model registrations

Revision ID: 005
Revises: 004
Create Date: 2026-10-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_pending",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("tg_user_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("tg_username", sa.String(100)),
        sa.Column("tg_first_name", sa.String(200)),
        sa.Column("tg_lang", sa.String(10)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("telegram_pending")
