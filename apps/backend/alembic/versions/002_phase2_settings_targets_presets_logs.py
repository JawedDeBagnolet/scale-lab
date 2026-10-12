"""002_phase2_settings_targets_presets_logs

Revision ID: 002
Revises: 001
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- workspace_settings (single-row, id=1) --------------------------------
    op.create_table(
        "workspace_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), server_default="Scale Lab", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("timezone", sa.String(length=50), server_default="Europe/Paris", nullable=False),
        sa.Column("oc_api_key", sa.Text(), nullable=True),
        sa.Column("oc_connected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("oc_last_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gms_api_key", sa.Text(), nullable=True),
        sa.Column("gms_connected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("gms_last_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tg_bot_token", sa.Text(), nullable=True),
        sa.Column("tg_chat_id", sa.String(length=100), nullable=True),
        sa.Column("tg_connected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "env_providers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "notifications",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- targets --------------------------------------------------------------
    op.create_table(
        "targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handle", sa.String(length=100), nullable=False),
        sa.Column("plateforme", sa.String(length=10), nullable=False),
        sa.Column("market", sa.String(length=10), nullable=True),
        sa.Column("niche_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="ok", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- presets --------------------------------------------------------------
    op.create_table(
        "presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("plateforme", sa.String(length=10), nullable=False),
        sa.Column("session_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- events ---------------------------------------------------------------
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=10), server_default="info", nullable=False),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("cause", sa.String(length=200), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_timestamp"), "events", ["timestamp"], unique=False)
    op.create_index(op.f("ix_events_module"), "events", ["module"], unique=False)

    # --- incidents ------------------------------------------------------------
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "solutions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "related_events",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incidents_module"), "incidents", ["module"], unique=False)

    # --- alert_rules ----------------------------------------------------------
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("threshold_errors", sa.Integer(), server_default="3", nullable=False),
        sa.Column("threshold_actions", sa.Integer(), server_default="10", nullable=False),
        sa.Column("tg_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("alert_rules")
    op.drop_index(op.f("ix_incidents_module"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_index(op.f("ix_events_module"), table_name="events")
    op.drop_index(op.f("ix_events_timestamp"), table_name="events")
    op.drop_table("events")
    op.drop_table("presets")
    op.drop_table("targets")
    op.drop_table("workspace_settings")
