"""Add story_planners table.

Revision ID: 022
"""

revision = "022"
down_revision = "021"

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


def upgrade():
    op.create_table(
        "story_planners",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("persona_id", UUID(as_uuid=True), sa.ForeignKey("personas.id", ondelete="SET NULL"), index=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("rules", JSONB, server_default="[]"),
        sa.Column("highlight_collections", JSONB, server_default="[]"),
        sa.Column("highlight_config", JSONB, server_default="{}"),
        sa.Column("anti_repetition_days", sa.Integer, server_default="3"),
        sa.Column("seed", sa.Integer, server_default="1"),
        sa.Column("cycle", sa.Integer, server_default="0"),
        sa.Column("loop_cache", JSONB, nullable=True),
        sa.Column("depth_days", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("story_planners")
