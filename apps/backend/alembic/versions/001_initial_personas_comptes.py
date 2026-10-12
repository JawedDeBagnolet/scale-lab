"""001_initial_personas_comptes

Revision ID: 001
Revises:
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marches",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("actif", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("langue", sa.String(length=5), nullable=True),
        sa.Column("fuseau", sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "niches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_table(
        "personas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prs_id", sa.String(length=100), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("market", sa.String(length=10), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("platforms", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("niches", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("bios", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("funnel", sa.Text(), nullable=True),
        sa.Column("telegram", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "comptes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handle", sa.String(length=100), nullable=False),
        sa.Column("persona_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("plateforme", sa.String(length=10), nullable=False),
        sa.Column("workflow", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("device_id", sa.String(length=100), nullable=True),
        sa.Column("proxy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("env", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sessions", sa.Integer(), nullable=False),
        sa.Column("follows", sa.Integer(), nullable=False),
        sa.Column("creds_encrypted", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_comptes_persona_id"), "comptes", ["persona_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_comptes_persona_id"), table_name="comptes")
    op.drop_table("comptes")
    op.drop_table("personas")
    op.drop_table("niches")
    op.drop_table("marches")
