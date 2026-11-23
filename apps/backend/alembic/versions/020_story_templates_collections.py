"""Add story_templates and story_collections tables.

Revision ID: 020
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("persona_id", UUID(as_uuid=True), sa.ForeignKey("personas.id", ondelete="SET NULL"), index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("story_type", sa.String(50), nullable=False, server_default="lifestyle"),
        sa.Column("username", sa.String(100), nullable=False, server_default=""),
        sa.Column("color", sa.String(20), nullable=False, server_default="#1b1f33"),
        sa.Column("media_ids", JSONB, server_default="[]"),
        sa.Column("bg_idx", sa.Integer, nullable=False, server_default="-1"),
        sa.Column("elements", JSONB, nullable=False, server_default="[]"),
        sa.Column("moments", JSONB, server_default="[]"),
        sa.Column("is_liked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "story_collections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("persona_id", UUID(as_uuid=True), sa.ForeignKey("personas.id", ondelete="SET NULL"), index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),  # story, hl
        sa.Column("story_type", sa.String(50)),
        sa.Column("template_ids", JSONB, server_default="[]"),
        sa.Column("by_persona", JSONB, server_default="{}"),
        sa.Column("highlight_name", sa.String(200)),
        sa.Column("highlight_icon", sa.String(50)),
        sa.Column("schedule", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("story_collections")
    op.drop_table("story_templates")
