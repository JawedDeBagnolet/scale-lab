"""004_engine_run_fields — Add account_progress and config to runs

Revision ID: 004
Revises: 003
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Per-account step tracking: {account_id: {step_idx: "ok"|"running"|"error"|"waiting"|"blocked"|"skipped"}}
    op.add_column(
        "runs",
        sa.Column("account_progress", postgresql.JSONB(), server_default="{}", nullable=True),
    )
    # Launch config: {ignore_slots: bool, launched_by: str, ...}
    op.add_column(
        "runs",
        sa.Column("config", postgresql.JSONB(), server_default="{}", nullable=True),
    )
    # Next scheduled wake time for the engine (when a delay/slot is pending)
    op.add_column(
        "runs",
        sa.Column("next_wake_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Index for engine queries: find active runs quickly
    op.create_index(
        "ix_runs_status_active",
        "runs",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'running', 'paused')"),
    )


def downgrade() -> None:
    op.drop_index("ix_runs_status_active", table_name="runs")
    op.drop_column("runs", "next_wake_at")
    op.drop_column("runs", "config")
    op.drop_column("runs", "account_progress")
